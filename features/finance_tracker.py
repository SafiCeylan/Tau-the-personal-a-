# -*- coding: utf-8 -*-
"""
ULTRON FINANS VE BÜTÇE TAKİBİ MOTORU — Günlük harcamaları kaydeder ve raporlar.

İKİ TASARIM KARARI (ikisi de acı çekerek değil, ÖLÇÜLEREK alındı):

1) PARA KURUŞ OLARAK SAKLANIR (INTEGER).
   `REAL` ile 0.1 + 0.2 != 0.3'tür; yüzlerce kayıt toplanınca kuruşlar kayar ve
   "toplam" ile kalemlerin toplamı tutmaz. Bütçe rakamı tutmayınca özelliğin
   tamamı güvenilmez olur. DB'ye `miktar_kurus` yazılır, ekrana TL basılır.

2) TÜRKÇE SAYI BİÇİMİ ÖZEL AYRIŞTIRILIR.
   Türkçede binlik ayracı NOKTA, ondalık ayracı VİRGÜLDÜR. Naif
   `replace(",", ".")` yaklaşımı ölçülen şu hataları veriyordu:
       "1.200 TL"    → 1.2 TL     (1000 kat eksik)
       "12.500 TL"   → 12.5 TL    (1000 kat eksik)
       "1.250,75 TL" → 250.75 TL  (baştaki bin uçuyordu)
   Sessiz para hatasıdır: kullanıcı yanlış bütçeyi doğru sanır. `turkce_para_coz`
   bu yüzden var; `tests/test_finance_tracker.py` biçimleri kilitler.
"""

import os
import re
import sqlite3
from datetime import datetime
from typing import Tuple, Dict, Any, Optional

from core.paths import veri_dizini


def _db_baglantisi():
    db_yolu = os.path.join(veri_dizini(), "bilgiler.db")
    conn = sqlite3.connect(db_yolu)
    conn.row_factory = sqlite3.Row
    return conn


KATEGORI_KALIPLARI = {
    "market": r"\b(market|bakkal|süpermarket|grocer|migros|bim|a101|şok)\w*",
    "yemek": r"\b(yemek|yemeğe|restoran|lokanta|kafe|cafe|kahve|starbucks|döner|burger)\w*",
    "ulasim": r"\b(benzin|yakıt|otobüs|metrobüs|taksi|uber|akbil|dolmuş|otopark)\w*",
    "fatura": r"\b(fatura|elektrik|su|doğalgaz|internet|telefon|aidat|kira|kiraya)\w*",
    "eglence": r"\b(sinema|tiyatro|konser|oyun|steam|netflix|spotify)\w*",
}

# Binlik ayraçlı sayıyı da yakalar: "1.250,75" tek parça okunmalı. Eski desen
# (`\d+(?:[.,]\d+)?`) "1.250,75" içinde "250,75"i yakalayıp bini düşürüyordu.
#
# ⚠️ DIŞ PARANTEZ ŞART: bu sabit başka desenlere birleştiriliyor. Gruplamasız
# yazıldığında içindeki `|` ÜST SEVİYEDE bölüyor ve `"...markete\s+" + _SAYI`
# deseni "herhangi bir sayı" hâline geliyordu — ölçülen sonuç: "3'ü kapat"
# FINANCE_TRACK'e düştü (uygulama kapatma bozuldu).
_SAYI = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"

_PARA_RE = re.compile(r"(" + _SAYI + r")\s*(?:tl|lira|₺)", re.IGNORECASE)
_PARA_FIIL_RE = re.compile(
    r"(" + _SAYI + r")\s*(?:tl|lira|₺)?\s*(?:harcadım|harcadim|verdim|ödedim|odedim)",
    re.IGNORECASE,
)


def turkce_para_coz(sayi_metni: str) -> Optional[int]:
    """'1.250,75' → 125075 kuruş. Tanıyamazsa None.

    Kural (standart Türkçe yazım):
      • Virgül VARSA → virgül ondalıktır, noktalar binlik ayracıdır.
      • Virgül YOKSA → nokta ancak ardından TAM 3 hane geliyorsa binlik ayracıdır
        ("1.200"). Aksi hâlde ondalıktır ("50.50" = 50 TL 50 kr).
    """
    s = (sayi_metni or "").strip()
    if not s:
        return None

    if "," in s:
        tam, _, kesir = s.rpartition(",")
        tam = tam.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        tam, kesir = s.replace(".", ""), ""
    elif "." in s:
        tam, _, kesir = s.rpartition(".")
    else:
        tam, kesir = s, ""

    tam = tam.replace(" ", "")
    if not tam.isdigit():
        return None

    kesir = (kesir or "").strip()
    if kesir and not kesir.isdigit():
        return None
    # Kuruş iki hanedir: "5" → 50 kr, "753" → 75 kr (aşağı yuvarla, uydurma yok)
    kurus = int((kesir + "00")[:2]) if kesir else 0
    return int(tam) * 100 + kurus


def kurus_to_tl(kurus: int) -> str:
    """Ekrana basılacak TL metni — Türkçe biçimde (binlik nokta, ondalık virgül)."""
    tam, kr = divmod(int(kurus), 100)
    return f"{tam:,}".replace(",", ".") + f",{kr:02d}"


def kategori_tahmin_et(metin: str) -> str:
    metin_lower = metin.lower()
    for kat, pattern in KATEGORI_KALIPLARI.items():
        if re.search(pattern, metin_lower):
            return kat
    return "Genel"


def finans_niyeti_algila(cumle: str) -> bool:
    msg = cumle.lower()
    if re.search(r'\b(harcama|harcamalar|harcamalarım|bütçe|butce)\b', msg):
        return True
    if _PARA_FIIL_RE.search(msg):
        return True
    if re.search(r'\b(markete|yemeğe|benzine|faturaya|kiraya)\s+' + _SAYI, msg):
        return True
    return False


# Özet penceresi: "bugün ne kadar harcadım" ile "toplam harcamam" AYNI ŞEY DEĞİL.
# Pencere verilmezse İÇİNDE BULUNULAN AY kullanılır — "toplam" diye tüm zamanların
# toplamını basmak birkaç hafta sonra anlamsız bir sayı gösterir.
_DONEMLER = [
    # Türkçe ek alır ("tüm zamanların") → sondaki \b kullanılamaz.
    (r'\b(tüm zaman|tum zaman|her zaman|genel toplam|başından beri|basindan beri)', 'hepsi', 'tüm zamanlar'),
    (r'\b(bugün|bugun|günlük|gunluk)\b', 'gun', 'bugün'),
    (r'\b(bu hafta|haftalık|haftalik|son 7 gün)\b', 'hafta', 'bu hafta'),
    (r'\b(bu ay|aylık|aylik|son 30 gün)\b', 'ay', 'bu ay'),
    (r'\b(bu yıl|bu yil|yıllık|yillik)\b', 'yil', 'bu yıl'),
]


def donem_coz(cumle: str) -> Tuple[str, str]:
    """Cümleden zaman penceresini çıkarır. Varsayılan: içinde bulunulan ay."""
    msg = (cumle or "").lower()
    for kalip, kod, etiket in _DONEMLER:
        if re.search(kalip, msg):
            return kod, etiket
    return 'ay', 'bu ay'


def _donem_kosulu(donem: str) -> Tuple[str, list]:
    """Dönem kodunu SQL WHERE parçasına çevirir (SQLite tarih fonksiyonlarıyla)."""
    if donem == 'hepsi':
        return "", []
    if donem == 'gun':
        return "date(tarih) = date('now','localtime')", []
    if donem == 'hafta':
        return "date(tarih) >= date('now','localtime','-6 days')", []
    if donem == 'yil':
        return "strftime('%Y', tarih) = strftime('%Y','now','localtime')", []
    return "strftime('%Y-%m', tarih) = strftime('%Y-%m','now','localtime')", []


_TABLO = """
    CREATE TABLE IF NOT EXISTS harcamalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        miktar_kurus INTEGER NOT NULL,
        kategori TEXT DEFAULT 'Genel',
        aciklama TEXT,
        tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


def harcama_cumlesi_coz(cumle: str) -> Tuple[Optional[int], Optional[str], str]:
    """Cümleden (kuruş, açıklama, kategori) çıkarır.

    'bugün markete 1.200 TL harcadım' -> (120000, '<cümle>', 'market')
    """
    match = _PARA_RE.search(cumle) or _PARA_FIIL_RE.search(cumle)
    if not match:
        return None, None, "Genel"

    kurus = turkce_para_coz(match.group(1))
    if kurus is None or kurus <= 0:
        return None, None, "Genel"
    return kurus, cumle.strip(), kategori_tahmin_et(cumle)


def harcama_ekle(miktar_kurus: int, aciklama: str = "", kategori: str = "Genel") -> Dict[str, Any]:
    conn = None
    try:
        # `with sqlite3.connect(...)` bağlantıyı kapatmaz — açıkça kapatılır.
        conn = _db_baglantisi()
        cursor = conn.cursor()
        cursor.execute(_TABLO)
        cursor.execute(
            "INSERT INTO harcamalar (miktar_kurus, kategori, aciklama) VALUES (?, ?, ?)",
            (int(miktar_kurus), kategori, aciklama),
        )
        conn.commit()
        record_id = cursor.lastrowid
        return {
            "basarili": True,
            "id": record_id,
            "miktar_kurus": int(miktar_kurus),
            "kategori": kategori,
            "aciklama": aciklama,
            "mesaj": f"💰 {kurus_to_tl(miktar_kurus)} TL harcama '{kategori}' kategorisine kaydedildi.",
        }
    except Exception as e:
        return {"basarili": False, "hata": str(e), "mesaj": f"Harcama kaydedilemedi: {e}"}
    finally:
        if conn is not None:
            conn.close()


def harcama_ozeti(kategori: Optional[str] = None, donem: str = 'ay',
                  donem_etiketi: str = 'bu ay') -> Dict[str, Any]:
    """Dönem ve kategori filtresi TOPLAMA DA DAĞILIMA DA aynı uygulanır.

    (Eski sürümde kategori filtresi yalnızca toplama uygulanıyordu; dağılım
    filtresiz geldiği için "market harcamam" sorusuna bütün kategoriler
    listeleniyor ve toplam ile kalemler tutmuyordu.)
    """
    conn = None
    try:
        kosullar, parametreler = [], []
        tarih_kosul, tarih_param = _donem_kosulu(donem)
        if tarih_kosul:
            kosullar.append(tarih_kosul)
            parametreler += tarih_param
        if kategori:
            kosullar.append("kategori = ?")
            parametreler.append(kategori)
        where = (" WHERE " + " AND ".join(kosullar)) if kosullar else ""

        conn = _db_baglantisi()
        cursor = conn.cursor()
        cursor.execute(_TABLO)
        cursor.execute(
            "SELECT SUM(miktar_kurus) AS toplam, COUNT(*) AS adet FROM harcamalar" + where,
            parametreler,
        )
        row = cursor.fetchone()
        toplam = int(row["toplam"] or 0)
        adet = int(row["adet"] or 0)

        cursor.execute(
            "SELECT kategori, SUM(miktar_kurus) AS kat_toplam FROM harcamalar"
            + where + " GROUP BY kategori ORDER BY kat_toplam DESC",
            parametreler,
        )
        kategoriler = {r["kategori"]: int(r["kat_toplam"] or 0) for r in cursor.fetchall()}

        if adet == 0:
            return {
                "basarili": True, "toplam_kurus": 0, "adet": 0, "kategoriler": {},
                "donem": donem_etiketi,
                "mesaj": f"📊 {donem_etiketi.capitalize()} için kayıtlı harcama yok.",
            }

        kat_metni = ""
        if kategoriler:
            kat_metni = "\n" + "\n".join(
                f"  • {k}: {kurus_to_tl(v)} TL" for k, v in kategoriler.items()
            )

        return {
            "basarili": True,
            "toplam_kurus": toplam,
            "adet": adet,
            "kategoriler": kategoriler,
            "donem": donem_etiketi,
            "mesaj": (f"📊 Harcama Özeti ({donem_etiketi}): "
                      f"**{kurus_to_tl(toplam)} TL** ({adet} kayıt){kat_metni}"),
        }
    except Exception as e:
        return {"basarili": False, "hata": str(e), "mesaj": f"Harcama özeti alınamadı: {e}"}
    finally:
        if conn is not None:
            conn.close()
