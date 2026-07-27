# -*- coding: utf-8 -*-
"""
Dosya İndeksi — "hangi dosya nerede" bilgisi.

`file_finder.py` yalnızca 6 standart klasörün ÜST SEVİYESİNE bakar (os.listdir),
alt klasörleri hiç görmez. Bu modül kullanıcı klasörlerini alt klasörleriyle
birlikte tarayıp SQLite'a indeksler; böylece "rapor" yazınca dosya nerede olursa
olsun bulunur — ve telefondan da aranabilir.

Tasarım:
  • Ayrı veritabanı (`file_index.db`) — ana bilgiler.db şişmesin, kilit çakışmasın
  • Her çağrı kendi bağlantısını açar (proje kuralı: SQLite thread'ler arası paylaşılmaz)
  • Tarama süre ve dosya sayısı sınırlı — asistan donmasın

GÜVENLİK — bu indeks telefondan erişilebilir olduğu için:
  • Sadece kullanıcının kendi belge klasörleri taranır (Windows/Program Files/AppData YOK)
  • Sır taşıyan dosyalar indekse HİÇ girmez (.env, *.pem, *.kdbx, id_rsa, config.json…)
  • Uzaktan gönderim kararı bu modülde değil — çağıran katman onay kartı uygular
"""

import os
import re
import sqlite3
import time
from datetime import datetime

from core.paths import veri_yolu

INDEX_DB = veri_yolu('file_index.db')

# Tarama sınırları — asistan dakikalarca meşgul olmasın
MAX_DOSYA = 400_000
MAX_SURE_SN = 120
MAX_DERINLIK = 8

# ---------------------------------------------------------------------------
# GÜVENLİK FİLTRELERİ
# ---------------------------------------------------------------------------
# Bu klasörler hiç taranmaz (sistem, gizli veri, çöp)
ATLANAN_KLASORLER = {
    'appdata', 'windows', 'program files', 'program files (x86)', 'programdata',
    'node_modules', '.git', '.svn', '__pycache__', 'venv', '.venv', 'env',
    'site-packages', 'dist', 'build', '_internal', '.cache', '.next', 'target',
    '$recycle.bin', 'system volume information', '.vscode', '.idea', '.ssh', '.aws',
    '.gnupg', '.docker', '.npm', '.gradle', '.m2', 'temp', 'tmp',
}

# Bu adlar/uzantılar sır taşır — telefondan erişilebilir bir indekse ASLA girmez
GIZLI_ADLAR = {
    '.env', 'config.json', 'user_data.json', 'credentials.json', 'token.json',
    'secrets.json', 'id_rsa', 'id_ed25519', 'id_dsa', '.htpasswd', '.netrc',
    'shadow', 'sam', '.git-credentials', 'wallet.dat',
}
GIZLI_UZANTILAR = {
    '.key', '.pem', '.pfx', '.p12', '.kdbx', '.ppk', '.keystore', '.jks',
    '.asc', '.gpg', '.ovpn',
}
GIZLI_KALIPLAR = ('secret', 'password', 'parola', 'private_key', 'privatekey',
                  'credential', 'api_key', 'apikey')

# Anlamsız uzantılar — indekse girmesin (gürültü)
ATLANAN_UZANTILAR = {'.tmp', '.log', '.lock', '.pyc', '.pyo', '.obj', '.o',
                     '.class', '.pdb', '.ini', '.dat', '.db-journal', '.crdownload'}

# file_finder ile aynı tür sözlüğü (tek kaynak olsun diye oradan alınır)
try:
    from features.file_finder import TUR_UZANTILARI, KLASORLER, _gercek_yol
except Exception:                                    # pragma: no cover
    TUR_UZANTILARI, KLASORLER = {}, {}

    def _gercek_yol(k):
        return None


def _baglanti():
    conn = sqlite3.connect(INDEX_DB, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dosyalar (
            yol       TEXT PRIMARY KEY,
            ad        TEXT NOT NULL,
            ad_sade   TEXT NOT NULL,
            uzanti    TEXT,
            klasor    TEXT,
            kok       TEXT,
            boyut     INTEGER,
            degisim   REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ad_sade ON dosyalar(ad_sade)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_degisim ON dosyalar(degisim)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (anahtar TEXT PRIMARY KEY, deger TEXT)")
    return conn


# ---------------------------------------------------------------------------
# Türkçe sadeleştirme — "İndirilenler'deki RAPOR.pdf" ile "rapor" eşleşsin
# ---------------------------------------------------------------------------
_TR_HARITA = str.maketrans('çğıöşüâîûÇĞİÖŞÜ', 'cgiosuaiucgiosu')


def sadelestir(metin: str) -> str:
    return (metin or '').lower().translate(_TR_HARITA)


def gizli_mi(ad: str) -> bool:
    """Dosya sır taşıyor mu? (indekse alınmaz, uzaktan erişilemez)"""
    adl = ad.lower()
    if adl in GIZLI_ADLAR:
        return True
    if os.path.splitext(adl)[1] in GIZLI_UZANTILAR:
        return True
    return any(k in adl for k in GIZLI_KALIPLAR)


def _kokler():
    """Taranacak kök klasörler → [(yol, etiket)]"""
    kokler = []
    for std, etiket in (('Desktop', 'Masaüstü'), ('Documents', 'Belgeler'),
                        ('Downloads', 'İndirilenler'), ('Pictures', 'Resimler'),
                        ('Music', 'Müzikler'), ('Videos', 'Videolar')):
        yol = _gercek_yol(std)
        if yol and os.path.isdir(yol):
            kokler.append((yol, etiket))
    return kokler


# ---------------------------------------------------------------------------
# İNDEKSLEME
# ---------------------------------------------------------------------------
def indeksi_yenile(ilerleme_cb=None):
    """
    Kök klasörleri alt klasörleriyle tarar ve indeksi baştan kurar.
    Dönüş: (dosya_sayisi, gecen_saniye, atlanan_gizli_sayisi)
    """
    baslangic = time.time()
    kayitlar = []
    gizli_atlanan = 0

    for kok, etiket in _kokler():
        kok_derinlik = kok.rstrip(os.sep).count(os.sep)
        for dizin, alt_dizinler, dosyalar in os.walk(kok):
            # Derinlik ve süre freni
            if dizin.count(os.sep) - kok_derinlik >= MAX_DERINLIK:
                alt_dizinler[:] = []
                continue
            if time.time() - baslangic > MAX_SURE_SN or len(kayitlar) >= MAX_DOSYA:
                alt_dizinler[:] = []
                break

            # Atlanacak/gizli klasörleri daldan kes (os.walk'a girmeden)
            alt_dizinler[:] = [d for d in alt_dizinler
                               if d.lower() not in ATLANAN_KLASORLER and not d.startswith('.')]

            for ad in dosyalar:
                if ad.startswith('~$') or ad.startswith('.'):
                    continue
                uzanti = os.path.splitext(ad)[1].lower()
                if uzanti in ATLANAN_UZANTILAR:
                    continue
                if gizli_mi(ad):
                    gizli_atlanan += 1
                    continue
                tam = os.path.join(dizin, ad)
                try:
                    st = os.stat(tam)
                except OSError:
                    continue
                kayitlar.append((tam, ad, sadelestir(ad), uzanti,
                                 os.path.basename(dizin), etiket, st.st_size, st.st_mtime))

            if ilerleme_cb and len(kayitlar) % 2000 < 50:
                ilerleme_cb(len(kayitlar))

    conn = _baglanti()
    try:
        conn.execute("DELETE FROM dosyalar")
        conn.executemany(
            "INSERT OR REPLACE INTO dosyalar "
            "(yol, ad, ad_sade, uzanti, klasor, kok, boyut, degisim) "
            "VALUES (?,?,?,?,?,?,?,?)", kayitlar)
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('son_tarama', ?)",
                     (datetime.now().isoformat(timespec='seconds'),))
        conn.commit()
    finally:
        conn.close()

    return len(kayitlar), round(time.time() - baslangic, 1), gizli_atlanan


def indeks_durumu():
    """(dosya_sayisi, son_tarama_zamani) — indeks hiç kurulmadıysa (0, None)."""
    if not os.path.exists(INDEX_DB):
        return 0, None
    conn = _baglanti()
    try:
        sayi = conn.execute("SELECT COUNT(*) FROM dosyalar").fetchone()[0]
        row = conn.execute("SELECT deger FROM meta WHERE anahtar='son_tarama'").fetchone()
        return sayi, (row[0] if row else None)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ARAMA
# ---------------------------------------------------------------------------
def _arama_kosullari(sorgu: str, tur: str = None):
    """Sorguyu SQL koşullarına çevirir → (kosullar, parametreler) veya (None, None)."""
    tokenlar = [t for t in re.findall(r"[\w\-.]+", sadelestir(sorgu)) if len(t) >= 2]
    if not tokenlar and not tur:
        return None, None, []

    kosullar, parametreler = [], []
    for t in tokenlar:
        kosullar.append("ad_sade LIKE ?")
        parametreler.append(f"%{t}%")

    if tur:
        uzantilar = TUR_UZANTILARI.get(tur)
        if not uzantilar and tur.startswith('.'):
            uzantilar = [tur]
        if uzantilar:
            kosullar.append("uzanti IN (%s)" % ','.join('?' * len(uzantilar)))
            parametreler.extend(uzantilar)

    if not kosullar:
        return None, None, []
    return kosullar, parametreler, tokenlar


def sonuc_sayisi(sorgu: str, tur: str = None) -> int:
    """
    Eşleşen TOPLAM dosya sayısı.

    Neden ayrı fonksiyon: `ara()` limitli döner ve kullanıcıya "10 sonuç" demek
    yanıltıcıydı — aslında 23 eşleşme varken 13'ünün varlığı gizleniyordu.
    """
    sayi, _ = indeks_durumu()
    if not sayi:
        return 0
    kosullar, parametreler, _tok = _arama_kosullari(sorgu, tur)
    if not kosullar:
        return 0
    sql = "SELECT COUNT(*) FROM dosyalar WHERE " + " AND ".join(kosullar)
    conn = _baglanti()
    try:
        return conn.execute(sql, parametreler).fetchone()[0]
    finally:
        conn.close()


def ara(sorgu: str, tur: str = None, limit: int = 20, offset: int = 0):
    """
    İndekste arar → [{'yol','ad','boyut','degisim','kok'}] (en alakalı önce).

    Sorgudaki her kelime dosya adında geçmelidir (AND). Sıralama:
      1) adın tam başında eşleşme  2) yeni değişen  3) alfabetik

    `offset`: sayfalama için atlanacak sonuç sayısı ("devamını göster").
    """
    sayi, _ = indeks_durumu()
    if not sayi:
        return []

    kosullar, parametreler, tokenlar = _arama_kosullari(sorgu, tur)
    if not kosullar:
        return []

    sql = ("SELECT yol, ad, boyut, degisim, kok FROM dosyalar WHERE "
           + " AND ".join(kosullar) + " ORDER BY degisim DESC LIMIT ? OFFSET ?")
    parametreler = list(parametreler)
    parametreler.append(max(1, min(limit, 50)))
    parametreler.append(max(0, offset))

    conn = _baglanti()
    try:
        satirlar = conn.execute(sql, parametreler).fetchall()
    finally:
        conn.close()

    ilk_token = tokenlar[0] if tokenlar else ''

    def _puan(satir):
        ad_sade = sadelestir(satir[1])
        return (0 if ilk_token and ad_sade.startswith(ilk_token) else 1, -satir[3])

    satirlar.sort(key=_puan)
    return [{'yol': y, 'ad': a, 'boyut': b, 'degisim': d, 'kok': k}
            for y, a, b, d, k in satirlar]


def dosya_gecerli_mi(yol: str) -> bool:
    """Gönderim öncesi son kontrol: dosya hâlâ var mı ve gizli değil mi?"""
    if not yol or not os.path.isfile(yol):
        return False
    return not gizli_mi(os.path.basename(yol))


# ---------------------------------------------------------------------------
# SON ARAMA SONUÇLARI — "2'yi gönder" diyebilmek için
# ---------------------------------------------------------------------------
# Kanal başına ayrı tutulur: 'desktop' veya Telegram chat_id.
# Süreç içi bellek (kalıcı olmamalı — eski liste yanlış dosya göndermesin).
_SON_SONUCLAR = {}
_SONUC_OMRU_SN = 900   # 15 dakika


def son_sonuclari_kaydet(kanal, sonuclar, sorgu=None, tur=None, offset=0,
                         toplam=None, daraltma_bekliyor=False):
    """
    Son arama sonuçlarını kanal başına saklar.

    Sorgu/offset/toplam da saklanır ki "devamını göster" sonraki sayfayı
    çekebilsin ve "11'i gönder" ikinci sayfada doğru dosyayı seçebilsin.

    `daraltma_bekliyor`: kullanıcıya "hangisi?" diye soruldu mu. Sorulduysa
    bir sonraki kısa mesaj arama terimi olarak denenir.
    """
    _SON_SONUCLAR[str(kanal)] = {
        'sonuclar': list(sonuclar),
        'zaman': time.time(),
        'sorgu': sorgu,
        'tur': tur,
        'offset': offset,
        'toplam': toplam if toplam is not None else offset + len(sonuclar),
        'daraltma_bekliyor': daraltma_bekliyor,
    }


def daraltma_bayragini_dusur(kanal):
    """
    Daraltma bir kez denenir.

    Bayrak düşmezse konuşma boyunca her kısa cümle arama terimi sanılır —
    kullanıcı "tamam" dediğinde Ultron dosya aramaya kalkar.
    """
    kayit = _SON_SONUCLAR.get(str(kanal))
    if kayit:
        kayit['daraltma_bekliyor'] = False


def son_arama_bilgisi(kanal):
    """Taze arama kaydını döner; bayatsa temizler ve None döner."""
    kayit = _SON_SONUCLAR.get(str(kanal))
    if not kayit:
        return None
    if time.time() - kayit['zaman'] > _SONUC_OMRU_SN:
        _SON_SONUCLAR.pop(str(kanal), None)
        return None
    return kayit


def son_sonuclari_al(kanal):
    kayit = son_arama_bilgisi(kanal)
    return kayit['sonuclar'] if kayit else []


def sonuctan_sec(kanal, sira: int):
    """
    1 tabanlı sıra numarasıyla son arama sonucundan dosya seçer → yol veya None.

    Numaralar GENEL sıradır: ikinci sayfa 11'den başlar, o yüzden saklanan
    `offset` düşülür. (Aksi halde "11'i gönder" ikinci sayfada listenin 11.
    elemanını arar ve bulamaz.)
    """
    kayit = son_arama_bilgisi(kanal)
    if not kayit:
        return None
    yerel = sira - 1 - kayit.get('offset', 0)
    sonuclar = kayit['sonuclar']
    if yerel < 0 or yerel >= len(sonuclar):
        return None
    return sonuclar[yerel]['yol']


# ---------------------------------------------------------------------------
# BİÇİMLENDİRME
# ---------------------------------------------------------------------------
def boyut_yazi(bayt: int) -> str:
    mb = (bayt or 0) / (1024 * 1024)
    return f"{mb:.1f} MB" if mb >= 1 else f"{(bayt or 0) / 1024:.0f} KB"


def sonuclari_bicimle(sonuclar, baslik: str = "Bulunanlar", toplam: int = None,
                      baslangic: int = 1) -> str:
    """
    Numaralı liste — kullanıcı '2'yi gönder' diyebilsin.

    `toplam`: eşleşen TÜM dosyaların sayısı. Verilmezse gösterilen kadar sanılır.
    Bu ayrım önemli: önceden 23 eşleşme varken "10 sonuç" yazıyordu ve kalan
    13 dosyanın varlığı kullanıcıdan gizleniyordu.

    `baslangic`: numaralandırmanın başlayacağı sıra (2. sayfada 11'den başlar).
    """
    if not sonuclar:
        return "🔍 Eşleşen dosya bulunamadı."

    satirlar = []
    for i, s in enumerate(sonuclar, baslangic):
        tarih = datetime.fromtimestamp(s['degisim']).strftime('%d.%m.%Y %H:%M')
        klasor = os.path.dirname(s['yol'])
        satirlar.append(f"**{i}.** `{s['ad']}`\n     {boyut_yazi(s['boyut'])} · {tarih}\n     📁 {klasor}")

    gosterilen = len(sonuclar)
    son = baslangic + gosterilen - 1
    toplam = toplam if toplam is not None else son

    if toplam > son:
        basligi = f"🔍 **{baslik}** — {toplam} dosya bulundu, {baslangic}-{son} arası:"
        kuyruk = (f"\n\n➡️ `{baslangic}'i bana gönder` · `{baslangic + 1}'i anneme mail at`"
                  f"\n📄 Kalan {toplam - son} dosya için: `devamını göster`"
                  f"\n❓ **Hangisi?** Adından bir parça yazman yeter (`haftalık` gibi) —"
                  f" aramayı ona göre daraltırım.")
    else:
        sayi_yazi = f"{toplam} sonuç" if baslangic == 1 else f"{baslangic}-{son} arası (son sayfa)"
        basligi = f"🔍 **{baslik}** ({sayi_yazi}):"
        kuyruk = f"\n\n➡️ Göndermek için: `{baslangic}'i bana gönder` · `{baslangic + 1}'i anneme mail at`"

    return basligi + "\n\n" + "\n".join(satirlar) + kuyruk
