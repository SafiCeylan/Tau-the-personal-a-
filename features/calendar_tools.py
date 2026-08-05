# -*- coding: utf-8 -*-
"""
ULTRON — TAKVİM

Üç parçadan oluşur:

  1. YEREL TAKVİM   `takvim_etkinlikleri` tablosu. Ekle / sil / sorgula.
                    İnternetsiz çalışır, tek doğru kaynağı kullanıcıdır.

  2. ICS ABONELİĞİ  Google Calendar / Outlook'un "gizli iCal adresi" okunur.
                    OAuth YOK, API anahtarı YOK — projenin keysiz servis
                    çizgisi (wttr.in, open-meteo, er-api) burada da korunur.
                    ⚠️ TEK YÖNLÜ: dış takvim OKUNUR, oraya YAZILMAZ. Yazma
                    yanılsaması yaratma — kullanıcı Google'da göremediği bir
                    etkinliği kaydolmuş sanır.

  3. ICS DIŞA AKTARIM  Yerel etkinlikler .ics dosyası olur; kullanıcı onu
                    telefonuna/Google'a kendi ekler.

NEDEN AYRI BİR TABLO (hatırlatmalar varken):
    Hatırlatma bir ANDIR ("14:00'te dürt"), etkinlik bir ARALIKTIR ("14:00-15:00
    toplantı"). Hatırlatmalar tablosuna süre/yer/kaynak eklemek onu iki işe birden
    koşmak olurdu. Bunun yerine köprü kuruldu: etkinlik eklenince `hatirlatmalar`
    tablosuna N dakika öncesine bir satır yazılır — böylece ETKİNLİK, hâlihazırda
    çalışan bildirim/Telegram/toast yolunu olduğu gibi kullanır. Yeni zamanlayıcı
    yazılmadı.
"""

import json
import os
import re
from datetime import date, datetime, timedelta

try:
    import requests
except ImportError:  # requests yoksa yerel takvim yine çalışır
    requests = None

from core.paths import veri_yolu

# Saat ayıklama REMINDERS'TAN alınır, kopyalanmaz. Aynı cümleyi ("cuma saat
# 9'da") iki ayrı ayrıştırıcının farklı yorumlaması, kullanıcının hatırlatması
# ile etkinliğinin farklı saatlere düşmesi demektir.
from features.reminders import _saat_ayikla, _gun_kaydirma

GUNLER = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
         'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

KAYNAK_YEREL = 'yerel'

# Senkron penceresi: bu aralığın dışındaki dış etkinlikler alınmaz.
# Yineleyen etkinlikleri sonsuza kadar açmamak için sınır ŞART.
GECMIS_GUN = 7
GELECEK_GUN = 365

# Etkinlikten kaç dakika önce hatırlatma kurulsun (config ile değişir, 0 = kapalı)
VARSAYILAN_HATIRLATMA_DK = 15

_ZAMAN_BICIM = '%Y-%m-%d %H:%M:%S'


# ---------------------------------------------------------------------------
# Türkçe metin sadeleştirme
# ---------------------------------------------------------------------------
# ⚠️ TUZAK: 'İ'.lower() Python'da 'i̇' (i + birleşen nokta) üretir — iki kod
# noktası. Bu yüzden önce translate, SONRA lower. Ters sırada "İstanbul" içeren
# cümleler hiçbir kalıba eşleşmez.
_HARF_TABLOSU = str.maketrans({
    'ı': 'i', 'İ': 'i', 'ş': 's', 'Ş': 's', 'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u', 'ö': 'o', 'Ö': 'o', 'ç': 'c', 'Ç': 'c',
})


def _sade(metin: str) -> str:
    """Kalıp eşleştirme için ASCII'ye indirgenmiş küçük harf."""
    return (metin or '').translate(_HARF_TABLOSU).lower().strip()


# Ay adları — sadeleştirilmiş biçimde aranır ("agustos", "subat")
_AY_ADLARI = {
    'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6,
    'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12,
}


def _config() -> dict:
    try:
        with open(veri_yolu('config.json'), 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# TABLO
# ---------------------------------------------------------------------------
_TABLO_SQL = """
CREATE TABLE IF NOT EXISTS takvim_etkinlikleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    baslik TEXT NOT NULL,
    baslangic TIMESTAMP NOT NULL,
    bitis TIMESTAMP,
    tum_gun INTEGER DEFAULT 0,
    yer TEXT,
    aciklama TEXT,
    kaynak TEXT DEFAULT 'yerel',
    dis_uid TEXT,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kaynak, dis_uid)
)
"""


def tabloyu_hazirla(cursor, conn=None) -> None:
    """
    Tabloyu garantiye alır.

    `schema.sql` zaten her açılışta çalışıyor; bu, modülü ondan BAĞIMSIZ kılmak
    için var (testler ve zamanlanmış görevler kendi bağlantılarını açıyor).
    """
    cursor.execute(_TABLO_SQL)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_takvim_baslangic "
                   "ON takvim_etkinlikleri(baslangic)")
    if conn is not None:
        conn.commit()


# ---------------------------------------------------------------------------
# TÜRKÇE TARİH ÇÖZÜMÜ
# ---------------------------------------------------------------------------
def _acik_tarih(sade: str, now: datetime):
    """
    Cümledeki AÇIK tarihi çözer → (date, eşleşen_metin) veya (None, None).

    Desteklenen: "15 agustos", "15 agustos 2026", "15.08", "15.08.2026",
                 "15/08/2026", "2026-08-15"
    """
    # 2026-08-15 (ISO)
    m = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', sade)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(0)
        except ValueError:
            pass

    # "15 agustos" / "15 agustos 2026"
    for ay_adi, ay_no in _AY_ADLARI.items():
        m = re.search(rf'\b(\d{{1,2}})\s+{ay_adi}\b(?:\s+(\d{{4}}))?', sade)
        if m:
            yil = int(m.group(2)) if m.group(2) else now.year
            try:
                bulunan = date(yil, ay_no, int(m.group(1)))
            except ValueError:
                continue
            # Yıl yazılmamış ve tarih geçmişte kalıyorsa gelecek yılı kastediyordur
            if not m.group(2) and bulunan < now.date():
                try:
                    bulunan = bulunan.replace(year=yil + 1)
                except ValueError:
                    pass
            return bulunan, m.group(0)

    # 15.08.2026 / 15/08/2026 / 15.08
    #
    # ⚠️ TUZAK — "14.05" hem 14 Mayıs hem 14:05 demektir. Türkçede saat NOKTAYLA
    # yazılır ("toplantı 14.30'da"), tarih ise genelde yılıyla ya da ay adıyla
    # yazılır. Bu yüzden nokta biçimi SADECE saat olamayacağı kesinse tarih
    # sayılır. Kural deterministiktir; tahmin edip yanlış güne etkinlik
    # yazmaktansa saat olarak okuyup kullanıcıya onay mesajında göstermek
    # yeğdir (kullanıcı "🕐 Bugün saat 14:05" satırını görüp düzeltebilir).
    m = re.search(r'\b(\d{1,2})([./])(\d{1,2})(?:[./](\d{2,4}))?\b', sade)
    if m:
        gun, ayirac, ay = int(m.group(1)), m.group(2), int(m.group(3))
        yil_txt = m.group(4)
        saat_olabilir = (ayirac == '.' and not yil_txt
                         and 0 <= gun <= 23 and 0 <= ay <= 59)
        if 1 <= gun <= 31 and 1 <= ay <= 12 and not saat_olabilir:
            if yil_txt:
                yil = int(yil_txt)
                if yil < 100:
                    yil += 2000
            else:
                yil = now.year
            try:
                bulunan = date(yil, ay, gun)
            except ValueError:
                return None, None
            if not yil_txt and bulunan < now.date():
                try:
                    bulunan = bulunan.replace(year=yil + 1)
                except ValueError:
                    pass
            return bulunan, m.group(0)

    return None, None


def tarih_coz(mesaj: str, now: datetime = None):
    """
    Cümleden etkinlik zamanını çıkarır.

    Dönen: {'baslangic': datetime, 'bitis': datetime|None, 'tum_gun': bool,
            'temizlenecek': [metin parçaları]}  veya  None

    Zaman ifadesi YOKSA None döner — "takvime toplantı ekle" gibi zamansız bir
    cümleyi bugüne kaydetmek sessiz bir yanlıştır; çağıran taraf kullanıcıya sorar.
    """
    now = now or datetime.now()
    sade = _sade(mesaj)
    temizlenecek = []

    # 1) Gün: açık tarih > göreli gün ifadesi
    hedef_gun, tarih_txt = _acik_tarih(sade, now)
    if hedef_gun:
        temizlenecek.append(tarih_txt)
    else:
        gun_farki, gun_txt = _gun_kaydirma(_sade_gun_metni(mesaj), now)
        if gun_farki is None:
            # "öbür gün" / "ertesi gün" — reminders bunları tanımıyor
            if re.search(r'\b(obur gun|ertesi gun)\b', sade):
                gun_farki, gun_txt = 2, 'öbür gün'
        if gun_farki is not None:
            hedef_gun = (now + timedelta(days=gun_farki)).date()
            if gun_txt:
                temizlenecek.append(gun_txt)

    # 2) Saat
    #
    # ⚠️ Saat, tarihin ÇIKARILDIĞI metinde aranır. Aksi hâlde "15.08.2026 10:30"
    # cümlesinde saat ayıklayıcı önce "15.08"i görüp saati 15:08 sanıyordu —
    # etkinlik doğru güne ama yanlış saate yazılıyordu.
    sade_saat = sade.replace(tarih_txt, ' ', 1) if tarih_txt else sade

    saat_bilgisi = _saat_ayikla(sade_saat)
    if not saat_bilgisi:
        # "akşam 8", "sabah 9" — çıplak sayı; reminders bu biçimi tanımıyor
        m = re.search(r'\b(sabah|ogle|oglen|aksam|gece)\s+(\d{1,2})\b(?!\s*[:.]\d)',
                      sade_saat)
        if m and 0 <= int(m.group(2)) <= 23:
            saat_bilgisi = (int(m.group(2)), 0, m.group(0))

    bitis = None

    if saat_bilgisi:
        h, mi, saat_txt = saat_bilgisi
        # "aksam 8" / "gece 11" → öğleden sonrayı kastediyor
        if h < 12 and re.search(r'\b(aksam|gece|ogleden sonra)\b', sade_saat):
            h += 12
        temizlenecek.append(saat_txt)

        if hedef_gun is None:
            hedef_gun = now.date()
            aday = datetime.combine(hedef_gun, datetime.min.time()).replace(hour=h, minute=mi)
            # Gün belirtilmemiş ve saat bugün için geçmişse yarını kastediyordur
            if aday <= now:
                hedef_gun = hedef_gun + timedelta(days=1)

        baslangic = datetime.combine(hedef_gun, datetime.min.time()).replace(hour=h, minute=mi)
        tum_gun = False

        # Bitiş saati: "14:00-16:00" veya "14:00 - 16:00"
        aralik = re.search(r'\b(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})\b',
                           sade_saat)
        if aralik:
            try:
                bitis = baslangic.replace(hour=int(aralik.group(3)),
                                          minute=int(aralik.group(4)))
                if bitis <= baslangic:
                    bitis += timedelta(days=1)
                temizlenecek.append(aralik.group(0))
            except ValueError:
                bitis = None

        # Süre: "2 saatlik", "90 dakikalik"
        if bitis is None:
            sure = re.search(r'\b(\d{1,3})\s*(saat|dakika|dk)\w*\b', sade_saat)
            if sure:
                miktar = int(sure.group(1))
                delta = (timedelta(hours=miktar) if sure.group(2) == 'saat'
                         else timedelta(minutes=miktar))
                bitis = baslangic + delta
                temizlenecek.append(sure.group(0))
    elif hedef_gun is not None:
        # Saat yok, gün var → tüm gün etkinliği
        baslangic = datetime.combine(hedef_gun, datetime.min.time())
        tum_gun = True
    else:
        return None

    return {'baslangic': baslangic, 'bitis': bitis, 'tum_gun': tum_gun,
            'temizlenecek': [p for p in temizlenecek if p]}


def _sade_gun_metni(mesaj: str) -> str:
    """
    `reminders._gun_kaydirma` TÜRKÇE karakterli kalıplar arar ('yarın', 'çarşamba').
    Bu yüzden ona sadeleştirilmiş değil, sadece küçük harfe indirilmiş metin verilir.
    """
    return (mesaj or '').replace('İ', 'i').lower()


# ---------------------------------------------------------------------------
# YEREL CRUD
# ---------------------------------------------------------------------------
def etkinlik_ekle(cursor, conn, baslik: str, baslangic: datetime,
                  bitis: datetime = None, tum_gun: bool = False,
                  yer: str = None, aciklama: str = None,
                  kaynak: str = KAYNAK_YEREL, dis_uid: str = None,
                  hatirlatma_dk: int = None):
    """
    Etkinlik kaydeder. Dönen: (id, hatırlatma_kuruldu_mu)

    Bitiş verilmemiş saatli etkinlikler 1 saat sayılır (takvim yazılımlarının
    standardı) — böylece "bu saatte meşgul müyüm" sorusu anlamlı cevap verir.
    """
    tabloyu_hazirla(cursor, conn)

    if bitis is None and not tum_gun:
        bitis = baslangic + timedelta(hours=1)

    cursor.execute("""
        INSERT OR REPLACE INTO takvim_etkinlikleri
            (baslik, baslangic, bitis, tum_gun, yer, aciklama, kaynak, dis_uid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (baslik.strip(), baslangic.strftime(_ZAMAN_BICIM),
          bitis.strftime(_ZAMAN_BICIM) if bitis else None,
          1 if tum_gun else 0, yer, aciklama, kaynak, dis_uid))
    yeni_id = cursor.lastrowid

    hatirlatma_kuruldu = False
    if kaynak == KAYNAK_YEREL:
        hatirlatma_kuruldu = _hatirlatma_kopru(cursor, baslik, baslangic,
                                               tum_gun, hatirlatma_dk)
    conn.commit()
    return yeni_id, hatirlatma_kuruldu


def _hatirlatma_kopru(cursor, baslik: str, baslangic: datetime,
                      tum_gun: bool, hatirlatma_dk: int = None) -> bool:
    """
    Etkinliğin N dakika öncesine `hatirlatmalar` tablosuna satır yazar.

    Böylece etkinlik, hâlihazırda çalışan bildirim yolunu (toast + Telegram +
    ön-uyarı) olduğu gibi kullanır. GEÇMİŞTE kalan hedefe hatırlatma kurulmaz —
    kurulursa otonom döngü onu "gecikmiş" sayıp anında bildirir.
    """
    if hatirlatma_dk is None:
        try:
            hatirlatma_dk = int(_config().get('takvim_hatirlatma_dk',
                                              VARSAYILAN_HATIRLATMA_DK))
        except (TypeError, ValueError):
            hatirlatma_dk = VARSAYILAN_HATIRLATMA_DK
    if hatirlatma_dk <= 0:
        return False

    # Tüm gün etkinliğinde "00:00'dan 15 dk önce" anlamsız → sabah 09:00'a kur
    hedef = (baslangic.replace(hour=9, minute=0) if tum_gun
             else baslangic - timedelta(minutes=hatirlatma_dk))
    if hedef <= datetime.now():
        return False

    try:
        cursor.execute("""
            INSERT INTO hatirlatmalar (metin, hedef_tarih, olusturma_tarihi, durum)
            VALUES (?, ?, ?, 'bekliyor')
        """, (f"📅 {baslik.strip()}", hedef.strftime(_ZAMAN_BICIM),
              datetime.now().strftime(_ZAMAN_BICIM)))
        return True
    except Exception as e:
        # Hatırlatma kurulamadıysa etkinlik YİNE DE kaydedilmiş olmalı
        print(f"[ULTRON Takvim] Hatirlatma koprusu kurulamadi: {e}")
        return False


def etkinlik_sil(cursor, conn, etkinlik_id: int) -> str:
    tabloyu_hazirla(cursor, conn)
    cursor.execute("SELECT baslik, kaynak FROM takvim_etkinlikleri WHERE id = ?",
                   (etkinlik_id,))
    satir = cursor.fetchone()
    if not satir:
        return f"⚠️ #{etkinlik_id} numaralı etkinlik bulunamadı."

    baslik, kaynak = satir[0], satir[1]
    if kaynak != KAYNAK_YEREL:
        # Dış takvimden gelen satırı silmek işe yaramaz: sonraki senkron geri
        # getirir. Kullanıcıya "sildim" demek yalan olur.
        return (f"⚠️ **{baslik}** dış takvimden (`{kaynak}`) geliyor. "
                f"Buradan silsem bir sonraki senkronda geri gelir — "
                f"onu Google/Outlook tarafında silmen gerekiyor.")

    cursor.execute("DELETE FROM takvim_etkinlikleri WHERE id = ?", (etkinlik_id,))
    conn.commit()
    return f"🗑️ **{baslik}** takvimden silindi."


def etkinlikleri_getir(cursor, baslangic: datetime, bitis: datetime, limit: int = 50):
    """[baslangic, bitis) aralığındaki etkinlikler — başlangıç saatine göre sıralı."""
    tabloyu_hazirla(cursor)
    cursor.execute("""
        SELECT id, baslik, baslangic, bitis, tum_gun, yer, kaynak
        FROM takvim_etkinlikleri
        WHERE baslangic >= ? AND baslangic < ?
        ORDER BY baslangic
        LIMIT ?
    """, (baslangic.strftime(_ZAMAN_BICIM), bitis.strftime(_ZAMAN_BICIM), limit))
    return cursor.fetchall()


def sonraki_etkinlik(cursor, now: datetime = None):
    """Şu andan sonraki ilk etkinlik (yoksa None)."""
    now = now or datetime.now()
    tabloyu_hazirla(cursor)
    cursor.execute("""
        SELECT id, baslik, baslangic, bitis, tum_gun, yer, kaynak
        FROM takvim_etkinlikleri
        WHERE baslangic >= ?
        ORDER BY baslangic LIMIT 1
    """, (now.strftime(_ZAMAN_BICIM),))
    return cursor.fetchone()


# ---------------------------------------------------------------------------
# BİÇİMLENDİRME
# ---------------------------------------------------------------------------
def _gun_etiketi(d: date, now: datetime = None) -> str:
    now = now or datetime.now()
    fark = (d - now.date()).days
    if fark == 0:
        return "Bugün"
    if fark == 1:
        return "Yarın"
    if fark == -1:
        return "Dün"
    return f"{d.day} {AYLAR[d.month - 1]} {GUNLER[d.weekday()]}"


def etkinlikleri_bicimle(satirlar, baslik: str, now: datetime = None) -> str:
    """Etkinlik listesini güne göre gruplayarak yazar."""
    if not satirlar:
        return f"📅 **{baslik}** — kayıtlı etkinlik yok."

    now = now or datetime.now()
    gruplar = {}
    for sid, e_baslik, bas, bit, tum_gun, yer, kaynak in satirlar:
        try:
            bas_dt = datetime.strptime(bas, _ZAMAN_BICIM)
        except (TypeError, ValueError):
            continue
        gruplar.setdefault(bas_dt.date(), []).append(
            (sid, e_baslik, bas_dt, bit, tum_gun, yer, kaynak))

    parcalar = [f"📅 **{baslik}**"]
    for gun in sorted(gruplar):
        gun_basligi = _gun_etiketi(gun, now)
        # "Yarın" başlığının altına yine "Yarın" yazmak gereksiz gürültü
        if not (len(gruplar) == 1 and gun_basligi == baslik):
            parcalar.append(f"\n**{gun_basligi}**")
        for sid, e_baslik, bas_dt, bit, tum_gun, yer, kaynak in gruplar[gun]:
            if tum_gun:
                zaman = "tüm gün"
            else:
                zaman = bas_dt.strftime('%H:%M')
                if bit:
                    try:
                        zaman += "–" + datetime.strptime(bit, _ZAMAN_BICIM).strftime('%H:%M')
                    except (TypeError, ValueError):
                        pass
            satir = f"• **#{sid}** `{zaman}` — {e_baslik}"
            if yer:
                satir += f" _({yer})_"
            if kaynak and kaynak != KAYNAK_YEREL:
                # Kaynağı göstermek süs değil: kullanıcı neyi buradan
                # silebileceğini, neyi Google'dan silmesi gerektiğini görmeli.
                satir += f" ⟨{kaynak.replace('ics:', '')}⟩"
            parcalar.append(satir)
    return "\n".join(parcalar)


# ---------------------------------------------------------------------------
# ICS AYRIŞTIRMA
# ---------------------------------------------------------------------------
def _satirlari_ac(metin: str):
    """RFC 5545 satır katlaması: devam satırı boşluk/tab ile başlar."""
    sonuc = []
    for ham in (metin or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if ham[:1] in (' ', '\t') and sonuc:
            sonuc[-1] += ham[1:]
        else:
            sonuc.append(ham)
    return sonuc


def _satir_coz(satir: str):
    """'DTSTART;TZID=Europe/Istanbul:20260815T140000' → ('DTSTART', {...}, '2026...')"""
    tirnak_ici = False
    for i, ch in enumerate(satir):
        if ch == '"':
            tirnak_ici = not tirnak_ici
        elif ch == ':' and not tirnak_ici:
            sol, deger = satir[:i], satir[i + 1:]
            break
    else:
        return None, {}, ''

    parcalar = sol.split(';')
    ad = parcalar[0].strip().upper()
    parametreler = {}
    for p in parcalar[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            parametreler[k.strip().upper()] = v.strip().strip('"')
    return ad, parametreler, deger


def _metni_coz(deger: str) -> str:
    r"""ICS kaçışlarını çözer: \n \, \; \\ """
    return (deger or '').replace('\\N', '\n').replace('\\n', '\n') \
                        .replace('\\,', ',').replace('\\;', ';') \
                        .replace('\\\\', '\\').strip()


def _zaman_coz(deger: str, parametreler: dict):
    """
    ICS zaman değerini YEREL saatli datetime'a çevirir → (datetime, tum_gun)

    ⚠️ 'Z' eki UTC demektir ve ÇEVİRMEK ZORUNLUDUR. Çevirmezsek Türkiye'de her
    toplantı 3 saat kaymış görünür — takvim özelliğini işe yaramaz hâle getiren
    tam olarak budur. TZID'li değerlerde tzdata her Windows'ta bulunmaz; o
    durumda değer YEREL kabul edilir (Türkçe bir takvimde doğru varsayım).
    """
    deger = (deger or '').strip()

    if parametreler.get('VALUE') == 'DATE' or re.fullmatch(r'\d{8}', deger):
        try:
            return datetime.strptime(deger[:8], '%Y%m%d'), True
        except ValueError:
            return None, False

    m = re.fullmatch(r'(\d{8})T(\d{6})(Z?)', deger)
    if not m:
        return None, False
    try:
        naive = datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M%S')
    except ValueError:
        return None, False

    if m.group(3) == 'Z':
        from datetime import timezone
        return naive.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None), False

    tzid = parametreler.get('TZID')
    if tzid:
        try:
            from zoneinfo import ZoneInfo
            return naive.replace(tzinfo=ZoneInfo(tzid)).astimezone().replace(tzinfo=None), False
        except Exception:
            pass  # tzdata yok → yerel kabul et
    return naive, False


_ICS_GUN_KODU = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}


def _rrule_coz(deger: str) -> dict:
    kurallar = {}
    for parca in (deger or '').split(';'):
        if '=' in parca:
            k, v = parca.split('=', 1)
            kurallar[k.strip().upper()] = v.strip()
    return kurallar


def _tekrari_ac(baslangic: datetime, rrule: dict, pencere_bas: datetime,
                pencere_son: datetime, haric: set, azami: int = 400):
    """
    Yineleyen etkinliği pencere içindeki tekil tarihlere açar.

    Desteklenen: FREQ=DAILY/WEEKLY/MONTHLY/YEARLY + INTERVAL, COUNT, UNTIL,
    BYDAY (haftalık). Desteklenmeyen kural varsa sadece ilk tarih döner —
    UYDURMAKTANSA EKSİK GÖSTER: yanlış günde toplantı bildirmek, hiç
    bildirmemekten kötüdür.
    """
    freq = (rrule.get('FREQ') or '').upper()
    if freq not in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'):
        return [baslangic]

    try:
        aralik = max(1, int(rrule.get('INTERVAL', 1)))
    except (TypeError, ValueError):
        aralik = 1

    sayi_siniri = None
    if rrule.get('COUNT'):
        try:
            sayi_siniri = int(rrule['COUNT'])
        except (TypeError, ValueError):
            sayi_siniri = None

    son_tarih = pencere_son
    if rrule.get('UNTIL'):
        bitis_dt, _ = _zaman_coz(rrule['UNTIL'], {})
        if bitis_dt:
            son_tarih = min(son_tarih, bitis_dt)

    gunler = []
    if freq == 'WEEKLY' and rrule.get('BYDAY'):
        for kod in rrule['BYDAY'].split(','):
            kod = kod.strip().upper()[-2:]
            if kod in _ICS_GUN_KODU:
                gunler.append(_ICS_GUN_KODU[kod])

    tarihler = []
    imlec = baslangic
    uretilen = 0
    while imlec <= son_tarih and uretilen < azami:
        if freq == 'WEEKLY' and gunler:
            # Haftanın başına git, seçili günleri üret
            hafta_basi = imlec - timedelta(days=imlec.weekday())
            for g in sorted(gunler):
                aday = hafta_basi + timedelta(days=g)
                if aday < baslangic or aday > son_tarih:
                    continue
                if aday >= pencere_bas and aday.strftime('%Y%m%d') not in haric:
                    tarihler.append(aday)
                uretilen += 1
                if sayi_siniri and uretilen >= sayi_siniri:
                    break
            imlec = hafta_basi + timedelta(weeks=aralik)
        else:
            if imlec >= pencere_bas and imlec.strftime('%Y%m%d') not in haric:
                tarihler.append(imlec)
            uretilen += 1
            if freq == 'DAILY':
                imlec += timedelta(days=aralik)
            elif freq == 'WEEKLY':
                imlec += timedelta(weeks=aralik)
            elif freq == 'MONTHLY':
                imlec = _ay_ekle(imlec, aralik)
            else:
                imlec = _ay_ekle(imlec, 12 * aralik)

        if sayi_siniri and uretilen >= sayi_siniri:
            break
    return tarihler


def _ay_ekle(d: datetime, ay: int) -> datetime:
    """Ay ekler; ayın 31'i olmayan aylarda son güne kırpar."""
    toplam = d.month - 1 + ay
    yil = d.year + toplam // 12
    yeni_ay = toplam % 12 + 1
    gun = d.day
    while gun > 0:
        try:
            return d.replace(year=yil, month=yeni_ay, day=gun)
        except ValueError:
            gun -= 1
    return d


def ics_ayristir(metin: str, pencere_bas: datetime = None,
                 pencere_son: datetime = None):
    """
    ICS metnini etkinlik sözlüklerine çevirir.

    Dönen: [{'baslik','baslangic','bitis','tum_gun','yer','aciklama','uid'}, ...]
    Ayrıştırılamayan tek bir etkinlik TÜM dosyayı düşürmemeli — her VEVENT
    kendi try'ında işlenir.
    """
    now = datetime.now()
    pencere_bas = pencere_bas or (now - timedelta(days=GECMIS_GUN))
    pencere_son = pencere_son or (now + timedelta(days=GELECEK_GUN))

    etkinlikler = []
    icinde = False
    alan = {}

    for satir in _satirlari_ac(metin):
        duz = satir.strip()
        if duz.upper() == 'BEGIN:VEVENT':
            icinde, alan = True, {'haric': set()}
            continue
        if duz.upper() == 'END:VEVENT':
            if icinde:
                try:
                    etkinlikler.extend(_vevent_cevir(alan, pencere_bas, pencere_son))
                except Exception as e:
                    print(f"[ULTRON Takvim] VEVENT atlandi: {type(e).__name__}: {e}")
            icinde, alan = False, {}
            continue
        if not icinde or not duz:
            continue

        ad, parametreler, deger = _satir_coz(duz)
        if ad == 'SUMMARY':
            alan['baslik'] = _metni_coz(deger)
        elif ad == 'DTSTART':
            alan['baslangic'], alan['tum_gun'] = _zaman_coz(deger, parametreler)
        elif ad == 'DTEND':
            alan['bitis'], _ = _zaman_coz(deger, parametreler)
        elif ad == 'LOCATION':
            alan['yer'] = _metni_coz(deger)
        elif ad == 'DESCRIPTION':
            alan['aciklama'] = _metni_coz(deger)
        elif ad == 'UID':
            alan['uid'] = deger.strip()
        elif ad == 'RRULE':
            alan['rrule'] = _rrule_coz(deger)
        elif ad == 'EXDATE':
            for p in deger.split(','):
                alan['haric'].add(p.strip()[:8])

    return etkinlikler


def _vevent_cevir(alan: dict, pencere_bas: datetime, pencere_son: datetime):
    baslangic = alan.get('baslangic')
    if not baslangic or not alan.get('baslik'):
        return []

    uid = alan.get('uid') or f"{alan['baslik']}-{baslangic:%Y%m%d%H%M}"
    sure = None
    if alan.get('bitis'):
        sure = alan['bitis'] - baslangic

    if alan.get('rrule'):
        tarihler = _tekrari_ac(baslangic, alan['rrule'], pencere_bas,
                               pencere_son, alan.get('haric') or set())
        cogul = True
    else:
        tarihler = [baslangic] if pencere_bas <= baslangic <= pencere_son else []
        cogul = False

    sonuc = []
    for t in tarihler:
        sonuc.append({
            'baslik': alan['baslik'],
            'baslangic': t,
            'bitis': (t + sure) if sure else None,
            'tum_gun': bool(alan.get('tum_gun')),
            'yer': alan.get('yer'),
            'aciklama': alan.get('aciklama'),
            # Yinelenen etkinliğin her tekrarı AYRI satırdır → uid'e tarih eklenir,
            # yoksa UNIQUE(kaynak, dis_uid) hepsini tek satıra ezer.
            'uid': f"{uid}#{t:%Y%m%d}" if cogul else uid,
        })
    return sonuc


# ---------------------------------------------------------------------------
# ICS SENKRON
# ---------------------------------------------------------------------------
def ics_kaynaklari():
    """config'ten ICS adreslerini okur. Tek metin ya da liste olabilir."""
    ham = _config().get('takvim_ics_url') or []
    if isinstance(ham, str):
        ham = [p.strip() for p in ham.split(',')]
    return [p for p in ham if p and str(p).strip()]


def _ics_indir(adres: str) -> str:
    """ICS içeriğini getirir. Yerel dosya yolu da kabul edilir."""
    if os.path.exists(adres):
        with open(adres, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    if requests is None:
        raise RuntimeError("requests kurulu değil")
    # webcal:// Google/Apple'ın verdiği şema — https ile aynı adrestir
    if adres.startswith('webcal://'):
        adres = 'https://' + adres[len('webcal://'):]
    cevap = requests.get(adres, timeout=20, headers={'User-Agent': 'ULTRON/3.0'})
    cevap.raise_for_status()
    return cevap.text


def _kaynak_adi(adres: str, sira: int) -> str:
    """ICS adresinden kısa, kararlı bir kaynak etiketi üretir."""
    if os.path.exists(adres):
        return f"ics:{os.path.splitext(os.path.basename(adres))[0][:24]}"
    try:
        from urllib.parse import urlparse
        alan = urlparse(adres).netloc.split(':')[0]
        if alan:
            return f"ics:{alan.replace('www.', '')[:24]}"
    except Exception:
        pass
    return f"ics:takvim{sira + 1}"


def ics_senkronize(cursor, conn, adresler=None):
    """
    Yapılandırılmış ICS adreslerini çeker ve yerel tabloya yazar.

    Dönen: (toplam_etkinlik, [hata mesajları])

    Strateji: her kaynağın ESKİ satırları silinip yenisi yazılır. Dış takvim
    orada tek doğru kaynaktır — birleştirmeye çalışmak, Google'dan silinen bir
    toplantının Ultron'da sonsuza kadar yaşaması demektir.
    ⚠️ Silme `kaynak` ile sınırlıdır; 'yerel' satırlara ASLA dokunulmaz.
    """
    adresler = adresler if adresler is not None else ics_kaynaklari()
    if not adresler:
        return 0, []

    tabloyu_hazirla(cursor, conn)
    now = datetime.now()
    pencere_bas = now - timedelta(days=GECMIS_GUN)
    pencere_son = now + timedelta(days=GELECEK_GUN)

    toplam, hatalar = 0, []
    for sira, adres in enumerate(adresler):
        kaynak = _kaynak_adi(adres, sira)
        try:
            metin = _ics_indir(adres)
            etkinlikler = ics_ayristir(metin, pencere_bas, pencere_son)
        except Exception as e:
            hatalar.append(f"{kaynak}: {type(e).__name__}")
            continue

        # Kaynağın eski satırlarını temizle (yerel kayıtlara dokunmadan)
        cursor.execute("DELETE FROM takvim_etkinlikleri WHERE kaynak = ?", (kaynak,))
        for e in etkinlikler:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO takvim_etkinlikleri
                        (baslik, baslangic, bitis, tum_gun, yer, aciklama, kaynak, dis_uid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (e['baslik'], e['baslangic'].strftime(_ZAMAN_BICIM),
                      e['bitis'].strftime(_ZAMAN_BICIM) if e['bitis'] else None,
                      1 if e['tum_gun'] else 0, e['yer'], e['aciklama'],
                      kaynak, e['uid']))
                toplam += 1
            except Exception as ie:
                print(f"[ULTRON Takvim] Etkinlik yazilamadi: {ie}")
        conn.commit()

    return toplam, hatalar


# ---------------------------------------------------------------------------
# ICS DIŞA AKTARIM
# ---------------------------------------------------------------------------
def _ics_kacir(metin: str) -> str:
    return (metin or '').replace('\\', '\\\\').replace(';', '\\;') \
                        .replace(',', '\\,').replace('\n', '\\n')


def ics_disa_aktar(cursor, hedef_yol: str = None, gun: int = 365) -> str:
    """Yerel etkinlikleri .ics dosyasına yazar → dosya yolu."""
    tabloyu_hazirla(cursor)
    now = datetime.now()
    cursor.execute("""
        SELECT id, baslik, baslangic, bitis, tum_gun, yer, aciklama
        FROM takvim_etkinlikleri
        WHERE kaynak = ? AND baslangic >= ?
        ORDER BY baslangic
    """, (KAYNAK_YEREL, (now - timedelta(days=gun)).strftime(_ZAMAN_BICIM)))
    satirlar = cursor.fetchall()

    parcalar = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//ULTRON//Neural Core 3.0//TR',
                'CALSCALE:GREGORIAN']
    for sid, baslik, bas, bit, tum_gun, yer, aciklama in satirlar:
        try:
            bas_dt = datetime.strptime(bas, _ZAMAN_BICIM)
        except (TypeError, ValueError):
            continue
        parcalar.append('BEGIN:VEVENT')
        parcalar.append(f'UID:ultron-{sid}@localhost')
        parcalar.append(f'DTSTAMP:{now:%Y%m%dT%H%M%S}')
        if tum_gun:
            parcalar.append(f'DTSTART;VALUE=DATE:{bas_dt:%Y%m%d}')
            parcalar.append(f'DTEND;VALUE=DATE:{bas_dt + timedelta(days=1):%Y%m%d}')
        else:
            parcalar.append(f'DTSTART:{bas_dt:%Y%m%dT%H%M%S}')
            if bit:
                try:
                    parcalar.append(
                        f'DTEND:{datetime.strptime(bit, _ZAMAN_BICIM):%Y%m%dT%H%M%S}')
                except (TypeError, ValueError):
                    pass
        parcalar.append(f'SUMMARY:{_ics_kacir(baslik)}')
        if yer:
            parcalar.append(f'LOCATION:{_ics_kacir(yer)}')
        if aciklama:
            parcalar.append(f'DESCRIPTION:{_ics_kacir(aciklama)}')
        parcalar.append('END:VEVENT')
    parcalar.append('END:VCALENDAR')

    hedef_yol = hedef_yol or _varsayilan_ics_yolu(now)
    with open(hedef_yol, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\r\n'.join(parcalar))
    return hedef_yol


def _varsayilan_ics_yolu(now: datetime = None) -> str:
    """
    Dışa aktarımın varsayılan hedefi (Masaüstü).

    Ayrı fonksiyon: test zırhı burayı yamalayıp geçici dizine yönlendiriyor —
    yoksa dışa aktarımı çağıran her test kullanıcının Masaüstüne dosya bırakır.
    """
    now = now or datetime.now()
    masaustu = os.path.join(os.path.expanduser('~'), 'Desktop')
    if not os.path.isdir(masaustu):
        masaustu = os.path.dirname(veri_yolu('config.json'))
    return os.path.join(masaustu, f"ultron_takvim_{now:%Y%m%d}.ics")


# ---------------------------------------------------------------------------
# DOĞAL DİL — NİYET KAPISI
# ---------------------------------------------------------------------------
# ⚠️ Bu kapı niyet zincirinde DOSYA niyetinden ÖNCE sorulur (bkz.
# pipeline_layers). Sebep `LEARNING_REPORT` ile birebir aynı: "takvimi göster"
# cümlesindeki "göster" fiili `_ARAMA_FIILLERI` içinde var; 134 bin dosyalık
# indekste "takvim" adlı bir dosya bulunursa komut dosya aramasına kaçar.
# Bu yüzden kapı DAR olmak zorunda — yalnızca açık takvim işaretleri.

_TAKVIM_KELIMELERI = ('takvim', 'ajanda')

_ETKINLIK_KELIMELERI = (
    'etkinlik', 'randevu', 'toplanti', 'bulusma', 'konser', 'sinav', 'vize',
    'final', 'dogum gunu', 'yildonumu', 'ucus', 'mulakat', 'seminer', 'nobet',
)

# "yarın ne var" gibi takvim kelimesi geçmeyen gündem soruları
_GUNDEM_SORUSU = re.compile(
    r'\b(bugun|yarin|obur gun|ertesi gun|bu hafta|haftaya|gelecek hafta|hafta sonu|'
    r'bu ay|pazartesi|sali|carsamba|persembe|cuma|cumartesi|pazar)\b'
    r'[^?]*\b(ne var|neler var|ne isim var|programim|planim|planlarim|'
    r'mesgul muyum|musait miyim|isim var mi)\b'
)

# Başkasının işi olan cümleler — takvim bunlara ASLA el koymaz
_BASKASININ_ISI = re.compile(r'\b(hatirlat|alarm|sayac|kronometre)\b')
_ZAMANLAYICI_ISI = re.compile(r'\bzamanla\b|\bher\s+(gun|sabah|aksam)\b.*\d{1,2}[:.]\d{2}')

# Yineleyen etkinlik ("her salı toplantı") — v1'de yerel yineleme YOK
_YINELEME = re.compile(r'\bher\s+(gun|hafta|ay|pazartesi|sali|carsamba|persembe|'
                       r'cuma|cumartesi|pazar|sabah|aksam)\b')

_SENKRON_RE = re.compile(r'takvim\w*\s+(senkron\w*|guncelle|yenile|cek|es[iy]tle)|'
                         r'(senkron\w*|guncelle|yenile)\s+takvim')
_DISA_AKTAR_RE = re.compile(r'takvim\w*\s+(disa aktar|disari aktar|ics|disa ver|yedekle)|'
                            r'(disa aktar|yedekle)\s+takvim')
# Silme fiili + numara. Numarayı fiile YAKINLIK kuralıyla bağlamayı denedim,
# "takvimden 1 numaralı etkinliği sil" gibi araya kelime giren doğal cümleleri
# kaçırıyordu. Bu katman yalnızca CALENDAR niyetinde çalıştığı için fiil +
# numaranın aynı cümlede olması yeterli ve güvenli.
_SIL_FIILI = re.compile(r'\b(sil|kaldir|iptal)\w*\b')
_NUMARA_RE = re.compile(r'#?(\d{1,4})\b')
_EKLE_FIILI = re.compile(r'\b(ekle|kaydet|koy|olustur|gir|yaz)\b')
_SONRAKI_RE = re.compile(r'\b(sonraki|bir sonraki|siradaki|ilk)\b.*'
                         r'\b(etkinlik|toplanti|randevu|isim|program)')


def takvim_niyeti_algila(mesaj: str) -> bool:
    """Bu cümle takvim komutu mu? (Niyet katmanının sorduğu tek soru.)"""
    s = _sade(mesaj)
    if not s:
        return False

    # Açıkça başka bir modülün fiili varsa el koyma. Kullanıcı "hatırlat"
    # dediyse hatırlatma ister; takvime yazıp susmak komutu sessizce değiştirmektir.
    if _BASKASININ_ISI.search(s) or _ZAMANLAYICI_ISI.search(s):
        return False

    if any(k in s for k in _TAKVIM_KELIMELERI):
        return True
    if _GUNDEM_SORUSU.search(s):
        return True
    if _SONRAKI_RE.search(s):
        return True
    # "yarın 14:00 diş randevusu ekle" — etkinlik adı + ekleme fiili
    if any(k in s for k in _ETKINLIK_KELIMELERI) and (
            _EKLE_FIILI.search(s) or re.search(r'\bvar\b', s)):
        return True
    return False


# ---------------------------------------------------------------------------
# DOĞAL DİL — SORGU ARALIĞI
# ---------------------------------------------------------------------------
def aralik_coz(mesaj: str, now: datetime = None):
    """Sorgu cümlesinden (başlangıç, bitiş, etiket) üretir."""
    now = now or datetime.now()
    s = _sade(mesaj)
    bugun = datetime.combine(now.date(), datetime.min.time())

    if 'hafta sonu' in s:
        cumartesi = bugun + timedelta(days=(5 - bugun.weekday()) % 7)
        return cumartesi, cumartesi + timedelta(days=2), "Hafta sonu"
    if 'gelecek hafta' in s or 'haftaya' in s:
        gelecek_pzt = bugun + timedelta(days=7 - bugun.weekday())
        return gelecek_pzt, gelecek_pzt + timedelta(days=7), "Gelecek hafta"
    if 'bu hafta' in s:
        return bugun, bugun + timedelta(days=7 - bugun.weekday()), "Bu hafta"
    if 'bu ay' in s:
        ay_sonu = _ay_ekle(bugun.replace(day=1), 1)
        return bugun, ay_sonu, "Bu ay"
    if 'yarin' in s:
        return bugun + timedelta(days=1), bugun + timedelta(days=2), "Yarın"
    if re.search(r'\b(obur gun|ertesi gun)\b', s):
        return bugun + timedelta(days=2), bugun + timedelta(days=3), "Öbür gün"
    if 'bugun' in s or 'bu aksam' in s:
        return bugun, bugun + timedelta(days=1), "Bugün"

    # Açık tarih ya da gün adı ("cuma ne var")
    cozum = tarih_coz(mesaj, now)
    if cozum and cozum['tum_gun']:
        gun = cozum['baslangic']
        return gun, gun + timedelta(days=1), _gun_etiketi(gun.date(), now)

    return bugun, bugun + timedelta(days=7), "Önümüzdeki 7 gün"


# Sadeleştirmenin TERSİ: 's' hem 's' hem 'ş' olabilir.
_GERI_FOLD = {
    'i': '[iıIİ]', 's': '[sşSŞ]', 'g': '[gğGĞ]',
    'u': '[uüUÜ]', 'o': '[oöOÖ]', 'c': '[cçCÇ]',
}


def _sade_kalip(parca: str) -> str:
    """
    Sadeleştirilmiş bir parçadan, HAM metinde de eşleşen regex üretir.

    ⚠️ Bu fonksiyon olmadan başlık temizliği SESSİZCE çalışmıyordu: zaman
    parçaları sade metinden ("aksam 8", "15 agustos") çıkıyor ama ham metinde
    Türkçe harfle yazılı ("akşam 8", "15 ağustos"). `re.escape` ile aranınca
    hiçbiri eşleşmiyor ve etkinlik "akşam 8 Ahmet ile yemek" adıyla
    kaydediliyordu. (CLAUDE.md'deki `sadelestir & Türkçe` tuzağının aynası.)
    """
    parcalar = []
    for ch in parca:
        if ch.isspace():
            parcalar.append(r'\s+')
        elif ch in _GERI_FOLD:
            parcalar.append(_GERI_FOLD[ch])
        else:
            parcalar.append(re.escape(ch))
    return ''.join(parcalar)


def _baslik_temizle(ham: str, temizlenecek) -> str:
    """
    Cümleden zaman ifadelerini ve komut fiillerini atıp etkinlik adını bırakır.

    Başlık HAM metinden üretilir (sadeleştirilmişten değil) — kullanıcının
    Türkçe harfleri takvimde bozulmuş görünmesin.
    """
    metin = ham or ''
    for parca in sorted(temizlenecek or [], key=len, reverse=True):
        if not parca:
            continue
        metin = re.sub(_sade_kalip(parca), ' ', metin, flags=re.IGNORECASE)

    metin = re.sub(r'\btakvim\w*\b|\bajanda\w*\b', ' ', metin, flags=re.IGNORECASE)
    metin = re.sub(r'\b(ekle|kaydet|koy|olu[sş]tur|gir|yaz|var|saat|de|da|te|ta|g[uü]n[uü]|ara[sş][ıi])\b',
                   ' ', metin, flags=re.IGNORECASE)
    metin = re.sub(r'^\s*[:\-–]\s*', ' ', metin)
    metin = re.sub(r'\s+', ' ', metin).strip(" ,.;:'’\"-–")
    return metin


def takvim_komutu_algila(mesaj: str, cursor=None, conn=None, now: datetime = None):
    """
    Takvim komutunu çalıştırır. Dönen: (işlendi_mi, yanıt)

    `islendi=False` → cümle takvim komutu değil, akış LLM'e düşsün.
    """
    now = now or datetime.now()
    ham = (mesaj or '').strip()
    s = _sade(ham)
    if not s or cursor is None:
        return False, None

    # 1) SENKRON
    if _SENKRON_RE.search(s):
        try:
            sayi, hatalar = ics_senkronize(cursor, conn)
        except Exception as e:
            return True, f"⚠️ Takvim senkronu başarısız: {type(e).__name__}"
        if not sayi and not hatalar:
            return True, ("📅 Bağlı bir dış takvim yok.\n\n"
                          "Google Takvim → Ayarlar → *Takvimi entegre et* → "
                          "**Gizli iCal adresi**'ni kopyala, Ultron Ayarlar'daki "
                          "`takvim_ics_url` alanına yapıştır.")
        mesaj_metni = f"🔄 **Takvim senkronize edildi** — {sayi} etkinlik alındı."
        if hatalar:
            mesaj_metni += "\n⚠️ Ulaşılamayan kaynak: " + ", ".join(hatalar)
        return True, mesaj_metni

    # 2) DIŞA AKTARIM
    if _DISA_AKTAR_RE.search(s):
        try:
            yol = ics_disa_aktar(cursor)
        except Exception as e:
            return True, f"⚠️ Takvim dışa aktarılamadı: {type(e).__name__}"
        return True, (f"📤 Takvim dışa aktarıldı:\n`{yol}`\n\n"
                      f"Bu dosyayı Google Takvim'e *İçe aktar* ile ekleyebilirsin.")

    # 3) SİLME
    if _SIL_FIILI.search(s) and conn is not None:
        numara = _NUMARA_RE.search(s)
        if numara:
            return True, etkinlik_sil(cursor, conn, int(numara.group(1)))
        # Numara yoksa TAHMİN ETME — yanlış etkinliği silmek geri alınamaz.
        return True, ("🗑️ Hangi etkinliği sileyim? Listedeki numarasını yaz:\n"
                      "`takvimden 3'ü sil`")

    # 4) SONRAKİ ETKİNLİK
    if _SONRAKI_RE.search(s):
        satir = sonraki_etkinlik(cursor, now)
        if not satir:
            return True, "📅 Önünde kayıtlı bir etkinlik yok."
        return True, etkinlikleri_bicimle([satir], "Sıradaki etkinlik", now)

    # 5) EKLEME
    ekleme_isteniyor = bool(_EKLE_FIILI.search(s)) or bool(
        re.search(r'\b(var|olacak)\b', s) and
        any(k in s for k in _ETKINLIK_KELIMELERI))
    # "takvimde ne var" bir SORGUDUR, ekleme değil
    if re.search(r'\bne(ler)? var\b|\bne isim var\b|\bmesgul muyum\b|'
                 r'\bmusait miyim\b|\bgoster\b|\blistele\b', s):
        ekleme_isteniyor = False

    if ekleme_isteniyor and conn is not None:
        if _YINELEME.search(s):
            # Yinelemeyi tek seferlik kaydedip susmak, kullanıcının haftaya
            # geleceğini sandığı etkinliğin sessizce kaybolması demektir.
            return True, ("🔁 Yinelenen etkinliği (her hafta/her ay) henüz yerel "
                          "takvime kuramıyorum.\n"
                          "• Tek seferlik istiyorsan tarihi net yaz: "
                          "`takvime 12 Ağustos 14:00 toplantı ekle`\n"
                          "• Her gün aynı saatte bir KOMUT çalışsın istiyorsan: "
                          "`her gün 09:00 sabah brifingi`")

        cozum = tarih_coz(ham, now)
        if not cozum:
            return True, ("📅 Etkinliğin ne zaman olduğunu anlayamadım.\n"
                          "Örnek: `takvime yarın 14:00 diş randevusu ekle`")

        baslik = _baslik_temizle(ham, cozum['temizlenecek'])
        if not baslik or len(baslik) < 2:
            return True, ("📅 Etkinliğin adını anlayamadım.\n"
                          "Örnek: `takvime cuma 15:00 Ahmet ile toplantı ekle`")

        _eid, hatirlatma = etkinlik_ekle(
            cursor, conn, baslik, cozum['baslangic'],
            bitis=cozum['bitis'], tum_gun=cozum['tum_gun'])

        ne_zaman = _gun_etiketi(cozum['baslangic'].date(), now)
        if not cozum['tum_gun']:
            ne_zaman += f" saat {cozum['baslangic']:%H:%M}"
        cevap = f"📅 **Takvime eklendi:** {baslik}\n🕐 {ne_zaman}"
        if hatirlatma:
            cevap += "\n🔔 Etkinlikten önce hatırlatacağım."
        return True, cevap

    # 6) LİSTELEME (varsayılan takvim davranışı)
    if any(k in s for k in _TAKVIM_KELIMELERI) or _GUNDEM_SORUSU.search(s) or \
            any(k in s for k in _ETKINLIK_KELIMELERI):
        bas, son, etiket = aralik_coz(ham, now)
        satirlar = etkinlikleri_getir(cursor, bas, son)
        if not satirlar:
            return True, (f"📅 **{etiket}** — kayıtlı etkinlik yok. 🎉\n\n"
                          f"Eklemek için: `takvime yarın 14:00 toplantı ekle`")
        return True, etkinlikleri_bicimle(satirlar, etiket, now)

    return False, None


# ---------------------------------------------------------------------------
# BRİFİNG KÖPRÜSÜ
# ---------------------------------------------------------------------------
def gun_ozeti(cursor, gun_farki: int = 0, now: datetime = None):
    """
    Sabah brifingi / akşam raporu için tek satırlık gün özeti.

    Hata fırlatMAZ ve etkinlik yoksa None döner — brifing bölümleri bağımsızdır,
    takvim yüzünden hava durumu kaybolmamalı.
    """
    try:
        now = now or datetime.now()
        bas = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=gun_farki)
        satirlar = etkinlikleri_getir(cursor, bas, bas + timedelta(days=1))
        if not satirlar:
            return None
        parcalar = []
        for _sid, baslik, b, _bit, tum_gun, yer, _kaynak in satirlar:
            if tum_gun:
                saat = "tüm gün"
            else:
                try:
                    saat = datetime.strptime(b, _ZAMAN_BICIM).strftime('%H:%M')
                except (TypeError, ValueError):
                    saat = "?"
            parcalar.append(f"  • {saat} — {baslik}" + (f" ({yer})" if yer else ""))
        etiket = "Bugünkü" if gun_farki == 0 else "Yarınki"
        return f"📅 **{etiket} etkinlikler:**\n" + "\n".join(parcalar)
    except Exception as e:
        print(f"[ULTRON Takvim] Gun ozeti uretilemedi: {e}")
        return None
