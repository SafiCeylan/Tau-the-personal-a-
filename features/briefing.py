"""
Sabah Brifingi — "günaydın" / "sabah brifingi" deyince tek mesajda:
  🌤️ hava durumu (wttr.in — API anahtarı gerektirmez, şehir verilmezse IP'den bulur)
  💵 döviz kurları (open.er-api.com — API anahtarı gerektirmez)
  ⏰ bugünkü hatırlatmalar (SQLite)

Şehir tercihi user_data.json içindeki "sehir" anahtarından okunur (opsiyonel).
"""

import json
import os
import threading
import time
import urllib.parse
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

from core.paths import veri_yolu

USER_DATA_PATH = veri_yolu('user_data.json')

GUNLER = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
         'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']


def _sehir_tercihi():
    try:
        with open(USER_DATA_PATH, 'r', encoding='utf-8') as f:
            return (json.load(f).get('sehir') or '').strip()
    except Exception:
        return ''


# WMO hava kodları → Türkçe (Open-Meteo weather_code alanı)
WMO_KODLARI = {
    0: 'Açık', 1: 'Çoğunlukla açık', 2: 'Parçalı bulutlu', 3: 'Kapalı',
    45: 'Sisli', 48: 'Kırağılı sis',
    51: 'Hafif çisenti', 53: 'Çisenti', 55: 'Yoğun çisenti',
    56: 'Dondurucu çisenti', 57: 'Dondurucu çisenti',
    61: 'Hafif yağmur', 63: 'Yağmurlu', 65: 'Kuvvetli yağmur',
    66: 'Dondurucu yağmur', 67: 'Dondurucu yağmur',
    71: 'Hafif kar', 73: 'Kar yağışlı', 75: 'Yoğun kar', 77: 'Kar taneleri',
    80: 'Hafif sağanak', 81: 'Sağanak yağmur', 82: 'Şiddetli sağanak',
    85: 'Kar sağanağı', 86: 'Yoğun kar sağanağı',
    95: 'Gök gürültülü fırtına', 96: 'Dolu fırtınası', 99: 'Şiddetli dolu fırtınası',
}


def _wmo(kod) -> str:
    try:
        return WMO_KODLARI.get(int(kod), 'Bilinmeyen')
    except Exception:
        return 'Bilinmeyen'


def _konum():
    """(enlem, boylam, şehir_adı) — user_data'daki şehir tercihi ya da IP konumu."""
    sehir = _sehir_tercihi()
    if sehir:
        r = requests.get('https://geocoding-api.open-meteo.com/v1/search',
                         params={'name': sehir, 'count': 1, 'language': 'tr'},
                         timeout=6).json()
        res = (r.get('results') or [{}])[0]
        if res.get('latitude') is not None:
            return res['latitude'], res['longitude'], res.get('name', sehir)
    r = requests.get('http://ip-api.com/json/?fields=lat,lon,city', timeout=6).json()
    return r.get('lat'), r.get('lon'), r.get('city', '')


# ---------------------------------------------------------------------------
# AĞ ÖNBELLEĞİ — hava ve döviz
# ---------------------------------------------------------------------------
#
# ⏱️ NEDEN: Ölçüm (15 Eyl) — "hava durumu nedir" komutu 955 ms sürüyordu ve
#    tamamı ağ bekleyişiydi. Sabah brifingi hava + dövizi birlikte çağırdığı
#    için ~2 sn açılıyordu. Hava 10 dakikada bir değişmez.
#
# 🔌 ÇEVRİMDIŞI DAVRANIŞ: Üretici başarısız olursa BAYAT kayıt döner (yaşıyla
#    birlikte). Önceden internet yokken brifingin hava/döviz bölümü tamamen
#    düşüyordu; artık "1 saat önce alınmış" notuyla geliyor. Eski bilgiyi
#    yaşını SÖYLEYEREK vermek, hiç vermemekten iyidir — ama yaşını
#    söylemeden vermek ikisinden de kötüdür.

_ONBELLEK = {}
_ONBELLEK_KILIDI = threading.Lock()

# Hava ve döviz için tazelik süresi (saniye). Testler bunu kısaltabilir.
TAZELIK_SN = 600


def onbellegi_temizle():
    """Testler ve 'zorla yenile' için."""
    with _ONBELLEK_KILIDI:
        _ONBELLEK.clear()


def _yas_metni(yas_sn: float) -> str:
    dk = int(yas_sn // 60)
    if dk < 1:
        return "az önce"
    if dk < 60:
        return f"{dk} dakika önce"
    saat = dk // 60
    return f"{saat} saat önce"


def _onbellekli_cagir(ad: str, uretici, tazelik_sn: float = None):
    """(deger, yas_sn) döner.

    • Taze kayıt varsa ağa HİÇ gidilmez → yas_sn = 0.0
    • Kayıt bayatsa üretici denenir; başarılıysa yenisi yazılır.
    • Üretici başarısız/None ise BAYAT kayıt döner (yas_sn > 0).
    • Hiç kayıt yoksa ve üretici başarısızsa (None, None).
    """
    if tazelik_sn is None:
        tazelik_sn = TAZELIK_SN

    with _ONBELLEK_KILIDI:
        kayit = _ONBELLEK.get(ad)

    simdi = time.time()
    if kayit is not None:
        yazma_zamani, deger = kayit
        if simdi - yazma_zamani < tazelik_sn:
            return deger, 0.0

    try:
        yeni = uretici()
    except Exception as e:
        print(f"[Ultron Önbellek] {ad} üretilemedi: {type(e).__name__}")
        yeni = None

    if yeni is not None:
        with _ONBELLEK_KILIDI:
            _ONBELLEK[ad] = (simdi, yeni)
        return yeni, 0.0

    # Üretim başarısız — elimizde bayat bir şey var mı?
    if kayit is not None:
        yazma_zamani, deger = kayit
        return deger, simdi - yazma_zamani
    return None, None


def _hava_ozet_veri_ham():
    """
    Standart hava özeti: {'sehir', 'simdi': (desc, temp, feels), 'gunler': [(desc, min, max), ...]}
    Birincil kaynak Open-Meteo (stabil); düşerse wttr.in yedeği denenir.
    """
    if requests is None:
        return None

    # 1. Open-Meteo (birincil)
    try:
        lat, lon, sehir = _konum()
        if lat is not None:
            r = requests.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': lat, 'longitude': lon,
                'current': 'temperature_2m,apparent_temperature,weather_code',
                'daily': 'temperature_2m_min,temperature_2m_max,weather_code',
                'forecast_days': 3, 'timezone': 'auto',
            }, timeout=8).json()
            cur = r.get('current') or {}
            daily = r.get('daily') or {}
            gunler = []
            for i in range(len(daily.get('time') or [])):
                gunler.append((
                    _wmo(daily['weather_code'][i]),
                    round(daily['temperature_2m_min'][i]),
                    round(daily['temperature_2m_max'][i]),
                ))
            return {
                'sehir': sehir,
                'simdi': (_wmo(cur.get('weather_code')),
                          round(cur.get('temperature_2m', 0)),
                          round(cur.get('apparent_temperature', 0))),
                'gunler': gunler,
            }
    except Exception as e:
        print(f"[Ultron Hava] Open-Meteo hatası: {type(e).__name__} — wttr.in deneniyor")

    # 2. wttr.in (yedek)
    try:
        sehir_t = _sehir_tercihi()
        loc = urllib.parse.quote(sehir_t) if sehir_t else ''
        data = requests.get(f"https://wttr.in/{loc}?format=j1&lang=tr",
                            timeout=8, headers={'User-Agent': 'curl/8.0'}).json()
        cur = data['current_condition'][0]
        desc = (cur.get('lang_tr') or [{}])[0].get('value') or \
               (cur.get('weatherDesc') or [{}])[0].get('value', '')
        area = ((data.get('nearest_area') or [{}])[0].get('areaName') or [{}])[0].get('value', '')
        gunler = []
        for g in (data.get('weather') or []):
            hourly = g.get('hourly') or []
            g_desc = ''
            if len(hourly) > 4:
                h = hourly[4]
                g_desc = (h.get('lang_tr') or [{}])[0].get('value') or \
                         (h.get('weatherDesc') or [{}])[0].get('value', '')
            gunler.append((g_desc, g.get('mintempC', '?'), g.get('maxtempC', '?')))
        return {
            'sehir': area,
            'simdi': (desc, cur.get('temp_C', '?'), cur.get('FeelsLikeC', '?')),
            'gunler': gunler,
        }
    except Exception as e:
        print(f"[Ultron Hava] wttr.in hatası: {type(e).__name__}")
    return None


def _hava_ozet_veri(tazelik_sn: float = None):
    """Önbellekli hava verisi. (veri, yas_sn) döner; yas_sn > 0 ise BAYAT."""
    return _onbellekli_cagir('hava', _hava_ozet_veri_ham, tazelik_sn)


def _doviz(tazelik_sn: float = None):
    """Önbellekli döviz satırı. (metin, yas_sn) döner; yas_sn > 0 ise BAYAT."""
    return _onbellekli_cagir('doviz', _doviz_ham, tazelik_sn)


def _hava_durumu():
    """Brifing için tek satırlık bugün özeti."""
    v, yas = _hava_ozet_veri()
    if not v:
        return None
    desc, temp, feels = v['simdi']
    satir = f"🌤️ **Hava — {v['sehir']}:** {desc}, şu an {temp}°C (hissedilen {feels}°C)."
    if v['gunler']:
        _, min_t, max_t = v['gunler'][0]
        satir += f" Bugün {min_t}° / {max_t}°C."
    if yas:
        satir += f" _({_yas_metni(yas)} alındı — servise şu an ulaşılamıyor)_"
    return satir


def hava_raporu() -> str:
    """'Hava nasıl' sorularına doğrudan cevap. ASLA exception fırlatmaz."""
    try:
        v, yas = _hava_ozet_veri()
    except Exception:
        v, yas = None, None
    if not v:
        return "⚠️ Hava durumu servislerine şu an ulaşılamadı — birkaç dakika sonra tekrar deneyin."

    desc, temp, feels = v['simdi']
    satirlar = [f"🌤️ **HAVA DURUMU — {v['sehir']}**",
                f"• Şu an: {desc}, **{temp}°C** (hissedilen {feels}°C)"]
    etiketler = ['Bugün', 'Yarın', 'Ertesi gün']
    for i, (g_desc, min_t, max_t) in enumerate(v['gunler'][:3]):
        ek = f", {g_desc}" if g_desc else ""
        satirlar.append(f"• {etiketler[i]}: {min_t}° / {max_t}°C{ek}")
    if yas:
        satirlar.append(f"_(⚠️ {_yas_metni(yas)} alınmış bilgi — servise şu an ulaşılamıyor)_")
    return "\n".join(satirlar)


def doviz_raporu() -> str:
    """'Dolar kaç' sorularına doğrudan cevap."""
    try:
        r, yas = _doviz()
    except Exception as e:
        return f"⚠️ Döviz servisine ulaşılamadı ({type(e).__name__})."
    if not r:
        return "⚠️ Döviz servisine ulaşılamadı."
    if yas:
        r += f" _(⚠️ {_yas_metni(yas)} alındı — servise şu an ulaşılamıyor)_"
    return r


def _doviz_ham():
    """USD bazlı kur tablosundan TRY ve EUR/TRY hesaplanır."""
    if requests is None:
        return None
    r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
    rates = r.json().get('rates', {})
    usd_try = rates.get('TRY')
    eur = rates.get('EUR')
    if not usd_try or not eur:
        return None
    eur_try = usd_try / eur
    return f"💵 **Döviz:** Dolar **{usd_try:.2f} ₺** • Euro **{eur_try:.2f} ₺**"


def _bugunku_etkinlikler(cursor):
    """
    Brifingin takvim bölümü.

    ⚠️ ASLA None dönmez: brifing döngüsü boş cevabı HATA sayıp
    "Takvim okunamadı" yazar. "Etkinlik yok" ile "takvim okunamadı" farklı
    şeylerdir — ikincisi kullanıcıyı boşuna telaşlandırır.
    """
    if cursor is None:
        return "📅 **Bugünkü etkinlikler:** —"
    try:
        from features.calendar_tools import gun_ozeti
        return gun_ozeti(cursor, 0) or "📅 **Bugünkü etkinlikler:** Takvim boş. 🎉"
    except Exception as e:
        print(f"[Ultron Takvim] Brifing bölümü atlandı: {e}")
        return "📅 **Bugünkü etkinlikler:** okunamadı."


def _bugunku_hatirlatmalar(cursor):
    if cursor is None:
        return None
    bugun = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT metin, hedef_tarih FROM hatirlatmalar
        WHERE durum = 'bekliyor' AND hedef_tarih LIKE ?
        ORDER BY hedef_tarih
    """, (bugun + '%',))
    rows = cursor.fetchall()
    if not rows:
        return "⏰ **Bugünkü hatırlatmalar:** Bugün için bekleyen hatırlatma yok. 🎉"
    lines = [f"  • {(tarih or '')[11:16]} — {metin}" for metin, tarih in rows]
    return "⏰ **Bugünkü hatırlatmalar:**\n" + "\n".join(lines)


def aksam_raporu_olustur(cursor=None) -> str:
    """🌙 Gün sonu özeti: bugünkü aktivite + ruh hali + yarının hatırlatmaları."""
    from datetime import timedelta
    now = datetime.now()
    bugun = now.strftime('%Y-%m-%d')
    yarin = (now + timedelta(days=1)).strftime('%Y-%m-%d')

    satirlar = [f"🌙 **GÜNÜN RAPORU — {now.day} {AYLAR[now.month - 1]} {GUNLER[now.weekday()]}**\n"]

    if cursor is not None:
        try:
            cursor.execute("SELECT COUNT(*) FROM sohbet_gecmisi WHERE tarih LIKE ?", (bugun + '%',))
            mesaj_sayisi = cursor.fetchone()[0]
            satirlar.append(f"💬 Bugün **{mesaj_sayisi}** konuşma yaptık.")
        except Exception:
            pass

        try:
            cursor.execute("""SELECT COUNT(*) FROM hatirlatmalar
                              WHERE durum = 'tamamlandi' AND hedef_tarih LIKE ?""", (bugun + '%',))
            tamam = cursor.fetchone()[0]
            if tamam:
                satirlar.append(f"✅ Bugün **{tamam}** hatırlatma tamamlandı.")
        except Exception:
            pass

        try:
            cursor.execute("""SELECT ruh_hali, COUNT(*) FROM ruh_hali_gecmisi
                              WHERE tarih LIKE ? GROUP BY ruh_hali
                              ORDER BY COUNT(*) DESC""", (bugun + '%',))
            rows = cursor.fetchall()
            if rows:
                baskin = rows[0][0]
                emoji = {'pozitif': '😊', 'negatif': '😔', 'nötr': '😐'}.get(baskin, '🎭')
                satirlar.append(f"{emoji} Günün baskın ruh hali: **{baskin}**")
        except Exception:
            pass

        try:
            from features.calendar_tools import gun_ozeti
            yarinki = gun_ozeti(cursor, 1)
            if yarinki:
                satirlar.append(yarinki)
        except Exception as e:
            print(f"[Ultron Takvim] Akşam raporu takvim bölümü atlandı: {e}")

        try:
            cursor.execute("""SELECT metin, hedef_tarih FROM hatirlatmalar
                              WHERE durum = 'bekliyor' AND hedef_tarih LIKE ?
                              ORDER BY hedef_tarih""", (yarin + '%',))
            rows = cursor.fetchall()
            if rows:
                liste = "\n".join(f"  • {(t or '')[11:16]} — {m}" for m, t in rows)
                satirlar.append(f"⏰ **Yarının hatırlatmaları:**\n{liste}")
            else:
                satirlar.append("⏰ Yarın için bekleyen hatırlatma yok.")
        except Exception:
            pass

    satirlar.append("\nİyi geceler! Sistemler nöbette kalacak. 🔴")
    try:
        from features.suggestions import tek_satir_oneri_sun
        oneri_metni = tek_satir_oneri_sun(db_cursor=cursor)
        if oneri_metni:
            satirlar.append(oneri_metni)
    except Exception:
        pass
    return "\n".join(satirlar)



def sabah_brifingi_olustur(cursor=None):
    """Bölümlerden biri çökse bile diğerleri gelir (her biri bağımsız try/except)."""
    now = datetime.now()
    baslik = (f"🌅 **GÜNAYDIN! ULTRON SABAH BRİFİNGİ**\n"
              f"📅 {now.day} {AYLAR[now.month - 1]} {now.year} {GUNLER[now.weekday()]} — "
              f"saat {now.strftime('%H:%M')}\n")

    bolumler = []
    for uretici, hata_etiketi in (
        (_hava_durumu, "🌤️ Hava durumu alınamadı"),
        (_doviz, "💵 Döviz kurları alınamadı"),
        (lambda: _bugunku_etkinlikler(cursor), "📅 Takvim okunamadı"),
        (lambda: _bugunku_hatirlatmalar(cursor), "⏰ Hatırlatmalar okunamadı"),
    ):
        try:
            b = uretici()
            bolumler.append(b if b else f"{hata_etiketi}.")
        except Exception as e:
            bolumler.append(f"{hata_etiketi} ({type(e).__name__}).")

    return baslik + "\n" + "\n\n".join(bolumler)
