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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DB = os.path.join(_ROOT, 'file_index.db')

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
def ara(sorgu: str, tur: str = None, limit: int = 20):
    """
    İndekste arar → [{'yol','ad','boyut','degisim','kok'}] (en alakalı önce).

    Sorgudaki her kelime dosya adında geçmelidir (AND). Sıralama:
      1) adın tam başında eşleşme  2) yeni değişen  3) alfabetik
    """
    sayi, _ = indeks_durumu()
    if not sayi:
        return []

    tokenlar = [t for t in re.findall(r"[\w\-.]+", sadelestir(sorgu)) if len(t) >= 2]
    if not tokenlar and not tur:
        return []

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
        return []

    sql = ("SELECT yol, ad, boyut, degisim, kok FROM dosyalar WHERE "
           + " AND ".join(kosullar) + " ORDER BY degisim DESC LIMIT ?")
    parametreler.append(max(1, min(limit, 50)))

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


def son_sonuclari_kaydet(kanal, sonuclar):
    _SON_SONUCLAR[str(kanal)] = (list(sonuclar), time.time())


def son_sonuclari_al(kanal):
    kayit = _SON_SONUCLAR.get(str(kanal))
    if not kayit:
        return []
    sonuclar, zaman = kayit
    if time.time() - zaman > _SONUC_OMRU_SN:
        _SON_SONUCLAR.pop(str(kanal), None)
        return []
    return sonuclar


def sonuctan_sec(kanal, sira: int):
    """1 tabanlı sıra numarasıyla son arama sonucundan dosya seçer → yol veya None."""
    sonuclar = son_sonuclari_al(kanal)
    if not sonuclar or sira < 1 or sira > len(sonuclar):
        return None
    return sonuclar[sira - 1]['yol']


# ---------------------------------------------------------------------------
# BİÇİMLENDİRME
# ---------------------------------------------------------------------------
def boyut_yazi(bayt: int) -> str:
    mb = (bayt or 0) / (1024 * 1024)
    return f"{mb:.1f} MB" if mb >= 1 else f"{(bayt or 0) / 1024:.0f} KB"


def sonuclari_bicimle(sonuclar, baslik: str = "Bulunanlar") -> str:
    """Numaralı liste — kullanıcı '2'yi gönder' diyebilsin."""
    if not sonuclar:
        return "🔍 Eşleşen dosya bulunamadı."
    satirlar = []
    for i, s in enumerate(sonuclar, 1):
        tarih = datetime.fromtimestamp(s['degisim']).strftime('%d.%m.%Y %H:%M')
        klasor = os.path.dirname(s['yol'])
        satirlar.append(f"**{i}.** `{s['ad']}`\n     {boyut_yazi(s['boyut'])} · {tarih}\n     📁 {klasor}")
    return (f"🔍 **{baslik}** ({len(sonuclar)} sonuç):\n\n" + "\n".join(satirlar) +
            "\n\n➡️ Göndermek için: `1'i bana gönder` · `2'yi anneme mail at`")
