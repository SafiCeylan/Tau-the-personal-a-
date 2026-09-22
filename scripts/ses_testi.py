# -*- coding: utf-8 -*-
"""
🎙️ MİKROFONSUZ SES TESTİ — ses boru hattını insan konuşmadan ÖLÇER.

    python scripts/ses_testi.py                 # tam ölçüm (edge-tts + Google gerekir)
    python scripts/ses_testi.py --sadece-vosk   # Google'sız (yalnız çevrimdışı motor)
    python scripts/ses_testi.py --ornek-kaydet  # tests/ses_ornekleri/ WAV'larını yeniden üret

NEDEN VAR: Projenin en pahalı dersi "birim testi yönlendirmeyi kanıtlamaz"
(12 Ağu: testler yeşil, özelliklerin yarısı çalışmıyordu). Sesin bir katmanı
daha var: cümle doğru niyete gidiyor olabilir ama KONUŞULDUĞUNDA yazıya
yanlış çevrilip başka yere gidebilir. Bu betik her cümle için:

  1. edge-tts ile iki Türkçe sesle (erkek + kadın) ve üç hızda konuşma üretir,
  2. 16 kHz'e indirir (mikrofon akışı gibi),
  3. WAKE WORD — WakeWordThread'in AYNI tanıyıcısı, AYNI karar fonksiyonu ve
     AYNI 0,5 sn'lik parçalarıyla "uyandırır mı?" diye bakar; sıradan
     cümlelerde yanlış tetiklemeyi de sayar,
  4. STT — Google ve Vosk ile ayrı ayrı yazıya çevirir,
  5. YÖNLENDİRME — yazıya dökülen metni gerçek niyet zincirinden geçirir.

İLK ÇALIŞTIRMANIN BULDUKLARI (16 Eyl 2026):
  • "25 dakika odaklan" YAZILI hâliyle bile WINDOW_FOCUS'a gidiyordu (pomodoro
    hiç başlamıyordu). İlk sürüm beklenen niyeti yazılı cümleden türettiği için
    bunu "doğru" saymıştı — beklenen niyetler artık ELLE yazılı.
  • Tek başına "ultra" ile uyanma kuralı sıradan cümlelerin %13'ünde
    tetikliyordu → kural "hey ultra" art arda oldu (%3).
  • Google 32/32, Vosk (çevrimdışı) 26/32 doğru niyet.

Sentetik ses gerçek mikrofondan temizdir (oda yankısı, gürültü, aksan yok):
buradaki başarı ORAN ÜST SINIRIDIR, canlı doğruluk bundan düşük olur. Ama
burada kırılan bir cümle canlıda kesin kırılır — asıl değeri bu.
"""
import argparse
import asyncio
import hashlib
import os
import re
import sys
import tempfile
import time

PROJE_KOKU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJE_KOKU)

SESLER = ['tr-TR-AhmetNeural', 'tr-TR-EmelNeural']
HIZLAR = ['-15%', '+0%', '+15%']
HEDEF_HIZ = 16000

# Belgelenen uyandırma ifadesi — hepsi uyandırmalı
UYANDIRMA_CUMLELERI = ['hey ultron', 'hey ultron hava durumu nasıl']
# Bilgi amaçlı: artık uyandırmaması BEKLENEN (bkz. speech.uyandirma_sonucu_mu)
BILGI_CUMLELERI = ['ultron', 'Ultra HD bir film aç']

# Sesli kullanımda doğal söylenen komutlar ve GİTMESİ GEREKEN niyet (elle yazılı).
KOMUTLAR = [
    ('hava durumu nasıl', 'WEATHER'),
    ('dolar kaç lira', 'CURRENCY'),
    ('chrome aç', 'SYSTEM_CONTROL'),
    ('sesi yüzde elli yap', 'SET_VOLUME'),
    ('müziği duraklat', 'MEDIA_CONTROL'),
    ('sonraki şarkı', 'MEDIA_CONTROL'),
    ('ekran görüntüsü al', 'SCREENSHOT'),
    ('yarın saat üçte toplantıyı hatırlat', 'CREATE_REMINDER'),
    ('25 dakika odaklan', 'FOCUS_MODE'),
    ('bugün ne kadar harcadım', 'FINANCE_TRACK'),
    ('Zen penceresine geç', 'WINDOW_FOCUS'),
    ('canlı sesli sohbeti başlat', 'DUPLEX_VOICE'),
    ('sabah brifingi', 'MORNING_BRIEFING'),
    ('saat kaç', 'TIME_DATE'),
    ('arka planda ne çalışıyor', 'SYSTEM_CONTROL'),
    ('notlarımı göster', 'NOTE_TAKE'),
]

# Yalnız yanlış tetikleme ölçümü için ek sıradan cümleler
EK_OLUMSUZLAR = [
    'bugün hava çok güzel', 'altıya kadar bekle', 'kültür sanat haberleri',
    'dolar ne kadar oldu', 'lira değer kaybetti',
]

# tests/test_ses_tanima.py'nin çevrimdışı kullandığı kayıtlar (Ahmet, normal hız)
ORNEK_KAYITLAR = {
    'hey_ultron.wav': 'hey ultron',
    'hava_durumu_nasil.wav': 'hava durumu nasıl',
    # Eski kuralla uyandırıyordu (Vosk "ultra" duyuyor) — yeni kuralın kilidi
    'dolar_kac_lira.wav': 'dolar kaç lira',
}

_ONBELLEK = os.path.join(tempfile.gettempdir(), 'ultron_ses_testi')


def konusma_uret(metin: str, ses: str, hiz: str = '+0%'):
    """edge-tts → int16 numpy dizi @16 kHz (mp3 önbellekli). Üretilemezse None."""
    import edge_tts
    import numpy as np
    import soundfile as sf

    os.makedirs(_ONBELLEK, exist_ok=True)
    anahtar = hashlib.sha1(f'{ses}|{hiz}|{metin}'.encode('utf-8')).hexdigest()[:16]
    mp3 = os.path.join(_ONBELLEK, f'{anahtar}.mp3')
    if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
        async def _gen():
            await edge_tts.Communicate(metin, voice=ses, rate=hiz).save(mp3)
        # edge-tts ara sıra "NoAudioReceived" veriyor (ölçüldü) — kısa yeniden deneme
        for deneme in range(3):
            try:
                asyncio.run(_gen())
                break
            except Exception as e:
                if os.path.exists(mp3):
                    os.remove(mp3)
                if deneme == 2:
                    print(f'    (üretilemedi: "{metin}" {ses} {hiz}: {type(e).__name__})')
                    return None
                time.sleep(1)
        if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
            return None

    data, kaynak_hiz = sf.read(mp3, dtype='float32')
    if data.ndim > 1:
        data = data[:, 0]
    if kaynak_hiz != HEDEF_HIZ:
        try:
            from math import gcd
            from scipy.signal import resample_poly
            g = gcd(kaynak_hiz, HEDEF_HIZ)
            data = resample_poly(data, HEDEF_HIZ // g, kaynak_hiz // g)
        except ImportError:
            yeni_n = int(len(data) * HEDEF_HIZ / kaynak_hiz)
            data = np.interp(np.linspace(0, len(data), yeni_n, endpoint=False),
                             np.arange(len(data)), data)
    return (np.clip(data, -1, 1) * 32767).astype('int16')


def uyandirir_mi(pcm: bytes) -> bool:
    """WakeWordThread döngüsünün birebir aynısı (16 kHz, 8000 örnek = 0,5 sn)."""
    from features import speech
    rec = speech.uyandirma_tanicisi(speech.vosk_modeli(), HEDEF_HIZ)
    pcm = b'\x00\x00' * (HEDEF_HIZ // 2) + pcm + b'\x00\x00' * HEDEF_HIZ
    adim = 8000 * 2
    for i in range(0, len(pcm), adim):
        if rec.AcceptWaveform(pcm[i:i + adim]) and speech.uyandirma_sonucu_mu(rec.Result()):
            return True
    return False


def google_ile(pcm: bytes):
    from features import speech
    sr = speech._sr()
    try:
        return sr.Recognizer().recognize_google(
            sr.AudioData(pcm, HEDEF_HIZ, 2), language='tr-TR')
    except sr.UnknownValueError:
        return ''
    except sr.RequestError as e:
        return f'<HATA: {e}>'


def sade(metin: str) -> str:
    m = (metin or '').replace('I', 'ı').replace('İ', 'i').lower()
    return re.sub(r'[^\w% ]', '', m).strip()


def ornekleri_kaydet():
    import soundfile as sf
    hedef = os.path.join(PROJE_KOKU, 'tests', 'ses_ornekleri')
    os.makedirs(hedef, exist_ok=True)
    for ad, metin in ORNEK_KAYITLAR.items():
        ses = konusma_uret(metin, SESLER[0])
        if ses is None:
            print(f'  ✗ {ad} üretilemedi')
            continue
        yol = os.path.join(hedef, ad)
        sf.write(yol, ses, HEDEF_HIZ, subtype='PCM_16')
        print(f'  ✓ {os.path.relpath(yol, PROJE_KOKU)}  ({os.path.getsize(yol) // 1024} KB) ← "{metin}"')


def _kisa(ses):
    return ses.split('-')[2].replace('Neural', '')


def main():
    ap = argparse.ArgumentParser(description='Mikrofonsuz ses boru hattı ölçümü')
    ap.add_argument('--sadece-vosk', action='store_true', help='Google STT çağırma')
    ap.add_argument('--ornek-kaydet', action='store_true',
                    help='tests/ses_ornekleri/ kayıtlarını üret ve çık')
    args = ap.parse_args()

    if args.ornek_kaydet:
        ornekleri_kaydet()
        return

    # Niyet zinciri öğrenme arşivine/diske yazmasın — testlerle aynı zırh
    from tests.safety import guvenlik_zirhi_kur
    guvenlik_zirhi_kur()
    from tests.test_intent_routing import niyet, _dosya_durumunu_temizle
    from features import speech

    if speech.vosk_modeli() is None:
        print('❌ Vosk modeli yok (models/vosk-tr) — wake word ve çevrimdışı ölçüm yapılamaz.')
        return

    def yonlendir(metin):
        _dosya_durumunu_temizle()
        return niyet(metin) if metin else None

    t0 = time.time()
    hatalar = []

    print('\n══ 0) YAZILI YÖNLENDİRME (ses yok — taban çizgisi) ═══════════')
    for metin, beklenen in KOMUTLAR:
        giden = yonlendir(metin)
        if giden != beklenen:
            hatalar.append(f'yazılı "{metin}" → {giden} (beklenen {beklenen})')
            print(f'  ❌ "{metin}" → {giden}  (beklenen {beklenen}) — SES DEĞİL, METİN HATASI')
    if not any(h.startswith('yazılı') for h in hatalar):
        print(f'  ✅ {len(KOMUTLAR)}/{len(KOMUTLAR)} komut yazılı hâliyle doğru niyete gidiyor')

    print('\n══ 1) WAKE WORD (2 ses × 3 hız) ═════════════════════════════')
    uyanan = uyanma_toplam = yanlis = olumsuz_toplam = 0
    olumsuzlar = [m for m, _ in KOMUTLAR] + EK_OLUMSUZLAR
    for metin in UYANDIRMA_CUMLELERI + BILGI_CUMLELERI + olumsuzlar:
        satir = []
        for ses in SESLER:
            for hiz in HIZLAR:
                pcm = konusma_uret(metin, ses, hiz)
                if pcm is None:
                    satir.append('?')
                    continue
                sonuc = uyandirir_mi(pcm.tobytes())
                satir.append('U' if sonuc else '·')
                if metin in UYANDIRMA_CUMLELERI:
                    uyanma_toplam += 1
                    uyanan += sonuc
                elif metin in olumsuzlar:
                    olumsuz_toplam += 1
                    yanlis += sonuc
        isaret = ''.join(satir)
        if metin in UYANDIRMA_CUMLELERI:
            durum = '✅' if '·' not in isaret else '❌ KAÇIRDI'
        elif metin in BILGI_CUMLELERI:
            durum = 'ℹ️  bilgi (uyandırmaması beklenir)'
        else:
            durum = '✅ sessiz' if 'U' not in isaret else '❌ YANLIŞ TETİK'
        print(f'  {metin:<38} [{isaret}]  {durum}')
    print('  (sıra: Ahmet -15/0/+15, Emel -15/0/+15 · U = uyandı)')

    print('\n══ 2) STT + YÖNLENDİRME ══════════════════════════════════════')
    motorlar = ['vosk'] if args.sadece_vosk else ['google', 'vosk']
    dogru = {m: 0 for m in motorlar}
    birebir = {m: 0 for m in motorlar}
    toplam = 0
    for metin, beklenen in KOMUTLAR:
        print(f'\n  "{metin}"  →  beklenen: {beklenen}')
        for ses in SESLER:
            ses_verisi = konusma_uret(metin, ses)
            if ses_verisi is None:
                continue
            pcm = ses_verisi.tobytes()
            toplam += 1
            for motor in motorlar:
                duyulan = google_ile(pcm) if motor == 'google' else (
                    speech.vosk_yaziya_cevir(pcm, HEDEF_HIZ) or '')
                gecerli = duyulan and not duyulan.startswith('<HATA')
                giden = yonlendir(duyulan.lower()) if gecerli else None
                tamam = giden == beklenen
                dogru[motor] += tamam
                birebir[motor] += sade(duyulan) == sade(metin)
                print(f'    {_kisa(ses):<6} {motor:<6} "{duyulan}" → {giden} {"✅" if tamam else "❌"}')

    print('\n══ ÖZET ══════════════════════════════════════════════════════')
    yazili = sum(1 for h in hatalar if h.startswith('yazılı'))
    print(f'  Yazılı yönlendirme   : {len(KOMUTLAR) - yazili}/{len(KOMUTLAR)}')
    print(f'  Wake word yakalama   : {uyanan}/{uyanma_toplam}  ("Hey Ultron")')
    print(f'  Yanlış tetikleme     : {yanlis}/{olumsuz_toplam} sıradan cümle örneği')
    for motor in motorlar:
        if toplam:
            print(f'  {motor:<6} doğru niyet  : {dogru[motor]}/{toplam} '
                  f'(%{round(100 * dogru[motor] / toplam)})   '
                  f'birebir metin: {birebir[motor]}/{toplam}')
    print(f'  Süre                 : {time.time() - t0:.1f} sn')
    print('  NOT: sentetik ses temizdir — canlı doğruluk bundan DÜŞÜK olur.')


if __name__ == '__main__':
    main()
