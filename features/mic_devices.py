# -*- coding: utf-8 -*-
"""
🎙️ MİKROFON SEÇİMİ — hangi aygıt gerçekten mikrofon, hangisi değil.

NEDEN VAR (16 Eyl 2026, ölçüldü):
    config'te `mic_device_index: 1` duruyordu. O gün 1 numaralı aygıt
    "Stereo Karışımı (Realtek)" idi — mikrofon DEĞİL, hoparlörden çıkan sesin
    kaydı. "Hey Ultron" kullanıcının sesini hiç duymuyordu; kullanıcı da
    bilgisayarında mikrofon olmadığını sanıyordu. Oysa dahili "Mikrofon Dizisi"
    çalışıyordu (hoparlörden çalınan 1 kHz bip mikrofonda 12 kat sinyal verdi).

    İki kök neden vardı:
      1. Ayarlar listesi hoparlör kaydını (Stereo Karışımı) mikrofon diye sunuyordu.
      2. Aygıt NUMARAYLA saklanıyordu. Numara, Bluetooth kulaklık bağlanıp
         ayrıldıkça kayar: dün mikrofon olan 1 bugün Stereo Karışımı olabilir.
         Yanlış aygıt hata vermeden AÇILDIĞI için "açılamazsa varsayılana düş"
         yedeği de devreye girmiyordu — sessiz hata.

    Çözüm: aygıt ADIYLA saklanır (`mic_device_name`), her kullanımda o anki
    numaraya çözülür; hoparlör kaydı hiçbir koşulda mikrofon sayılmaz.

NUMARA UZAYI: wake word `sounddevice`, komut dinleme `PyAudio` (sr.Microphone)
kullanıyor. İkisi de PortAudio sarmalayıcısı ve bu makinede aygıt numaraları
birebir aynı çıktı (16 Eyl, MME/DirectSound/WASAPI/WDM-KS dahil ölçüldü).
Liste yalnız MME'den üretilir; MME adları Windows tarafından 31 karakterde
kesilir ("Mikrofon Dizisi (Realtek(R) Aud") — karşılaştırma bu kesik adla yapılır.

`sounddevice` bilerek fonksiyon içinde import edilir (açılış hızı —
bkz. tests/test_acilis_hizi.py).
"""

# Adında bunlardan biri geçen aygıt mikrofon DEĞİLDİR: hoparlörden çıkan sesi kaydeder.
# ASCII yazılır; karşılaştırma `_sade()` çıktısında yapılır (Türkçe harf eşleşmez).
HOPARLOR_KAYDI_KALIPLARI = (
    'stereo karisimi', 'stereo mix', 'what u hear', 'wave out', 'loopback',
    'hoparlor', 'speaker', 'output',
)

# Sistem varsayılanının takma adları — listede "Sistem varsayılanı" zaten var,
# ikinci kez gösterilmez; seçilmişse varsayılan sayılır (uyarı yok).
VARSAYILAN_TAKMA_ADLARI = (
    'ses eslestiricisi', 'sound mapper', 'birincil ses yakalama', 'primary sound capture',
)

_TR_ASCII = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')


def _sade(ad) -> str:
    return str(ad or '').translate(_TR_ASCII).lower().strip()


def hoparlor_kaydi_mi(ad) -> bool:
    s = _sade(ad)
    return any(k in s for k in HOPARLOR_KAYDI_KALIPLARI)


def varsayilan_takma_adi_mi(ad) -> bool:
    s = _sade(ad)
    return any(k in s for k in VARSAYILAN_TAKMA_ADLARI)


def mikrofon_mu(ad) -> bool:
    """Listede seçilebilir gerçek bir mikrofon mu?"""
    if not _sade(ad):
        return False
    return not hoparlor_kaydi_mi(ad) and not varsayilan_takma_adi_mi(ad)


def _hoparlor_uyarisi(ad: str) -> str:
    return (f"⚠️ Ayarlı ses aygıtı ({ad}) bir mikrofon değil — hoparlörden çıkan "
            f"sesi kaydeder, seni duymaz. Sistem varsayılanı kullanılıyor; "
            f"Ayarlar'dan gerçek mikrofonu seç.")


def aygit_coz(aygitlar, ad=None, indeks=None):
    """Kayıtlı mikrofonu o anki aygıt numarasına çözer. SAF fonksiyon (donanımsız test edilir).

    aygitlar: [(numara, ad), ...] — tek host API'nin (MME) giriş aygıtları.
    ad:       config `mic_device_name` (öncelikli — numara kayar, ad kaymaz)
    indeks:   config `mic_device_index` (ad yoksa, eski config'ler için)

    Dönüş: (numara | None, uyarı | None). numara None = sistem varsayılanı.
    """
    ad = str(ad or '').strip()
    if ad:
        for no, aygit_adi in aygitlar:
            if aygit_adi == ad:
                if hoparlor_kaydi_mi(aygit_adi):
                    return None, _hoparlor_uyarisi(aygit_adi)
                if varsayilan_takma_adi_mi(aygit_adi):
                    return None, None
                return no, None
        return None, (f"🎙️ Kayıtlı mikrofon ({ad}) şu an bağlı değil — "
                      f"sistem varsayılanı kullanılıyor.")

    try:
        indeks = int(indeks)
    except (TypeError, ValueError):
        return None, None
    if indeks < 0:
        return None, None

    for no, aygit_adi in aygitlar:
        if no == indeks:
            if hoparlor_kaydi_mi(aygit_adi):
                return None, _hoparlor_uyarisi(aygit_adi)
            if varsayilan_takma_adi_mi(aygit_adi):
                return None, None
            return no, None
    return None, (f"🎙️ Kayıtlı mikrofon (#{indeks}) bulunamadı — "
                  f"sistem varsayılanı kullanılıyor.")


def giris_aygitlari():
    """[(numara, ad)] — MME'deki TÜM giriş aygıtları (filtresiz). Hata yükseltebilir."""
    import sounddevice as sd
    aygitlar = []
    for no, d in enumerate(sd.query_devices()):
        if d.get('max_input_channels', 0) <= 0:
            continue
        try:
            host = sd.query_hostapis(d['hostapi'])['name']
        except Exception:
            host = ''
        if host == 'MME':
            aygitlar.append((no, d['name']))
    return aygitlar


def mikrofonlari_listele():
    """Ayarlar menüsü için: yalnız gerçek mikrofonlar. Hata olursa boş liste."""
    try:
        return [(no, ad) for no, ad in giris_aygitlari() if mikrofon_mu(ad)]
    except Exception as e:
        print(f"[Mikrofon] Aygıt listesi alınamadı: {e}")
        return []


def _varsayilan_giris_adi():
    import sounddevice as sd
    return sd.query_devices(kind='input')['name']


def mikrofon_sec(config: dict):
    """Dinleyiciler (wake word / komut) için: (numara | None, uyarı | None).

    Aygıt listesi okunamazsa ESKİ davranışa döner (config'teki numarayı olduğu
    gibi kullanır) — koruma katmanı bozulunca sesi tamamen kesmesin.
    """
    config = config or {}
    try:
        aygitlar = giris_aygitlari()
    except Exception as e:
        print(f"[Mikrofon] Aygıt listesi alınamadı, kayıtlı numara kullanılıyor: {e}")
        eski = config.get('mic_device_index', -1)
        return (None if eski in (None, -1, '') else eski), None

    no, uyari = aygit_coz(aygitlar, config.get('mic_device_name'),
                          config.get('mic_device_index'))
    if no is None:
        # Varsayılana düştük — Windows'un varsayılan kayıt aygıtı da hoparlör
        # kaydı olabilir; o zaman "varsayılan" da kullanıcıyı duymaz.
        try:
            varsayilan = _varsayilan_giris_adi()
            if hoparlor_kaydi_mi(varsayilan):
                ek = (f"⚠️ Windows'un varsayılan kayıt aygıtı ({varsayilan}) da bir "
                      f"hoparlör kaydı — Ayarlar'dan gerçek mikrofonu seç.")
                uyari = f"{uyari}\n{ek}" if uyari else ek
        except Exception:
            pass
    return no, uyari


def seviye_yorumla(tepe_orani: float):
    """Mikrofon testindeki tepe seviyeyi (0..1) yorumlar → (durum, mesaj).

    durum: 'iyi' | 'zayif' | 'yok'. Eşikler eski Test Et penceresiyle aynı.
    Ölçüm (16 Eyl): sessiz odada dahili mikrofon dizisi ~%3 tepe veriyor —
    bu yüzden 'zayif' eşiği konuşma beklentisiyle yorumlanmalı, sessizlikle değil.
    """
    yuzde = round(max(0.0, min(1.0, float(tepe_orani or 0))) * 100)
    if yuzde >= 10:
        return 'iyi', f"✅ Ses algılandı (tepe %{yuzde}) — bu mikrofon kullanıma hazır."
    if yuzde >= 2:
        return 'zayif', (f"⚠️ Çok zayıf ses (tepe %{yuzde}). Konuştuysan mikrofona "
                         f"yaklaş ya da Windows'ta mikrofon seviyesini yükselt.")
    return 'yok', (f"❌ Ses gelmedi (tepe %{yuzde}). Yanlış aygıt seçilmiş olabilir — "
                   f"listeden başka bir mikrofon dene.")
