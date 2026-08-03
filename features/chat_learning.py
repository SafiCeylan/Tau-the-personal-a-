# -*- coding: utf-8 -*-
"""
ULTRON ÖĞRENME KATMANI — geçmiş sohbetlerden GERÇEKTEN öğrenir.

NEDEN VAR
    Ultron'un hafızası üç parçaydı ve üçü de kısa ömürlüydü:
      • `memory` tablosu → sadece kullanıcının AÇIKÇA öğrettiği bilgiler
      • `recent_context` → son 6 mesaj (pencere kapanınca uçar)
      • `sohbet_gecmisi` → 300+ konuşma kayıtlı ama HİÇBİR YERDE okunmuyordu
    Yani Ultron her açılışta hafızasını kaybediyordu: dün cevapladığı soruyu
    bugün ilk kez duyuyormuş gibi karşılıyordu.

NE YAPAR — üç sütun
    1. EPİZODİK GERİ ÇAĞIRMA
       Yeni mesaja EN ALAKALI geçmiş konuşmalar FTS5 + BM25 ile bulunup
       prompt'a girer. Artık "geçen sefer ne konuşmuştuk" cevaplanabilir.
    2. ÖRÜNTÜ ÇIKARIMI
       Hangi komut ne sıklıkla, hangi saatte, kiminle, hangi uygulamayla…
       Saf SQL toplaması — LLM yok, dolayısıyla uydurma da yok.
    3. DÜZELTMEDEN ÖĞRENME
       Anlaşılmayan bir cümlenin hemen ardından kullanıcı aynı şeyi başka
       türlü söyleyip BAŞARDIYSA, eski cümle o niyete bağlanır. Regex'in
       kaçırdığı ifadeler kullanıldıkça kendini kapatır.

TASARIM KURALLARI — bunları bozma
    • Öğrenme AKIŞI ASLA KIRMAZ. Her public fonksiyon kendi hatasını yutar;
      öğrenme bir iyileştirmedir, tek nokta arıza değil.
    • SIR ÖĞRENİLMEZ. PIN/şifre/token geçen mesaj arşive HİÇ girmez. Bu
      kayıtlar prompt'a ve oradan Telegram'a geri dönüyor — sızıntı yolu budur.
      (`level4_input.pin_maskele` aynı gerekçeyle yazılmıştı.)
    • ÖĞRENİLEN KALIP SESSİZ UYGULANMAZ. Kullanıcı ne öğrenildiğini görür
      ("ne öğrendin") ve silebilir ("şunu unut: ..."). Sessiz öğrenme, bir
      gün yanlış komutun sessizce çalışması demektir.
    • MESAJ GÖNDEREN NİYETLER ÖĞRENİLMEZ (`OGRENILEBILIR_INTENTLER`).
      Yanlış öğrenilmiş bir kalıp yanlış kişiye mesaj göndermektir — telafisi
      yoktur. Aynı gerekçe `core/aliases.py`'deki bulanık eşleşme yasağında da var.
    • AYRI VERİTABANI (`ogrenme.db`). Ana `bilgiler.db` kilitlenmesin, FTS
      indeksi onu şişirmesin. (`file_index.db` ile aynı gerekçe.)
    • Her çağrı KENDİ bağlantısını açar — SQLite thread'ler arasında paylaşılamaz.

VERİMLİLİK
    • Arama FTS5 + BM25 üzerinden → tam tarama yok.
    • Örüntüler 10 dakika süreyle süreç içinde önbelleklenir; yeni kayıt
      geldiğinde önbellek düşer.
    • Geçmiş arşivi `sohbet_gecmisi`den ARTIMLI kopyalanır (son id işareti).
"""

import os
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

from core.paths import veri_yolu

DB_ADI = 'ogrenme.db'

# ---------------------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------------------
MIN_GOZLEM_KALIP = 2          # bir kalıp kaç gözlemde aktifleşir
KALIP_ESIK = 0.85             # öğrenilmiş kalıp eşleşme eşiği (0-1)
DUZELTME_PENCERESI_SN = 300   # düzeltme sayılan azami süre (5 dk)
DUZELTME_KAPSAMA = 0.5        # düzeltme sayılması için asgari kelime kapsaması
ORUNTU_TAZELIK_SN = 600       # örüntü önbelleği ömrü
MIN_ORUNTU_GOZLEM = 3         # bir örüntünün rapora girmesi için asgari gözlem
RECALL_ADAY = 40              # FTS'ten çekilip yeniden puanlanan aday sayısı
MAKS_METIN = 2000             # arşive yazılan azami karakter

# Öğrenilmiş kalıba BAĞLANABİLECEK niyetler.
# Listede OLMAYANLAR bilinçli dışarıda: WHATSAPP_MESSAGE / EMAIL_MESSAGE /
# FILE_TRANSFER alıcıya iş yapar (geri alınamaz), KEYBOARD_INPUT aktif
# pencereye tuş basar, CREATE_REMINDER / SCHEDULE_TASK cümlenin içeriğini
# ayrıştırır — yanlış eşleşme çöp kayıt üretir.
OGRENILEBILIR_INTENTLER = {
    'PLAY_MUSIC', 'MEDIA_CONTROL', 'SYSTEM_CONTROL', 'SET_VOLUME',
    'WEATHER', 'CURRENCY', 'WEB_SEARCH', 'TIME_DATE', 'CALCULATOR',
    'NOTE_TAKE', 'TIMER', 'SCREENSHOT', 'CLIPBOARD', 'FOCUS_MODE',
    'MORNING_BRIEFING', 'EVENING_REPORT', 'FILE_SEARCH', 'ANALYSIS_REPORT',
}

# Sır taşıyan mesajlar hiç öğrenilmez. Kalıplar SADELEŞTİRİLMİŞ metin
# üzerinde çalışır → hepsi ASCII yazılmalı (proje tuzağı: "şifre" yazarsan
# "sifre" ile eşleşmez).
SIR_KALIPLARI = (
    'sifre', 'parola', 'password', 'pin ', 'pin:', 'pini', 'pinim',
    'token', 'api key', 'apikey', 'api_key', 'gizli kod', 'kart numaras',
    'cvv', 'iban', 'kullanici adi ve', 'secret', 'credential',
)

# Tek başına anlamı olmayan kontrol kelimeleri — ne aranır ne örüntüye girer
KONTROL_KELIMELERI = {
    'evet', 'hayir', 'tamam', 'olur', 'iptal', 'dur', 'sus', 'devam',
    'yap', 'yapma', 'onayla', 'vazgec', 'ok', 'peki', 'e', 'hmm',
}

# Sadeleştirilmiş (ASCII) durak kelimeler
_STOPWORDS = {
    've', 'ile', 'bir', 'bu', 'su', 'da', 'de', 'ki', 'mi', 'mu', 'mus',
    'icin', 'gibi', 'ama', 'cok', 'ne', 'nasil', 'neden', 'kim', 'nedir',
    'kac', 'ben', 'sen', 'biz', 'siz', 'onlar', 'benim', 'senin', 'var',
    'yok', 'the', 'bana', 'sana', 'bir', 'daha', 'lutfen', 'misin', 'musun',
}

# ---------------------------------------------------------------------------
# TÜRKÇE SADELEŞTİRME
# `file_index.sadelestir` ile aynı tablo — tek kaynak olsun diye oradan alınır,
# import edilemezse (izole test) yerel kopyaya düşülür.
# ---------------------------------------------------------------------------
try:                                                    # pragma: no cover
    from features.file_index import sadelestir as _sadelestir_ham
except Exception:                                       # pragma: no cover
    _TR_HARITA = str.maketrans('çğıöşüâîûÇĞİÖŞÜ', 'cgiosuaiucgiosu')

    def _sadelestir_ham(metin: str) -> str:
        return (metin or '').lower().translate(_TR_HARITA)


# Telegram köprüsü mesajların başına "[Telegram] " ekler. Bu bir KANAL
# etiketidir, komutun parçası değil — temizlenmezse:
#   • aynı komut iki ayrı komut sayılır ("ekran görüntüsü" vs "[Telegram] ekran…")
#   • "telegram" kelimesi en sık konuşulan konu gibi görünür (gerçek ölçümde 66 kez)
#   • telefonda öğrenilen kalıp masaüstünde eşleşmez
_KANAL_ONEKI = re.compile(r'^\s*\[[^\]]{1,20}\]\s*')


def sadelestir(metin: str) -> str:
    """
    Karşılaştırılabilir ASCII metin (kanal etiketi atılmış).

    NOT: 'İ'.lower() Python'da 'i' + U+0307 (birleşen nokta) üretir; nokta
    haritada olmadığı için elde kalır ve eşleşmeyi bozar. Burada temizlenir.
    """
    return _sadelestir_ham(_KANAL_ONEKI.sub('', metin or '')).replace('̇', '')


def kanalsiz(metin: str) -> str:
    """
    Kanal etiketini ('[Telegram] ') atar ama Türkçe harfleri KORUR.

    `sadelestir` de öneki atar, ama ASCII'ye indirger — ekrana basılacak ya da
    komut olarak geri oynatılacak metin için kullanılamaz. Ham `kullanici`
    sütununda önek DURUYOR: canlı testte rapora ve öneriye
    "[Telegram] Ekran görüntüsü" diye sızdı; kabul edilseydi hiçbir niyete
    eşleşmeyen bir kısayol kurulacaktı.
    """
    return _KANAL_ONEKI.sub('', metin or '').strip()


def _tokenlar(metin: str):
    """Sadeleştirilmiş metni anlamlı kelimelere böler."""
    kelimeler = re.findall(r'\w+', sadelestir(metin))
    return [k for k in kelimeler if k not in _STOPWORDS and len(k) >= 3]


def _ortaklik(a: str, b: str) -> float:
    """
    İki cümlenin kelime örtüşmesi (Jaccard, 0-1).

    "Neredeyse aynı cümle mi?" sorusu için kullanılır (kalıp eşleşmesi) —
    uzunluk farkını cezalandırır, bu yüzden bilerek katıdır.
    """
    ta, tb = set(_tokenlar(a)), set(_tokenlar(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _kapsama(a: str, b: str) -> float:
    """
    KISA cümlenin kelimelerinin ne kadarı diğerinde geçiyor (0-1).

    Neden Jaccard değil: düzeltme cümleleri KISALIR. "biraz kısar mısın sesi"
    → "sesi kıs" örneğinde Jaccard 0.25 verip düzeltmeyi kaçırıyordu; oysa
    kısa cümlenin kelimelerinin yarısı diğerinde geçiyor. Aynı şeyden
    bahsedildiğini ölçen doğru araç bu.
    """
    ta, tb = set(_tokenlar(a)), set(_tokenlar(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def ogrenilebilir_mi(metin: str) -> bool:
    """
    Bu mesaj arşive girebilir mi?

    Reddedilenler: boş/çok kısa metinler, kontrol kelimeleri ("evet", "sus")
    ve SIR taşıyan cümleler. Sır filtresi zayıflatılmamalı — arşiv prompt'a,
    prompt da Telegram'a dönüyor.
    """
    if not metin:
        return False
    sade = sadelestir(metin).strip()
    if len(sade) < 3:
        return False
    if sade in KONTROL_KELIMELERI:
        return False
    return not any(k in sade for k in SIR_KALIPLARI)


# ---------------------------------------------------------------------------
# VERİTABANI
# ---------------------------------------------------------------------------
_fts_destegi = None      # None = henüz denenmedi


def _db_yolu() -> str:
    """Testler bu fonksiyonu yamalar — modül sabiti KULLANMA."""
    return veri_yolu(DB_ADI)


def _baglanti():
    """Şemayı garanti eden yeni bağlantı (her çağrı kendi bağlantısını açar)."""
    global _fts_destegi
    conn = sqlite3.connect(_db_yolu(), timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS konusma (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            kaynak_id INTEGER,              -- sohbet_gecmisi.id (geçmiş göçü için)
            kanal     TEXT DEFAULT 'desktop',
            kullanici TEXT NOT NULL,
            ultron    TEXT,
            sade      TEXT NOT NULL,
            intent    TEXT,
            basarili  INTEGER DEFAULT 0,
            kaynak    TEXT DEFAULT 'canli', -- 'canli' | 'gecmis'
            tarih     TEXT NOT NULL,
            saat      INTEGER,
            gun       INTEGER
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_kaynak_id "
                 "ON konusma(kaynak_id) WHERE kaynak_id IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_konusma_tarih ON konusma(tarih)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_konusma_intent ON konusma(intent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_konusma_sade ON konusma(sade)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS etiket (
            konusma_id INTEGER NOT NULL,
            tip        TEXT NOT NULL,       -- 'kisi' | 'uygulama' | ...
            deger      TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_etiket ON etiket(tip, deger)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kalip (
            sade    TEXT PRIMARY KEY,       -- öğrenilen ifade (sadeleştirilmiş)
            intent  TEXT NOT NULL,
            gozlem  INTEGER DEFAULT 1,
            aktif   INTEGER DEFAULT 0,
            ornek   TEXT,                   -- kullanıcının orijinal cümlesi
            ilk     TEXT,
            son     TEXT
        )
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS meta (anahtar TEXT PRIMARY KEY, deger TEXT)")

    # Sonradan eklenen sütunlar. CREATE TABLE yalnızca YENİ dosyada çalışır;
    # kullanıcının dolu arşivi zaten var olduğu için şema burada tamamlanır.
    # (PRAGMA ucuzdur — zaten her bağlantıda birkaç CREATE IF NOT EXISTS koşuyor.)
    try:
        sutunlar = {satir[1] for satir in conn.execute("PRAGMA table_info(konusma)")}
        if 'ruh_hali' not in sutunlar:
            conn.execute("ALTER TABLE konusma ADD COLUMN ruh_hali TEXT")
    except sqlite3.Error as e:
        print(f"[ULTRON Ogrenme] Sema tamamlanamadi: {e}")

    if _fts_destegi is not False:
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS konusma_fts "
                         "USING fts5(sade, tokenize='unicode61')")
            _fts_destegi = True
        except sqlite3.Error:
            # FTS5 olmayan bir SQLite derlemesi — LIKE tabanlı yedek yola düşülür
            _fts_destegi = False
    return conn


@contextmanager
def _acik():
    """
    Bağlantıyı açar, çıkışta commit + KAPATIR.

    `with sqlite3.connect(...)` yalnızca commit eder, bağlantıyı KAPATMAZ —
    Ultron uzun süre açık kalan bir uygulama; her mesajda bir bağlantı sızarsa
    dosya tanıtıcıları birikir.
    """
    conn = _baglanti()
    try:
        yield conn
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _meta_al(conn, anahtar, varsayilan=None):
    satir = conn.execute("SELECT deger FROM meta WHERE anahtar = ?", (anahtar,)).fetchone()
    return satir[0] if satir else varsayilan


def _meta_yaz(conn, anahtar, deger):
    conn.execute("INSERT INTO meta (anahtar, deger) VALUES (?, ?) "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger",
                 (anahtar, str(deger)))


# ---------------------------------------------------------------------------
# KAYIT — canlı akıştan öğrenme
# ---------------------------------------------------------------------------
# Kanal başına son tur (düzeltme tespiti için). Kalıcı değil: düzeltme ancak
# aynı oturumda, dakikalar içinde anlamlıdır.
_SON_TUR = {}


def kaydet(kullanici: str, ultron: str = "", intent: str = None,
           basarili: bool = False, kanal: str = "desktop",
           etiketler: dict = None, ruh_hali: str = None) -> int:
    """
    Bir konuşma turunu arşive yazar ve düzeltme öğrenmesini çalıştırır.

    `ruh_hali`: o turda ölçülen duygu ('pozitif'/'negatif'/'nötr'). Yalnızca
    gerçek sohbette ölçülür — komut cümlesinin duygusu yoktur. Ayrı bir tablo
    yerine turun YANINDA durur; "ne zaman/neyden bahsederken" sorusu ancak
    aynı satırda saat ve metinle birlikte cevaplanabilir.

    Dönüş: yeni kayıt id'si (yazılmadıysa 0). Hiçbir durumda istisna fırlatmaz.
    """
    try:
        if not ogrenilebilir_mi(kullanici):
            return 0
        sade = sadelestir(kullanici).strip()
        simdi = datetime.now()
        with _acik() as conn:
            imlec = conn.execute(
                "INSERT INTO konusma (kanal, kullanici, ultron, sade, intent, "
                "basarili, kaynak, tarih, saat, gun, ruh_hali) "
                "VALUES (?,?,?,?,?,?,'canli',?,?,?,?)",
                (kanal, (kullanici or '')[:MAKS_METIN], (ultron or '')[:MAKS_METIN],
                 sade, intent, 1 if basarili else 0,
                 simdi.strftime('%Y-%m-%d %H:%M:%S'), simdi.hour, simdi.weekday(),
                 (ruh_hali or None)))
            yeni_id = imlec.lastrowid
            _fts_ekle(conn, yeni_id, sade)
            for tip, deger in (etiketler or {}).items():
                if deger:
                    conn.execute("INSERT INTO etiket (konusma_id, tip, deger) VALUES (?,?,?)",
                                 (yeni_id, tip, str(deger).strip().lower()[:100]))
            _duzeltmeden_ogren(conn, kanal, kullanici, sade, intent, basarili)
            conn.commit()
        _SON_TUR[kanal] = {'sade': sade, 'metin': kullanici, 'intent': intent,
                           'basarili': bool(basarili), 'zaman': time.time()}
        _onbellegi_dusur()
        return yeni_id
    except Exception as e:
        print(f"[ULTRON Ogrenme] Kayit yazilamadi: {e}")
        return 0


def cevabi_tamamla(kanal: str, kullanici: str, cevap: str) -> None:
    """
    Cevabı sonradan yazar.

    Masaüstünde cevap STREAMING ile üretilir: engine kaydı açtığında Ultron'un
    ne söyleyeceği HENÜZ BELLİ DEĞİLDİR. Arayüz cevabı loglarken burayı çağırır;
    aynı kanaldaki en son eşleşen kayıt tamamlanır.
    """
    try:
        if not cevap or not ogrenilebilir_mi(kullanici):
            return
        sade = sadelestir(kullanici).strip()
        with _acik() as conn:
            satir = conn.execute(
                "SELECT id FROM konusma WHERE kanal = ? AND sade = ? "
                "ORDER BY id DESC LIMIT 1", (kanal, sade)).fetchone()
            if satir:
                conn.execute("UPDATE konusma SET ultron = ? WHERE id = ?",
                             (cevap[:MAKS_METIN], satir[0]))
                conn.commit()
    except Exception as e:
        print(f"[ULTRON Ogrenme] Cevap tamamlanamadi: {e}")


def _fts_ekle(conn, satir_id: int, sade: str) -> None:
    if _fts_destegi:
        try:
            conn.execute("INSERT INTO konusma_fts (rowid, sade) VALUES (?, ?)",
                         (satir_id, sade))
        except sqlite3.Error as e:
            print(f"[ULTRON Ogrenme] FTS yazilamadi: {e}")


# ---------------------------------------------------------------------------
# GEÇMİŞ GÖÇÜ — `sohbet_gecmisi` arşive alınır (artımlı)
# ---------------------------------------------------------------------------
def gecmisi_iceri_al(ana_db_yolu: str, limit: int = 20000) -> int:
    """
    Ana veritabanındaki `sohbet_gecmisi` kayıtlarını arşive kopyalar.

    Artımlıdır: son işlenen id `meta`da tutulur, ikinci çağrıda yalnızca yeni
    satırlar okunur. Bu yüzden her açılışta çağrılabilir.

    Dönüş: içeri alınan satır sayısı.
    """
    try:
        if not ana_db_yolu or not os.path.exists(ana_db_yolu):
            return 0
        with _acik() as conn:
            son_id = int(_meta_al(conn, 'gecmis_son_id', '0') or 0)
            kaynak = sqlite3.connect(f"file:{ana_db_yolu}?mode=ro", uri=True, timeout=10)
            try:
                satirlar = kaynak.execute(
                    "SELECT id, kullanici_girisi, sistem_cevabi, tarih FROM sohbet_gecmisi "
                    "WHERE id > ? ORDER BY id LIMIT ?", (son_id, limit)).fetchall()
            finally:
                kaynak.close()

            niyet_coz = _niyet_tahmincisi()
            eklenen = 0
            for kid, soru, cevap, tarih in satirlar:
                son_id = max(son_id, kid)
                if not ogrenilebilir_mi(soru):
                    continue
                sade = sadelestir(soru).strip()
                saat, gun = _tarih_parcala(tarih)
                # Geçmiş satırların niyeti kayıtlı değil — bugünkü regex zinciriyle
                # tahmin edilir. Böylece "en sık komutların" ilk günden çalışır.
                intent = niyet_coz(soru) if niyet_coz else None
                basarili = 0 if (intent in (None, 'GENERAL_CONVERSATION')
                                 or _basarisiz_cevap_mi(cevap)) else 1
                try:
                    imlec = conn.execute(
                        "INSERT OR IGNORE INTO konusma (kaynak_id, kanal, kullanici, "
                        "ultron, sade, intent, basarili, kaynak, tarih, saat, gun) "
                        "VALUES (?, 'desktop', ?, ?, ?, ?, ?, 'gecmis', ?, ?, ?)",
                        (kid, (soru or '')[:MAKS_METIN], (cevap or '')[:MAKS_METIN],
                         sade, intent, basarili, tarih, saat, gun))
                except sqlite3.Error:
                    continue
                if imlec.rowcount:
                    _fts_ekle(conn, imlec.lastrowid, sade)
                    eklenen += 1
            _meta_yaz(conn, 'gecmis_son_id', son_id)
            conn.commit()
        if eklenen:
            _onbellegi_dusur()
            print(f"[ULTRON Ogrenme] Gecmis arsive alindi: {eklenen} konusma")
        return eklenen
    except Exception as e:
        print(f"[ULTRON Ogrenme] Gecmis okunamadi: {e}")
        return 0


# Geçmiş satırın BAŞARISIZ olduğunu ele veren cevap izleri (sadeleştirilmiş).
# Kesin bilgi değil, sezgidir: eski kayıtlarda başarı alanı tutulmuyordu.
# Yanlış tarafa düşmesi hâlinde en fazla bir örüntü eksik/fazla sayılır —
# bu yüzden temkinli davranıp şüpheliyi BAŞARISIZ sayıyoruz.
_BASARISIZ_IZLERI = (
    'anlayamadim', 'anlamadim', 'bulunamadi', 'uretilemedi', 'basarisiz',
    'yanit alinamadi', 'desteklenmiyor', 'hata:', 'gerceklestiremedim',
    'yapamiyorum', 'bir sorun olustu',
)


def _basarisiz_cevap_mi(cevap: str) -> bool:
    if not cevap:
        return True
    sade = sadelestir(cevap)
    if '⚠️' in cevap or '❌' in cevap:
        return True
    return any(iz in sade for iz in _BASARISIZ_IZLERI)


def _niyet_tahmincisi():
    """
    Geçmiş satırları sınıflandıracak regex zincirini getirir.

    TEMBEL import: `pipeline_layers` bu modülü import ediyor (öğrenme komutu
    algılama) — modül seviyesinde import edersek döngü olur.
    """
    try:
        from core.layers.pipeline_layers import arsiv_niyeti_tahmin_et
        return arsiv_niyeti_tahmin_et
    except Exception as e:
        print(f"[ULTRON Ogrenme] Niyet tahmincisi yuklenemedi: {e}")
        return None


def _tarih_parcala(tarih: str):
    """'YYYY-MM-DD HH:MM:SS' → (saat, haftanın günü). Çözülemezse (None, None)."""
    try:
        d = datetime.strptime(str(tarih)[:19], '%Y-%m-%d %H:%M:%S')
        return d.hour, d.weekday()
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# 1. SÜTUN — EPİZODİK GERİ ÇAĞIRMA
# ---------------------------------------------------------------------------
def alakali_konusmalar(mesaj: str, k: int = 3, kanal: str = None) -> list:
    """
    Mesaja en alakalı geçmiş konuşmaları döner.

    Dönüş: [{'soru','cevap','tarih','skor'}] — alakalı yoksa boş liste.
    Boş liste DÖNMEK serbesttir; "en yenileri" doldurmak yanlış olur:
    alakasız geçmişi prompt'a koymak modeli yanıltır.
    """
    try:
        tokenlar = _tokenlar(mesaj)
        if not tokenlar:
            return []
        with _acik() as conn:
            adaylar = _fts_adaylari(conn, tokenlar) if _fts_destegi \
                else _like_adaylari(conn, tokenlar)
        return _adaylari_puanla(adaylar, mesaj, k)
    except Exception as e:
        print(f"[ULTRON Ogrenme] Gecmis aranamadi: {e}")
        return []


def _fts_adaylari(conn, tokenlar) -> list:
    """FTS5 + BM25 ile aday çeker. Sorgu OR'lanmış tırnaklı kelimelerdir."""
    sorgu = " OR ".join(f'"{t}"' for t in tokenlar[:12])
    try:
        return conn.execute(
            "SELECT k.kullanici, k.ultron, k.tarih, bm25(konusma_fts) "
            "FROM konusma_fts f JOIN konusma k ON k.id = f.rowid "
            "WHERE konusma_fts MATCH ? ORDER BY bm25(konusma_fts) LIMIT ?",
            (sorgu, RECALL_ADAY)).fetchall()
    except sqlite3.Error as e:
        print(f"[ULTRON Ogrenme] FTS sorgusu basarisiz, yedek yola dusuluyor: {e}")
        return _like_adaylari(conn, tokenlar)


def _like_adaylari(conn, tokenlar) -> list:
    """FTS yoksa: en uzun 3 kelimeyle LIKE taraması (son 3000 kayıt)."""
    kosullar, degerler = [], []
    for t in sorted(tokenlar, key=len, reverse=True)[:3]:
        kosullar.append("sade LIKE ?")
        degerler.append(f"%{t}%")
    if not kosullar:
        return []
    sql = ("SELECT kullanici, ultron, tarih, 0 FROM konusma WHERE (" +
           " OR ".join(kosullar) + ") ORDER BY id DESC LIMIT ?")
    return conn.execute(sql, (*degerler, RECALL_ADAY)).fetchall()


def _adaylari_puanla(adaylar, mesaj, k) -> list:
    """
    BM25 sırasını ORTAKLIK ve TAZELİK ile yeniden ağırlıklandırır.

    Neden yeniden puanlama: BM25 nadir kelimeyi çok ödüllendirir; tek bir
    ortak kelimeyle alakasız bir konuşma başa çıkabiliyor. Kelime ortaklığı
    bunu dengeler, tazelik ise eski cevaplar yerine güncelini seçtirir.
    """
    simdi = datetime.now()
    puanli = []
    for kullanici, ultron, tarih, bm in adaylar:
        ortaklik = _ortaklik(mesaj, kullanici)
        if ortaklik < 0.15:
            continue
        # Cevabı olmayan / hata mesajıyla biten turlar öğretici değildir
        cevap = (ultron or '').strip()
        if not cevap or cevap.startswith('⚠️') or 'Yanıt alınamadı' in cevap:
            devam_puani = 0.5
        else:
            devam_puani = 1.0
        yas_gun = 999.0
        try:
            yas_gun = max(0.0, (simdi - datetime.strptime(str(tarih)[:19],
                                                          '%Y-%m-%d %H:%M:%S')).days)
        except Exception:
            pass
        tazelik = 1.0 / (1.0 + yas_gun / 45.0)      # 45 günde yarıya iner
        bm_katki = min(1.0, abs(bm) / 10.0) if bm else 0.0
        skor = (ortaklik * 2.0 + bm_katki + tazelik * 0.5) * devam_puani
        puanli.append((skor, {'soru': kullanici, 'cevap': cevap,
                              'tarih': str(tarih)[:16], 'skor': round(skor, 3)}))
    puanli.sort(key=lambda x: x[0], reverse=True)

    # Aynı sorunun tekrarları arka arkaya gelmesin — tekilleştir
    secilen, gorulen = [], set()
    for _skor, kayit in puanli:
        anahtar = sadelestir(kayit['soru'])[:60]
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        secilen.append(kayit)
        if len(secilen) >= k:
            break
    return secilen


def prompt_blogu(mesaj: str, k: int = 3) -> str:
    """
    Geri çağrılan konuşmaları prompt'a girecek metne çevirir.

    ⚠️ "GEÇMİŞTEN" uyarısı şart: model eski bir konuşmayı bugün olmuş gibi
    anlatırsa halüsinasyondan farkı kalmaz.
    """
    kayitlar = alakali_konusmalar(mesaj, k=k)
    if not kayitlar:
        return ""
    satirlar = []
    for kayit in kayitlar:
        soru = kayit['soru'][:200].replace('\n', ' ')
        cevap = kayit['cevap'][:220].replace('\n', ' ')
        satirlar.append(f"- ({kayit['tarih']}) KULLANICI dedi ki: \"{soru}\" "
                        f"— SEN cevap vermiştin: \"{cevap}\"")
    # ⚠️ İki uyarı da şart:
    #   • "geçmişten" → model eski konuşmayı bugün olmuş gibi anlatırsa
    #     halüsinasyondan farkı kalmaz.
    #   • "kullanıcının bilgisi" → küçük model canlı testte "kedimin adı Pamuk"
    #     dedi; kullanıcının hayatını kendi hayatı gibi anlatmaya eğilimli.
    return ("\n[GEÇMİŞ KONUŞMA ARŞİVİ — kalıcı hafıza]\n" + "\n".join(satirlar) +
            "\nBu kayıtlar GEÇMİŞTEN gelir; bugün olmuş gibi anlatma. "
            "Buradaki bilgiler KULLANICIYA aittir, sana değil "
            "(\"senin kedinin adı\" de, \"benim kedim\" DEME). "
            "Sorulan şey bunlarla ilgiliyse hatırladığını söyleyebilirsin.\n")


# ---------------------------------------------------------------------------
# 2. SÜTUN — ÖRÜNTÜ ÇIKARIMI (deterministik)
# ---------------------------------------------------------------------------
_ORUNTU_ONBELLEK = {'zaman': 0.0, 'veri': None}

ZAMAN_DILIMLERI = (
    ('sabah', 6, 11), ('öğlen', 11, 17), ('akşam', 17, 23), ('gece', 23, 6),
)


def _onbellegi_dusur():
    _ORUNTU_ONBELLEK['zaman'] = 0.0
    _ORUNTU_ONBELLEK['veri'] = None


def _dilim(saat) -> str:
    if saat is None:
        return ''
    for ad, bas, bit in ZAMAN_DILIMLERI:
        if bas < bit:
            if bas <= saat < bit:
                return ad
        elif saat >= bas or saat < bit:
            return ad
    return ''


def oruntuler(zorla: bool = False) -> dict:
    """
    Arşivden çıkarılan davranış örüntüleri.

    {'toplam': int, 'sik_komut': [...], 'zaman': [...], 'etiket': [...],
     'konu': [...], 'kalip': [...]}

    Hepsi SQL toplamasıdır — LLM yok. `MIN_ORUNTU_GOZLEM` altındaki hiçbir şey
    örüntü sayılmaz: iki kez olan bir şey alışkanlık değildir.
    """
    if not zorla and _ORUNTU_ONBELLEK['veri'] is not None and \
            (time.time() - _ORUNTU_ONBELLEK['zaman']) < ORUNTU_TAZELIK_SN:
        return _ORUNTU_ONBELLEK['veri']
    try:
        with _acik() as conn:
            veri = {
                'toplam': conn.execute("SELECT COUNT(*) FROM konusma").fetchone()[0],
                'sik_komut': _sik_komutlar(conn),
                'zaman': _zaman_aliskanliklari(conn),
                'etiket': _sik_etiketler(conn),
                'konu': _sik_konular(conn),
                'kalip': _kaliplari_listele(conn),
                'ruh_hali': _ruh_hali_oruntusu(conn),
            }
        _ORUNTU_ONBELLEK.update({'zaman': time.time(), 'veri': veri})
        return veri
    except Exception as e:
        print(f"[ULTRON Ogrenme] Oruntu cikarilamadi: {e}")
        return {'toplam': 0, 'sik_komut': [], 'zaman': [], 'etiket': [],
                'konu': [], 'kalip': [],
                'ruh_hali': {'toplam': 0, 'dagilim': {}, 'dilim': None, 'konu': []}}


def _sik_komutlar(conn) -> list:
    # `ornek` = kullanıcının ORİJİNAL cümlesi. `sade` ASCII'ye indirgenmiştir
    # ("ekran goruntusu al") ve niyet regex'leri Türkçe harfle yazılıdır —
    # sade metni komut olarak geri oynatan bir şey (öneri/kısayol) hiçbir
    # niyete eşleşmez. Geri oynatılacak metin her zaman bu sütundan alınmalı.
    satirlar = conn.execute(
        "SELECT sade, COUNT(*) c, MAX(intent), MAX(tarih), MAX(kullanici) FROM konusma "
        "WHERE basarili = 1 AND intent IS NOT NULL AND intent != 'GENERAL_CONVERSATION' "
        "GROUP BY sade HAVING c >= ? ORDER BY c DESC LIMIT 8",
        (MIN_ORUNTU_GOZLEM,)).fetchall()
    return [{'komut': s, 'sayi': c, 'intent': i, 'son': (t or '')[:16],
             'ornek': kanalsiz(o) or s}
            for s, c, i, t, o in satirlar]


def _zaman_aliskanliklari(conn) -> list:
    """
    "Sabahları genelde X yapıyorsun" — ama yalnızca gerçekten YOĞUNLAŞMA varsa.

    Bir niyet gün içine eşit dağılmışsa alışkanlık değildir; o yüzden dilimin
    payı %50'nin altındaysa örüntü sayılmaz.
    """
    satirlar = conn.execute(
        "SELECT intent, saat, COUNT(*) FROM konusma "
        "WHERE intent IS NOT NULL AND intent != 'GENERAL_CONVERSATION' AND saat IS NOT NULL "
        "GROUP BY intent, saat").fetchall()
    toplam, dilimli, saatli = {}, {}, {}
    for intent, saat, sayi in satirlar:
        toplam[intent] = toplam.get(intent, 0) + sayi
        ad = _dilim(saat)
        if ad:
            dilimli[(intent, ad)] = dilimli.get((intent, ad), 0) + sayi
            # Dilim içindeki en yoğun SAAT — "sabahları" bir öneriye
            # çevrilemez, "08:00" çevrilebilir.
            onceki = saatli.get((intent, ad))
            if onceki is None or sayi > onceki[1]:
                saatli[(intent, ad)] = (saat, sayi)

    sonuc = []
    for (intent, ad), sayi in dilimli.items():
        if sayi < MIN_ORUNTU_GOZLEM:
            continue
        pay = sayi / max(1, toplam.get(intent, sayi))
        if pay < 0.5:
            continue
        tepe = saatli.get((intent, ad))
        sonuc.append({'intent': intent, 'dilim': ad, 'sayi': sayi,
                      'pay': round(pay, 2),
                      'saat': tepe[0] if tepe else None})
    sonuc.sort(key=lambda x: x['sayi'], reverse=True)
    return sonuc[:5]


def _sik_etiketler(conn) -> list:
    satirlar = conn.execute(
        "SELECT tip, deger, COUNT(*) c FROM etiket GROUP BY tip, deger "
        "HAVING c >= ? ORDER BY c DESC LIMIT 8", (MIN_ORUNTU_GOZLEM,)).fetchall()
    return [{'tip': t, 'deger': d, 'sayi': c} for t, d, c in satirlar]


def _sik_konular(conn) -> list:
    """Sohbet mesajlarında sık geçen içerik kelimeleri (son 3000 kayıt)."""
    satirlar = conn.execute(
        "SELECT sade FROM konusma WHERE intent IS NULL OR intent = 'GENERAL_CONVERSATION' "
        "ORDER BY id DESC LIMIT 3000").fetchall()
    sayac = {}
    for (sade,) in satirlar:
        for kelime in set(_tokenlar(sade)):
            if len(kelime) >= 4:
                sayac[kelime] = sayac.get(kelime, 0) + 1
    esik = max(MIN_ORUNTU_GOZLEM, 4)
    sirali = sorted((k for k in sayac.items() if k[1] >= esik),
                    key=lambda x: x[1], reverse=True)
    return [{'kelime': k, 'sayi': s} for k, s in sirali[:8]]


def _ruh_hali_oruntusu(conn) -> dict:
    """
    Arşiv × ruh hâli kesişimi: duygu NE ZAMAN ve NEDEN BAHSEDERKEN değişiyor.

    `ruh_hali_gecmisi` tablosu duyguyu tek başına tutuyordu — "%40 negatif"
    bilgisi tek başına eyleme dönüşmez. Aynı satırda saat ve metin varken
    "akşamları" ve "hangi konuda" cevaplanabilir hâle geliyor.

    ⚠️ Bu çıktı RAPORA girer, PROMPT'a GİRMEZ (`profil_satirlari` almaz).
    Modele "kullanıcı gergin" demek onu terapiste çevirir; küçük model zaten
    yorum yapmaya hevesli. Burada üretilen tek şey sayımdır, teşhis değil.
    """
    bos = {'toplam': 0, 'dagilim': {}, 'dilim': None, 'konu': []}
    try:
        satirlar = conn.execute(
            "SELECT ruh_hali, saat, sade FROM konusma "
            "WHERE ruh_hali IS NOT NULL AND ruh_hali != '' AND ruh_hali != 'belirsiz' "
            "ORDER BY id DESC LIMIT 3000").fetchall()
    except sqlite3.Error:
        return bos
    if len(satirlar) < MIN_ORUNTU_GOZLEM:
        return bos

    dagilim, dilim_toplam, dilim_negatif, konu_sayac = {}, {}, {}, {}
    for ruh, saat, sade in satirlar:
        dagilim[ruh] = dagilim.get(ruh, 0) + 1
        ad = _dilim(saat)
        if ad:
            dilim_toplam[ad] = dilim_toplam.get(ad, 0) + 1
            if ruh == 'negatif':
                dilim_negatif[ad] = dilim_negatif.get(ad, 0) + 1
        if ruh == 'negatif':
            for kelime in set(_tokenlar(sade)):
                if len(kelime) >= 4:
                    konu_sayac[kelime] = konu_sayac.get(kelime, 0) + 1

    # Negatifin YOĞUNLAŞTIĞI dilim — yalnızca gerçekten öne çıkıyorsa.
    # Eşit dağılmış duygu bir örüntü değildir; öyle sunmak veri uydurmaktır.
    en_yogun = None
    for ad, sayi in dilim_negatif.items():
        toplam = dilim_toplam.get(ad, sayi)
        pay = sayi / max(1, toplam)
        if sayi >= MIN_ORUNTU_GOZLEM and pay >= 0.5 and \
                (en_yogun is None or sayi > en_yogun['sayi']):
            en_yogun = {'dilim': ad, 'sayi': sayi, 'toplam': toplam,
                        'pay': round(pay, 2)}

    konular = sorted((k for k in konu_sayac.items() if k[1] >= MIN_ORUNTU_GOZLEM),
                     key=lambda x: x[1], reverse=True)[:5]
    return {'toplam': len(satirlar), 'dagilim': dagilim, 'dilim': en_yogun,
            'konu': [{'kelime': k, 'sayi': s} for k, s in konular]}


def profil_satirlari(azami: int = 5) -> list:
    """
    Örüntülerin prompt'a girecek insan dilindeki özeti.

    Sadece GÖZLENMİŞ olguları yazar ("12 kez hava sordun"), yorum yapmaz —
    çıkarım yapmak modelin işi değil, uydurma kapısıdır.
    """
    try:
        veri = oruntuler()
        satirlar = []
        for k in veri['sik_komut'][:2]:
            satirlar.append(f"'{k['komut']}' komutunu {k['sayi']} kez kullandı")
        for z in veri['zaman'][:2]:
            satirlar.append(f"{z['dilim'].capitalize()} saatlerinde genelde "
                            f"{_intent_turkce(z['intent'])} istiyor ({z['sayi']} kez)")
        for e in veri['etiket'][:2]:
            etiket_adi = 'en sık iletişim kurduğu kişi' if e['tip'] == 'kisi' \
                else 'en sık açtığı uygulama'
            satirlar.append(f"{etiket_adi}: {e['deger']} ({e['sayi']} kez)")
        konular = [k['kelime'] for k in veri['konu'][:4]]
        if konular:
            satirlar.append("sık konuştuğu konular: " + ", ".join(konular))
        return satirlar[:azami]
    except Exception as e:
        print(f"[ULTRON Ogrenme] Profil uretilemedi: {e}")
        return []


_INTENT_TR = {
    'WEATHER': 'hava durumu', 'CURRENCY': 'döviz kuru', 'PLAY_MUSIC': 'müzik',
    'MORNING_BRIEFING': 'sabah brifingi', 'EVENING_REPORT': 'akşam raporu',
    'SYSTEM_CONTROL': 'uygulama/sistem komutu', 'SET_VOLUME': 'ses ayarı',
    'FILE_SEARCH': 'dosya arama', 'FILE_TRANSFER': 'dosya gönderme',
    'WHATSAPP_MESSAGE': 'WhatsApp mesajı', 'EMAIL_MESSAGE': 'e-posta',
    'WEB_SEARCH': 'internet araması', 'NOTE_TAKE': 'not', 'TIMER': 'sayaç',
    'CREATE_REMINDER': 'hatırlatma', 'SCREENSHOT': 'ekran görüntüsü',
    'CLIPBOARD': 'pano işlemi', 'FOCUS_MODE': 'odak modu',
    'CALCULATOR': 'hesap', 'TIME_DATE': 'saat/tarih',
    'MEDIA_CONTROL': 'medya kontrolü', 'ANALYSIS_REPORT': 'analiz raporu',
    # Eksik kalanlar rapora ham adıyla düşüyordu ("keyboard_input" diye).
    # Yeni bir niyet eklerken buraya da bir satır: rapor kullanıcının okuduğu yer.
    'KEYBOARD_INPUT': 'klavye komutu', 'SCHEDULE_TASK': 'zamanlanmış görev',
    'FILE_INDEX': 'dosya indeksi', 'FILE_OPERATION': 'dosya işlemi',
    'LEARNING_REPORT': 'öğrenme raporu',
}


def _intent_turkce(intent: str) -> str:
    return _INTENT_TR.get(intent, (intent or '').lower())


# ---------------------------------------------------------------------------
# 3. SÜTUN — DÜZELTMEDEN ÖĞRENME
# ---------------------------------------------------------------------------
def _duzeltmeden_ogren(conn, kanal, kullanici, sade, intent, basarili) -> None:
    """
    Önceki tur anlaşılmadı, bu tur başardı → eski ifadeyi bu niyete bağla.

    Kapılar (hepsi gerekli):
      • önceki tur BAŞARISIZ ve niyetsiz/sohbet olmalı
      • bu tur BAŞARILI ve ÖĞRENİLEBİLİR bir niyette olmalı
      • aradan 5 dakikadan az geçmiş olmalı (sonraki gün gelen komut düzeltme değildir)
      • iki cümle aynı şeyden bahsetmeli (kelime kapsaması) — yoksa kullanıcı
        sadece konu değiştirmiştir
      • iki cümle AYNI olmamalı (aynıysa öğrenilecek yeni bir şey yok)
    """
    if not basarili or intent not in OGRENILEBILIR_INTENTLER:
        return
    onceki = _SON_TUR.get(kanal)
    if not onceki or onceki['basarili']:
        return
    if onceki['intent'] not in (None, 'GENERAL_CONVERSATION'):
        return
    if (time.time() - onceki['zaman']) > DUZELTME_PENCERESI_SN:
        return
    if onceki['sade'] == sade:
        return
    if _kapsama(onceki['metin'], kullanici) < DUZELTME_KAPSAMA:
        return
    _kalip_yaz(conn, onceki['sade'], intent, onceki['metin'])


def _kalip_yaz(conn, sade, intent, ornek) -> None:
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    satir = conn.execute("SELECT intent, gozlem FROM kalip WHERE sade = ?",
                         (sade,)).fetchone()
    if satir and satir[0] != intent:
        # Aynı ifade iki farklı niyete bağlanıyorsa ÖĞRENME GÜVENİLMEZDİR.
        # Kalıbı yükseltmek yerine düşür: kararsız kalıp yanlış komut demektir.
        conn.execute("DELETE FROM kalip WHERE sade = ?", (sade,))
        return
    conn.execute(
        "INSERT INTO kalip (sade, intent, gozlem, aktif, ornek, ilk, son) "
        "VALUES (?, ?, 1, 0, ?, ?, ?) "
        "ON CONFLICT(sade) DO UPDATE SET gozlem = gozlem + 1, son = excluded.son, "
        "aktif = CASE WHEN gozlem + 1 >= ? THEN 1 ELSE 0 END",
        (sade, intent, ornek, simdi, simdi, MIN_GOZLEM_KALIP))


def ogrenilmis_intent(mesaj: str):
    """
    Öğrenilmiş kalıplarda bu mesajın karşılığı var mı?

    Dönüş: (intent, ornek_cumle) veya None.

    Eşleşme SIKIDIR: ya birebir aynı ifade, ya da %85 üzeri kelime ortaklığı.
    Bulanık eşleşme yasağı burada da geçerli — gevşek eşleşme, kullanıcının
    sohbet cümlesini komuta çevirir.
    """
    try:
        sade = sadelestir(mesaj).strip()
        if not sade or not ogrenilebilir_mi(mesaj):
            return None
        with _acik() as conn:
            satir = conn.execute(
                "SELECT intent, ornek FROM kalip WHERE sade = ? AND aktif = 1",
                (sade,)).fetchone()
            if satir:
                return satir[0], satir[1]
            adaylar = conn.execute(
                "SELECT sade, intent, ornek FROM kalip WHERE aktif = 1 "
                "ORDER BY gozlem DESC LIMIT 200").fetchall()
        for aday_sade, intent, ornek in adaylar:
            if _ortaklik(aday_sade, sade) >= KALIP_ESIK:
                return intent, ornek
        return None
    except Exception as e:
        print(f"[ULTRON Ogrenme] Kalip okunamadi: {e}")
        return None


def _kaliplari_listele(conn) -> list:
    satirlar = conn.execute(
        "SELECT sade, intent, gozlem, aktif, ornek FROM kalip "
        "ORDER BY aktif DESC, gozlem DESC LIMIT 20").fetchall()
    return [{'sade': s, 'intent': i, 'gozlem': g, 'aktif': bool(a), 'ornek': o}
            for s, i, g, a, o in satirlar]


# ---------------------------------------------------------------------------
# KULLANICI ARAYÜZÜ — "ne öğrendin" / "şunu unut"
# ---------------------------------------------------------------------------
# Kalıplar SADELEŞTİRİLMİŞ metin üzerinde çalışır → hepsi ASCII yazılmalı.
_RAPOR_KALIPLARI = (
    r'\b(ne|neler)\s+ogrendin',
    r'\bogrendiklerin(i|iz)?\b(?!\s*unut)',
    r'\bogrenme raporu\b',
    r'\bhakkimda\s+ne(ler)?\s+biliyorsun',
    r'\bbeni\s+(ne kadar\s+)?taniyor\s*musun',
)
# "unut" TEK BAŞINA yetmez: sohbette geçen "bu konuyu unut" cümlesi kalıp
# silmeye kalkmasın. Ya açık nesne (":" ile), ya "öğrendiklerini unut" gerekir.
_UNUT_KALIPLARI = (
    r'(?:sunu|bunu|kalibi|ifadeyi)?\s*unut(?:ma)?\s*:\s*(?P<hedef>.+)$',
    r'\bogrendiklerin(?:i|izi)?\s+unut\b(?P<hedef>)',
    r'\bogrendiklerin(?:i|izi)?\s+sil\b(?P<hedef>)',
)


# Öneri kabul/red — sayı ya da düz ifade ("2. öneriyi uygula", "öneriyi boşver").
# Bu kalıplar sohbette kazara kurulmaz; guard'a ihtiyaçları yok.
_ONERI_KABUL_KALIPLARI = (
    r'(?P<hedef>\d+)\s*\.?\s*(?:numarali\s+)?oneriyi\s+(?:kabul et|uygula|kur|onayla|yap)',
    r'\boneri(?:yi)?\s+(?:kabul et|uygula|kur|onayla)\s*:?\s*(?P<hedef>\d*)',
)
_ONERI_RED_KALIPLARI = (
    r'(?P<hedef>\d+)\s*\.?\s*(?:numarali\s+)?oneriyi\s+(?:reddet|bosver|iptal et|istemiyorum|sil)',
    r'\boneri(?:yi)?\s+(?:reddet|bosver|iptal et|istemiyorum)\s*:?\s*(?P<hedef>\d*)',
)


def _oneri_sorgusu_mu(sade: str) -> bool:
    """
    "önerilerin neler" ULTRON'a sorulmuştur; "film önerilerin var mı" DEĞİLDİR.

    Ayrım kuralı: 'öneri' cümlenin İLK içerik kelimesi olmalı (ya da cümlede
    açık bir sistem kelimesi geçmeli). Aksi hâlde kullanıcı bir şey HAKKINDA
    öneri istiyordur ve cümle sohbete gitmelidir.

    Bu, projedeki `komut_bul` dersinin aynısı: serbest sohbet cümlesini komuta
    çevirmek, kullanıcının konuşamaz hâle gelmesi demektir.
    """
    if not re.search(r'\boneri', sade):
        return False
    if re.search(r'\b(ogrenme|sistem|ultron|aliskanlik)\s+onerileri?\b', sade):
        return True
    # "bekleyen öneri" tek başına yeterince açık: hiçbir konu hakkında
    # "bekleyen öneri" istenmez, bu Ultron'un kuyruğunu sorar.
    if re.search(r'\bbekleyen oneri', sade):
        return True
    if not re.search(r'\boneriler(?:in|iniz|ini|inizi)?\b|\boneri listesi\b', sade):
        return False
    icerik = _tokenlar(sade)
    return bool(icerik) and icerik[0].startswith('oneri')


def ogrenme_komutu_algila(metin: str):
    """
    "ne öğrendin" / "şunu unut: X" / öneri komutlarını tanır.

    Dönüş: {'islem': 'rapor'} · {'islem': 'unut', 'hedef': str} ·
           {'islem': 'oneri'} · {'islem': 'oneri_kabul'|'oneri_red', 'hedef': str} · None

    Tek kaynak: hem niyet katmanı hem araç bu fonksiyonu kullanır — kalıbı iki
    yere yazarsak biri güncellenir, diğeri unutulur.
    """
    sade = sadelestir(metin).strip()
    if not sade:
        return None
    for kalip in _ONERI_KABUL_KALIPLARI:
        eslesme = re.search(kalip, sade)
        if eslesme:
            return {'islem': 'oneri_kabul', 'hedef': (eslesme.group('hedef') or '').strip()}
    for kalip in _ONERI_RED_KALIPLARI:
        eslesme = re.search(kalip, sade)
        if eslesme:
            return {'islem': 'oneri_red', 'hedef': (eslesme.group('hedef') or '').strip()}
    for kalip in _UNUT_KALIPLARI:
        eslesme = re.search(kalip, sade)
        if eslesme:
            return {'islem': 'unut', 'hedef': (eslesme.group('hedef') or '').strip()}
    for kalip in _RAPOR_KALIPLARI:
        if re.search(kalip, sade):
            return {'islem': 'rapor'}
    if _oneri_sorgusu_mu(sade):
        return {'islem': 'oneri'}
    return None


def ogrenme_raporu() -> str:
    """Öğrenilenlerin okunabilir dökümü. Kullanıcı ne öğrenildiğini GÖRMELİ."""
    try:
        veri = oruntuler(zorla=True)
        if not veri['toplam']:
            return ("🧠 **ÖĞRENME ARŞİVİ BOŞ**\n\n"
                    "Henüz arşivlenmiş konuşma yok. Konuştukça öğrenmeye başlarım.")

        p = [f"🧠 **ÖĞRENDİKLERİM** — {veri['toplam']} konuşmadan çıkarıldı\n"]

        if veri['sik_komut']:
            p.append("**En sık kullandığın komutlar**")
            for i, k in enumerate(veri['sik_komut'][:5], 1):
                # Kullanıcı kendi cümlesini görmeli: `sade` ASCII'dir ve
                # ekranda bozuk Türkçe olarak görünüyordu ("hava nasil").
                p.append(f"{i}. `{k.get('ornek') or k['komut']}` — {k['sayi']} kez")
            p.append("")

        if veri['zaman']:
            p.append("**Zaman alışkanlıkların**")
            for z in veri['zaman'][:4]:
                p.append(f"• {z['dilim'].capitalize()} saatlerinde genelde "
                         f"**{_intent_turkce(z['intent'])}** ({z['sayi']} kez, "
                         f"%{int(z['pay'] * 100)})")
            p.append("")

        kisiler = [e for e in veri['etiket'] if e['tip'] == 'kisi']
        uygulamalar = [e for e in veri['etiket'] if e['tip'] == 'uygulama']
        if kisiler or uygulamalar:
            p.append("**Sık kullandıkların**")
            for e in kisiler[:3]:
                p.append(f"• 👤 {e['deger']} — {e['sayi']} kez mesajlaştın")
            for e in uygulamalar[:3]:
                p.append(f"• 🖥️ {e['deger']} — {e['sayi']} kez açtırdın")
            p.append("")

        if veri['konu']:
            konular = ", ".join(f"`{k['kelime']}` ({k['sayi']})"
                                for k in veri['konu'][:6])
            p.append(f"**Sık konuştuğun konular**\n{konular}\n")

        ruh = veri.get('ruh_hali') or {}
        if ruh.get('toplam'):
            d = ruh.get('dagilim') or {}
            p.append(f"**Ruh hâli gözlemleri** — {ruh['toplam']} sohbet mesajından")
            p.append(f"• 😊 pozitif {d.get('pozitif', 0)} · "
                     f"😐 nötr {d.get('nötr', 0)} · 😔 negatif {d.get('negatif', 0)}")
            if ruh.get('dilim'):
                z = ruh['dilim']
                p.append(f"• Keyifsiz mesajların çoğu **{z['dilim']}** saatlerinde "
                         f"({z['sayi']}/{z['toplam']}, %{int(z['pay'] * 100)})")
            if ruh.get('konu'):
                kelimeler = ", ".join(f"`{k['kelime']}` ({k['sayi']})" for k in ruh['konu'][:4])
                p.append(f"• Keyifsizken sık geçen kelimeler: {kelimeler}")
            p.append("")

        if veri['kalip']:
            p.append("**Öğrenilmiş ifadeler** (regex'in kaçırdığı, sonradan öğrendiğim)")
            for kal in veri['kalip'][:8]:
                durum = "✅ aktif" if kal['aktif'] else \
                    f"⏳ {kal['gozlem']}/{MIN_GOZLEM_KALIP} gözlem"
                p.append(f"• \"{kal['ornek'] or kal['sade']}\" → "
                         f"**{_intent_turkce(kal['intent'])}** ({durum})")
            p.append("\n_Yanlış öğrendiysem: `şunu unut: <ifade>`_")

        return "\n".join(p).strip()
    except Exception as e:
        return f"⚠️ Öğrenme raporu üretilemedi: {e}"


def unut(hedef: str = "") -> str:
    """
    Öğrenilmiş bir kalıbı (veya hepsini) siler.

    Konuşma ARŞİVİ silinmez: "unut" komutu bir kalıbı iptal etmek içindir,
    geçmişi yok etmek için değil. Arşivi temizlemek isteyen `arsivi_temizle()`
    çağırmalı — o da geri alınamaz olduğu için komuta bağlanmadı.
    """
    try:
        hedef_sade = sadelestir(hedef).strip()
        with _acik() as conn:
            if not hedef_sade or hedef_sade in ('hepsi', 'hepsini', 'tumu', 'tumunu',
                                                'her sey', 'hersey', 'ogrendiklerini'):
                sayi = conn.execute("SELECT COUNT(*) FROM kalip").fetchone()[0]
                conn.execute("DELETE FROM kalip")
                conn.commit()
                _onbellegi_dusur()
                return (f"🧹 {sayi} öğrenilmiş ifade silindi. "
                        f"Konuşma arşivi duruyor — sadece kalıplar unutuldu.")

            satir = conn.execute(
                "SELECT sade, ornek FROM kalip WHERE sade = ?", (hedef_sade,)).fetchone()
            if not satir:
                # Birebir yoksa en yakın kalıbı ara (kullanıcı ezberden yazmış olabilir)
                adaylar = conn.execute("SELECT sade, ornek FROM kalip").fetchall()
                satir = next((a for a in adaylar
                              if _ortaklik(a[0], hedef_sade) >= KALIP_ESIK), None)
            if not satir:
                return f"🤔 \"{hedef}\" diye öğrenilmiş bir ifade bulamadım."
            conn.execute("DELETE FROM kalip WHERE sade = ?", (satir[0],))
            conn.commit()
        _onbellegi_dusur()
        return f"🧹 Unuttum: \"{satir[1] or satir[0]}\""
    except Exception as e:
        return f"⚠️ Silinemedi: {e}"


def arsivi_temizle() -> int:
    """Tüm öğrenme arşivini siler. GERİ ALINAMAZ — komuta bağlanmadı."""
    with _acik() as conn:
        sayi = conn.execute("SELECT COUNT(*) FROM konusma").fetchone()[0]
        conn.execute("DELETE FROM konusma")
        conn.execute("DELETE FROM etiket")
        conn.execute("DELETE FROM kalip")
        if _fts_destegi:
            conn.execute("DELETE FROM konusma_fts")
        conn.execute("DELETE FROM meta")
        conn.commit()
    _SON_TUR.clear()
    _onbellegi_dusur()
    return sayi


def istatistik() -> dict:
    """Arayüz/istatistik sayfası için sayılar."""
    try:
        with _acik() as conn:
            return {
                'konusma': conn.execute("SELECT COUNT(*) FROM konusma").fetchone()[0],
                'kalip': conn.execute("SELECT COUNT(*) FROM kalip WHERE aktif = 1").fetchone()[0],
                'kalip_aday': conn.execute("SELECT COUNT(*) FROM kalip WHERE aktif = 0").fetchone()[0],
                'etiket': conn.execute("SELECT COUNT(*) FROM etiket").fetchone()[0],
            }
    except Exception:
        return {'konusma': 0, 'kalip': 0, 'kalip_aday': 0, 'etiket': 0}
