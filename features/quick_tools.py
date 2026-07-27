# -*- coding: utf-8 -*-
"""
Hızlı Yardımcılar — not alma, sayaç, hesap makinesi, saat/tarih.

Tasarım kararı: Bu işlerin hiçbiri LLM'e sorulmaz. Hepsi deterministik çalışır.
LLM "125*48 kaç eder" sorusuna yanlış cevap verebilir; burada Python hesaplar.
Saat/tarih de aynı — modelin eğitim tarihi değil, sistemin gerçek saati okunur.

Sayaç, yeni bir zamanlayıcı altyapısı kurmaz: mevcut `hatirlatmalar` tablosuna
hedef zamanlı kayıt yazar, uygulamanın hatırlatma döngüsü onu zaten kontrol
ediyor. Böylece bildirim/Telegram/ses akışı bedavaya gelir.
"""

import ast
import operator
import re
from datetime import datetime, timedelta

# Türkçe karakter toleransı: kullanıcı "notlarimi goster" yazsa da anlaşılsın.
# Anahtar kelime karşılaştırmaları bu sadeleştirilmiş biçim üzerinden yapılır.
_TR_HARITA = str.maketrans('çğıöşüâîû', 'cgiosuaiu')


def _sadelestir(metin: str) -> str:
    """Küçük harfe çevirip Türkçe karakterleri ASCII karşılığına indirger."""
    return (metin or "").lower().translate(_TR_HARITA).strip()

# ---------------------------------------------------------------------------
# HESAP MAKİNESİ
# ---------------------------------------------------------------------------
# Güvenlik: eval() KULLANILMAZ. Sadece izin verilen matematik düğümleri
# yürütülür; fonksiyon çağrısı, değişken, içe aktarma kabul edilmez.
_IZINLI_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Türkçe sözel operatörler → sembol
_SOZEL_OPS = [
    (r'\bbölü\b', '/'), (r'\bbolu\b', '/'),
    (r'\bçarpı\b', '*'), (r'\bcarpi\b', '*'), (r'\bkere\b', '*'),
    (r'\bartı\b', '+'), (r'\barti\b', '+'),
    (r'\beksi\b', '-'),
    (r'\büzeri\b', '**'), (r'\buzeri\b', '**'),
]

# Sözel sayılar → rakam. Sıra ÖNEMLİ: uzun ifadeler ("on beş") kısa olanlardan
# ("on") önce eşleşmeli, yoksa "on beş" → "10 5" olur.
_SAYI_KELIMELERI = [
    ('yüz', 100), ('yuz', 100),
    ('doksan', 90), ('seksen', 80), ('yetmiş', 70), ('yetmis', 70),
    ('altmış', 60), ('altmis', 60), ('elli', 50), ('kırk', 40), ('kirk', 40),
    ('otuz', 30), ('yirmi', 20),
    ('onbeş', 15), ('onbes', 15),
    ('on', 10), ('dokuz', 9), ('sekiz', 8), ('yedi', 7),
    ('altı', 6), ('alti', 6), ('beş', 5), ('bes', 5),
    ('dört', 4), ('dort', 4), ('üç', 3), ('uc', 3), ('iki', 2), ('bir', 1),
    ('sıfır', 0), ('sifir', 0),
]


def _sayi_sozcuklerini_cevir(metin: str) -> str:
    """'yüz yirmi beş' → '125'. Bitişik sayı gruplarını toplayarak birleştirir."""
    parcalar = metin.split()
    sonuc = []
    grup = []  # ardışık sayı kelimelerinin değerleri

    def _grubu_bosalt():
        if not grup:
            return
        # 100 + 20 + 5 = 125 (Türkçe sayı okunuşu toplamsaldır bu aralıkta)
        sonuc.append(str(sum(grup)))
        grup.clear()

    for parca in parcalar:
        temiz = parca.strip('.,;:!?')
        deger = None
        for kelime, sayi in _SAYI_KELIMELERI:
            if temiz == kelime:
                deger = sayi
                break
        if deger is not None:
            grup.append(deger)
        else:
            _grubu_bosalt()
            sonuc.append(parca)
    _grubu_bosalt()
    return ' '.join(sonuc)


def _guvenli_hesapla(node):
    """AST düğümünü özyinelemeli değerlendirir. İzinsiz düğümde hata verir."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Sadece sayı kullanılabilir.")
    if isinstance(node, ast.BinOp):
        op = _IZINLI_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Desteklenmeyen işlem.")
        return op(_guvenli_hesapla(node.left), _guvenli_hesapla(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _IZINLI_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Desteklenmeyen işlem.")
        return op(_guvenli_hesapla(node.operand))
    raise ValueError("Sadece matematik ifadeleri hesaplanabilir.")


def hesapla(ifade: str):
    """Matematik ifadesini güvenle hesaplar → (başarılı, mesaj)."""
    if not ifade:
        return False, "Hesaplanacak bir işlem bulamadım."

    temiz = ifade.lower().strip()
    temiz = _sayi_sozcuklerini_cevir(temiz)
    for kalip, sembol in _SOZEL_OPS:
        temiz = re.sub(kalip, sembol, temiz)
    temiz = temiz.replace('x', '*').replace('÷', '/').replace('×', '*').replace(',', '.')
    # Sadece matematik karakterlerini bırak
    temiz = re.sub(r'[^0-9\.\+\-\*/%\(\)\s]', '', temiz).strip()

    if not temiz:
        return False, "İşlemi anlayamadım. Örnek: `125*48 kaç eder`"

    try:
        agac = ast.parse(temiz, mode='eval')
        sonuc = _guvenli_hesapla(agac.body)
    except ZeroDivisionError:
        return False, "❌ Sıfıra bölme yapılamaz."
    except Exception:
        return False, f"İşlemi çözemedim: `{temiz}`"

    # Tam sayı sonuçları ondalık göstermeden yaz
    if isinstance(sonuc, float) and sonuc.is_integer():
        sonuc = int(sonuc)
    elif isinstance(sonuc, float):
        sonuc = round(sonuc, 6)

    return True, f"🧮 **{temiz} = {sonuc}**"


def hesap_niyeti_algila(mesaj: str):
    """Mesajdan hesaplanacak ifadeyi çıkarır → ifade veya None."""
    m = (mesaj or "").lower().strip()
    if not m:
        return None
    sade = _sadelestir(m)

    # Sözel operatör varsa veya sayı+operatör kalıbı varsa hesap isteğidir
    sozel_var = any(re.search(k, m) or re.search(k, sade) for k, _ in _SOZEL_OPS)
    sembol_var = re.search(r'\d\s*[\+\-\*/x×÷]\s*\d', m)
    if not (sozel_var or sembol_var):
        return None

    # Tarih/saat ifadelerini hesap sanma ("saat 10:30", "12.07.2026")
    if re.search(r'\d{1,2}[:.]\d{2}', m) and not sembol_var:
        return None
    # Hatırlatma/zamanlama cümleleri hesap değildir
    if any(k in sade for k in ['hatirlat', 'alarm', 'zamanla', 'sayac', 'dakika sonra']):
        return None

    return m


# ---------------------------------------------------------------------------
# SAAT / TARİH
# ---------------------------------------------------------------------------
_GUNLER = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
_AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
          'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']


def saat_tarih_raporu(mesaj: str = ""):
    """Gerçek sistem saatini/tarihini döndürür (LLM'e sorulmaz)."""
    now = datetime.now()
    m = _sadelestir(mesaj)
    gun_adi = _GUNLER[now.weekday()]
    ay_adi = _AYLAR[now.month - 1]

    sadece_saat = any(k in m for k in ['saat kac', 'saati soyle'])
    sadece_tarih = any(k in m for k in ['ayin kaci', 'hangi gun', 'bugun ne', 'tarih'])

    if sadece_saat and not sadece_tarih:
        return True, f"🕐 Saat **{now.strftime('%H:%M')}**"
    if sadece_tarih and not sadece_saat:
        return True, f"📅 Bugün **{now.day} {ay_adi} {now.year}, {gun_adi}**"
    return True, (f"🕐 Saat **{now.strftime('%H:%M')}** — "
                  f"📅 {now.day} {ay_adi} {now.year}, {gun_adi}")


def saat_tarih_niyeti_algila(mesaj: str) -> bool:
    m = _sadelestir(mesaj)
    if not m:
        return False
    return any(k in m for k in [
        'saat kac', 'saati soyle', 'saat ne',
        'bugun ayin kaci', 'ayin kaci', 'bugun gunlerden', 'hangi gundeyiz',
        'bugun hangi gun', 'bugunun tarihi', 'tarih ne',
    ])


# ---------------------------------------------------------------------------
# SAYAÇ / ZAMANLAYICI
# ---------------------------------------------------------------------------
_SAYI_SOZCUK = {
    'bir': 1, 'iki': 2, 'üç': 3, 'uc': 3, 'dört': 4, 'dort': 4, 'beş': 5, 'bes': 5,
    'altı': 6, 'alti': 6, 'yedi': 7, 'sekiz': 8, 'dokuz': 9, 'on': 10,
    'onbeş': 15, 'on beş': 15, 'yirmi': 20, 'otuz': 30, 'kırk': 40, 'kirk': 40,
    'elli': 50, 'altmış': 60, 'altmis': 60,
}


def sayac_niyeti_algila(mesaj: str):
    """Mesajdan sayaç süresini (dakika) çıkarır → float veya None."""
    m = _sadelestir(mesaj)
    if not m:
        return None

    sayac_kelimesi = any(k in m for k in [
        'sayac', 'zamanlayici', 'timer',
        'dakika sonra', 'saniye sonra', 'saat sonra', 'dakikaya kur',
    ])
    if not sayac_kelimesi:
        return None
    # "her gün 21:00" gibi tekrarlı zamanlamalar SCHEDULE_TASK'a ait
    if any(k in m for k in ['her gun', 'her sabah', 'her aksam', 'her hafta']):
        return None

    # "yarım saat" = 30 dk, "yarım dakika" = 30 sn — çarpan değil, yarısı
    if re.search(r'\byar[ıi]m\b', m):
        if 'saat' in m:
            return 30.0
        if 'saniye' in m:
            return 0.5 / 60.0
        return 0.5

    # Sayısal süre
    sayi = None
    eslesme = re.search(r'(\d+(?:[.,]\d+)?)\s*(saniye|dakika|dk|saat)', m)
    birim = 'dakika'
    if eslesme:
        sayi = float(eslesme.group(1).replace(',', '.'))
        birim = eslesme.group(2)
    else:
        # Sözel süre ("on dakika sonra")
        for kelime, deger in _SAYI_SOZCUK.items():
            if re.search(r'\b' + re.escape(kelime) + r'\b', m):
                sayi = float(deger)
                if 'saat' in m:
                    birim = 'saat'
                elif 'saniye' in m:
                    birim = 'saniye'
                break

    if sayi is None or sayi <= 0:
        return None

    if birim == 'saniye':
        return sayi / 60.0
    if birim == 'saat':
        return sayi * 60.0
    return sayi


def sayac_kur(cursor, conn, dakika: float, etiket: str = ""):
    """Sayacı hatırlatma olarak kaydeder → (başarılı, mesaj).

    Mevcut hatırlatma döngüsü bu kaydı görüp zamanı gelince bildirim gönderir.
    """
    try:
        dakika = float(dakika)
    except (TypeError, ValueError):
        return False, "Süreyi anlayamadım. Örnek: `5 dakika sayaç kur`"
    if dakika <= 0:
        return False, "Süre sıfırdan büyük olmalı."
    if dakika > 1440:
        return False, "Sayaç en fazla 24 saat olabilir. Daha uzunu için hatırlatma kurun."

    hedef = datetime.now() + timedelta(minutes=dakika)
    metin = etiket.strip() or "Sayaç doldu"

    try:
        cursor.execute("""
            INSERT INTO hatirlatmalar (metin, hedef_tarih, olusturma_tarihi, durum)
            VALUES (?, ?, ?, ?)
        """, (metin, hedef.strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'bekliyor'))
        conn.commit()
    except Exception as e:
        return False, f"Sayaç kurulamadı: {e}"

    if dakika < 1:
        sure_metni = f"{int(dakika * 60)} saniye"
    elif dakika == int(dakika):
        sure_metni = f"{int(dakika)} dakika"
    else:
        sure_metni = f"{dakika:g} dakika"

    return True, (f"⏳ **{sure_metni}** sayaç kuruldu.\n"
                  f"Zamanı geldiğinde haber vereceğim — saat **{hedef.strftime('%H:%M')}**.")


# ---------------------------------------------------------------------------
# NOT ALMA
# ---------------------------------------------------------------------------
NOT_TABLO_SQL = """
CREATE TABLE IF NOT EXISTS notlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metin TEXT NOT NULL,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _tabloyu_hazirla(cursor, conn):
    """Tablo yoksa oluşturur — eski veritabanları da çalışsın diye."""
    cursor.execute(NOT_TABLO_SQL)
    conn.commit()


def not_niyeti_algila(mesaj: str):
    """→ ('ekle', metin) | ('listele', None) | ('sil', None) | None"""
    ham = (mesaj or "").strip()
    m = _sadelestir(ham)
    if not m:
        return None

    if any(k in m for k in ['notlari goster', 'notlarimi goster', 'notlarim',
                            'notlari listele', 'ne not almistim', 'notlara bak']):
        return ('listele', None)
    if any(k in m for k in ['notlari sil', 'notlarimi sil', 'notlari temizle']):
        return ('sil', None)

    # Not ekleme: "not al: X", "not: X", "şunu not et X", "aklımda kalsın X"
    # İçerik HAM metinden alınır — Türkçe karakterler bozulmadan kaydedilsin.
    if any(k in m for k in ['not al', 'not et', 'nota ekle', 'not:']):
        eslesme = re.search(r'(?:not al|not et|nota ekle|not)\s*[:\-]?\s*(.+)',
                            ham, re.IGNORECASE)
        if eslesme:
            icerik = eslesme.group(1).strip()
            if icerik:
                return ('ekle', icerik)
    if 'aklimda kalsin' in m:
        eslesme2 = re.search(r'akl[ıi]mda kals[ıi]n\s*[:\-]?\s*(.+)',
                             ham, re.IGNORECASE)
        if eslesme2:
            icerik = eslesme2.group(1).strip()
            if icerik:
                return ('ekle', icerik)
    return None


def not_ekle(cursor, conn, metin: str):
    if not metin or not metin.strip():
        return False, "Boş not kaydedemem. Örnek: `not al: yarın fatura öde`"
    try:
        _tabloyu_hazirla(cursor, conn)
        cursor.execute("INSERT INTO notlar (metin, olusturma_tarihi) VALUES (?, ?)",
                       (metin.strip(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        return True, f"📝 Not kaydedildi: **{metin.strip()}**"
    except Exception as e:
        return False, f"Not kaydedilemedi: {e}"


def notlari_getir(cursor, conn, limit: int = 15):
    try:
        _tabloyu_hazirla(cursor, conn)
        cursor.execute("""
            SELECT metin, olusturma_tarihi FROM notlar
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        satirlar = cursor.fetchall()
    except Exception as e:
        return False, f"Notlar okunamadı: {e}"

    if not satirlar:
        return True, "📝 Henüz not almamışsınız. `not al: ...` diyerek başlayabilirsiniz."

    satir_metni = []
    for i, (metin, tarih) in enumerate(satirlar, 1):
        try:
            gosterim = datetime.strptime(tarih, '%Y-%m-%d %H:%M:%S').strftime('%d.%m %H:%M')
        except Exception:
            gosterim = str(tarih)[:16]
        satir_metni.append(f"{i}. {metin}  _({gosterim})_")

    return True, "📝 **Notlarınız:**\n" + "\n".join(satir_metni)


def notlari_sil(cursor, conn):
    try:
        _tabloyu_hazirla(cursor, conn)
        cursor.execute("SELECT COUNT(*) FROM notlar")
        adet = cursor.fetchone()[0]
        cursor.execute("DELETE FROM notlar")
        conn.commit()
        return True, f"🗑️ {adet} not silindi."
    except Exception as e:
        return False, f"Notlar silinemedi: {e}"
