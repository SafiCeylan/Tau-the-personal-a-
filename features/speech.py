import os
import re
import tempfile
import threading
import time
import subprocess

# ⚡ AĞIR BAĞIMLILIKLAR BİLEREK ÜST SEVİYEDE DEĞİL.
# Ölçüm (15 Eyl): `ui.tau_window` importu soğukta 2,78 sn sürüyordu; 1,74 sn'si
# bu modül, 1,67 sn'si tek başına `pygame` (numpy + pkg_resources zincirini
# çekiyor). pygame yalnızca mp3 çalmak, gTTS yalnızca yedek TTS, `sr` yalnızca
# mikrofon için gerekli — hiçbiri açılışta lazım değil. Üçü de SADECE fonksiyon
# içinde kullanılıyor, bu yüzden çağrı anına ertelendi (`_pg()` / `_sr()`).
# Üst seviyeye geri taşırsan açılış ~2 sn yavaşlar; `tests/test_acilis_hizi.py`
# bunu yakalar.


def _pg():
    """pygame'i ilk ses çalma anında yükler (sonraki çağrılar sys.modules'tan)."""
    import pygame
    return pygame


def _sr():
    """speech_recognition'ı ilk mikrofon kullanımında yükler."""
    import speech_recognition
    return speech_recognition

# ---------------------------------------------------------------------------
# TTS (Sesli Yanıt) — ULTRON cevaplarını okur
# ---------------------------------------------------------------------------
_pyttsx3_engine = None
_tts_lock = threading.Lock()


# Canlı sesli sohbetin durumu artık `features/duplex.py`'deki OTURUM nesnesinde
# (sessizlik/hata sayacı, süre tavanı, kapatma kuralı hep orada). Buradaki iki
# fonksiyon eski çağıranlar için ince kapıdır — İKİNCİ BİR BAYRAK TUTMA,
# iki gerçek kaynağı olan durum er geç ayrışır.
def is_duplex_voice_active() -> bool:
    from features.duplex import OTURUM
    return OTURUM.aktif_mi()


def set_duplex_voice_active(active: bool) -> bool:
    from features.duplex import OTURUM
    if active:
        OTURUM.baslat()
    else:
        OTURUM.kapat()
    return OTURUM.aktif_mi()


_EMOJI_RE = re.compile(
    '[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]'
)


def tts_metin_temizle(text: str, max_cumle: int = 3, max_len: int = 400) -> str:
    """Markdown/emoji temizler, ilk birkaç cümleyi alır (brifingin tamamını
    dinletmek işkence olur)."""
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', text or '')
    t = re.sub(r'```.*?```', ' ', t, flags=re.DOTALL)
    t = re.sub(r'`[^`]*`', ' ', t)
    t = _EMOJI_RE.sub('', t)
    t = re.sub(r'[#*_>\[\]|•]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    cumleler = re.split(r'(?<=[.!?])\s+', t)
    t = ' '.join(cumleler[:max_cumle])
    return t[:max_len].strip()


def konusmayi_durdur():
    """Devam eden seslendirmeyi anında keser (thread'ler arası güvenli)."""
    try:
        if _pg().mixer.get_init():
            _pg().mixer.music.stop()
    except Exception:
        pass
    global _pyttsx3_engine
    if _pyttsx3_engine is not None:
        try:
            _pyttsx3_engine.stop()
        except Exception:
            pass


def seslendir(text: str, engine: str = 'edge'):
    """Metni sesli okur. BLOKLAR — worker thread'den çağrılmalıdır.
    Yeni seslendirme öncekini otomatik keser.
    Motorlar: 'edge' (Ahmet — kalın erkek, doğal), 'gtts', 'sapi'."""
    t = tts_metin_temizle(text)
    if not t:
        return
    konusmayi_durdur()
    if engine == 'sapi':
        _seslendir_sapi(t)
    elif engine == 'gtts':
        _seslendir_gtts(t)
    else:
        try:
            _seslendir_edge(t)
        except Exception as e:
            print(f"[Ultron TTS] Edge başarısız ({e}) — gTTS'e düşülüyor")
            _seslendir_gtts(t)


def _mp3_cal(fname: str):
    """Üretilen mp3'ü çalar ve bitmesini bekler (durdurulabilir)."""
    with _tts_lock:
        if not _pg().mixer.get_init():
            _pg().mixer.init()
        _pg().mixer.music.load(fname)
        _pg().mixer.music.play()
    while _pg().mixer.music.get_busy():
        _pg().time.Clock().tick(10)


def _seslendir_edge(t: str):
    """Microsoft Edge Neural TTS — tr-TR-AhmetNeural (doğal erkek ses).
    pitch -8Hz ile ULTRON'a yakışır kalınlıkta. İnternet gerektirir, ücretsizdir."""
    import asyncio
    import edge_tts

    fname = os.path.join(tempfile.gettempdir(), f'ultron_tts_{int(time.time() * 1000)}.mp3')
    try:
        async def _gen():
            com = edge_tts.Communicate(t, voice="tr-TR-AhmetNeural",
                                       rate="+4%", pitch="-8Hz")
            await com.save(fname)

        asyncio.run(_gen())
        _mp3_cal(fname)
    finally:
        try:
            _pg().mixer.music.unload()
        except Exception:
            pass
        try:
            os.remove(fname)
        except Exception:
            pass


def _seslendir_sapi(t: str):
    """Windows SAPI (offline). NOT: Türkçe ses paketi kuruluysa iyi;
    yoksa İngilizce sesle Türkçe okur (kötü)."""
    global _pyttsx3_engine
    import pyttsx3
    with _tts_lock:
        eng = pyttsx3.init()
        _pyttsx3_engine = eng
        try:
            eng.say(t)
            eng.runAndWait()
        finally:
            _pyttsx3_engine = None


def _seslendir_gtts(t: str):
    """Google TTS (internet gerekir, doğal Türkçe)."""
    fname = os.path.join(tempfile.gettempdir(), f'ultron_tts_{int(time.time() * 1000)}.mp3')
    try:
        from gtts import gTTS
        gTTS(text=t, lang='tr', slow=False).save(fname)
        with _tts_lock:
            if not _pg().mixer.get_init():
                _pg().mixer.init()
            _pg().mixer.music.load(fname)
            _pg().mixer.music.play()
        while _pg().mixer.music.get_busy():
            _pg().time.Clock().tick(10)
    except Exception as e:
        print(f"[Ultron TTS] Seslendirme hatası: {e}")
    finally:
        try:
            _pg().mixer.music.unload()
        except Exception:
            pass
        try:
            os.remove(fname)
        except Exception:
            pass

def text_to_speech(text, lang='tr'):
    """Metni sese çevirir ve çalar (Online - gTTS + Pygame/System)"""
    try:
        if not text:
            return
            
        print(f"Seslendiriliyor: {text[:30]}...")
        
        # Dosya ismi oluştur
        filename = "yanit.mp3"
        
        # gTTS ile ses dosyası oluştur
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filename)
        except Exception as e:
            print(f"gTTS ses oluşturma hatası: {e}")
            return

        # 1. Yöntem: Pygame ile oynatmayı dene
        try:
            _pg().mixer.init()
            _pg().mixer.music.load(filename)
            _pg().mixer.music.play()
            
            # Çalma bitene kadar bekle
            while _pg().mixer.music.get_busy():
                _pg().time.Clock().tick(10)
                
            _pg().mixer.quit()
            
        except Exception as e:
            print(f"Pygame player hatası ({e}), sistem oynatıcısı deneniyor...")
            # 2. Yöntem: Sistem komutu ile oynat (Linux)
            try:
                # mpg123, ffplay veya paplay dene
                subprocess.run(["mpg123", "-q", filename], check=False)
            except FileNotFoundError:
                try: 
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", filename], check=False)
                except:
                    pass
        
        # Temizlik
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except:
            pass
            
    except Exception as e:
        print(f"TTS Genel Hatası: {e}")

# ---------------------------------------------------------------------------
# STT (Konuşmayı yazıya çevirme) — Google birincil, Vosk çevrimdışı yedek
# ---------------------------------------------------------------------------
# Vosk Türkçe modeli (~56 MB). Hem wake word hem çevrimdışı tanıma kullanır.
# exe'de ULTRON.spec modeli `_internal/models/vosk-tr`'ye koyar; bu dosya
# `_internal/features/` altında olduğu için yol iki ortamda da doğru çözülür.
VOSK_MODEL_YOLU = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'vosk-tr')

# Wake word gramer kilidi. 'ultron' TR sözlüğünde YOK → fonetik komşusu 'ultra'.
UYANDIRMA_GRAMERI = ["hey ultra", "ultra", "[unk]"]

_vosk_model = None
_vosk_model_lock = threading.Lock()


def vosk_modeli(model_yolu: str = None):
    """Vosk modelini BİR KEZ yükler ve paylaşır (Model thread'ler arası paylaşılabilir;
    her dinleyici kendi KaldiRecognizer'ını açar). Model/paket yoksa None."""
    global _vosk_model
    yol = model_yolu or VOSK_MODEL_YOLU
    with _vosk_model_lock:
        if _vosk_model is not None:
            return _vosk_model
        if not os.path.isdir(yol):
            return None
        try:
            import vosk
            vosk.SetLogLevel(-1)
            _vosk_model = vosk.Model(yol)
        except Exception as e:
            print(f"[Ultron STT] Vosk modeli yüklenemedi: {e}")
            return None
        return _vosk_model


def uyandirma_tanicisi(model, sample_rate: int = 16000):
    """Wake word için gramere kilitli tanıyıcı. WakeWordThread ve ses testi
    (scripts/ses_testi.py) AYNI tanıyıcıyı kullanır — test gerçek yolu ölçsün."""
    import json
    import vosk
    return vosk.KaldiRecognizer(model, sample_rate,
                                json.dumps(UYANDIRMA_GRAMERI, ensure_ascii=False))


def uyandirma_sonucu_mu(sonuc_json: str) -> bool:
    """KaldiRecognizer.Result() çıktısında "hey" hemen ardından "ultra" var mı?

    ⚠️ Eskiden tek başına "ultra" yetiyordu. Gramer kilidi her sesi bu üç
    seçenekten birine zorladığı için sıradan cümleler de "ultra" çıkıyordu.
    Ölçüm (16 Eyl, edge-tts 2 ses × 3 hız, 150 örnek):
        kural                 "hey ultron"   yalnız "ultron"   sıradan cümlede tetik
        "ultra" geçsin           12/12           4/6              17/131  (%13)
        "hey ultra" art arda     12/12           0/6               4/131  (%3)
    Yanlış tetikleyenler: "dolar kaç lira", "ekran görüntüsü al", "ultra hd…".
    Güven puanı (conf) AYIRT ETMİYOR — yanlış tetikler de 1.0 geliyordu.
    Bedeli: yalnız "Ultron" demek artık uyandırmaz (hiç belgelenmemişti,
    ölçümde de yarı yarıya çalışıyordu). Belgelenen ifade "Hey Ultron".
    Ölçümü tekrarlamak için: python scripts/ses_testi.py
    """
    import json
    try:
        metin = json.loads(sonuc_json or '{}').get('text', '')
    except ValueError:
        return False
    kelimeler = metin.split()
    return any(a == 'hey' and b == 'ultra' for a, b in zip(kelimeler, kelimeler[1:]))


def vosk_yaziya_cevir(pcm: bytes, sample_rate: int):
    """16-bit mono PCM → serbest metin (çevrimdışı). Model yoksa / ses yoksa None.

    Ölçüm (16 Eyl): edge-tts "hava durumu nasıl" → Vosk birebir aynı metni verdi,
    model yüklemesi 0,4 sn. Doğruluk tablosu için: python scripts/ses_testi.py
    """
    model = vosk_modeli()
    if model is None or not pcm:
        return None
    import json
    import vosk
    rec = vosk.KaldiRecognizer(model, sample_rate)
    adim = sample_rate * 2          # 2 bayt/örnek → ~1 sn'lik parçalar
    for i in range(0, len(pcm), adim):
        rec.AcceptWaveform(pcm[i:i + adim])
    metin = json.loads(rec.FinalResult()).get('text', '').strip()
    return metin or None


def pcm_yaziya_cevir(pcm: bytes, sample_rate: int, sample_width: int = 2):
    """Ham PCM'i yazıya çevirir. Dönüş: (metin | None, motor | None, hata | None).

    motor: 'google' | 'vosk'. Sıra:
      • Google anlarsa → Google metni.
      • Google "anlaşılamadı" derse → None (Vosk'a SORULMAZ: Google'ın
        anlamadığı sesten Vosk'un ürettiği metin çoğunlukla uydurma komuttur).
      • Google'a ULAŞILAMAZSA (internet yok, 429, zaman aşımı) → Vosk.
        Eskiden bu durumda sesli komut sessizce hiçbir şey yapmıyordu.
    """
    sr = _sr()
    audio = sr.AudioData(pcm, sample_rate, sample_width)
    try:
        metin = sr.Recognizer().recognize_google(audio, language='tr-TR')
        return ((metin or '').strip() or None), 'google', None
    except sr.UnknownValueError:
        return None, 'google', None
    except sr.RequestError as e:
        google_hatasi = e

    metin = vosk_yaziya_cevir(audio.get_raw_data(convert_width=2), sample_rate)
    if metin:
        return metin, 'vosk', None
    if vosk_modeli() is None:
        return None, None, (f"Google konuşma tanımaya ulaşılamadı ({google_hatasi}) "
                            f"ve çevrimdışı model (models/vosk-tr) bulunamadı.")
    return None, 'vosk', None


def ogg_sesi_yaziya_cevir_ayrintili(ogg_path: str):
    """Telegram sesli mesajı (OGG/Opus) → (metin, motor, hata). Bkz. pcm_yaziya_cevir."""
    try:
        import soundfile as sf
        data, rate = sf.read(ogg_path, dtype='int16')
        if getattr(data, 'ndim', 1) > 1:
            data = data[:, 0]
    except Exception as e:
        print(f"[TAU STT] Sesli mesaj çözülemedi: {e}")
        return None, None, f"Ses dosyası okunamadı: {e}"
    try:
        return pcm_yaziya_cevir(data.tobytes(), rate, 2)
    except Exception as e:
        print(f"[TAU STT] Sesli mesaj yazıya çevrilemedi: {e}")
        return None, None, str(e)


def ogg_sesi_yaziya_cevir(ogg_path: str):
    """Geriye uyumlu kısa yol: yalnız metin (veya None)."""
    return ogg_sesi_yaziya_cevir_ayrintili(ogg_path)[0]


def sesli_yanit_dosyasi_uret(text: str):
    """Cevabı Telegram SESLİ NOTU olarak gönderilecek dosyaya çevirir.

    edge-tts (Ahmet) mp3 üretir → soundfile ile OGG/Opus'a çevrilir: Telegram
    sesli not balonunu (dalga formu) OGG/Opus ile gösterir. Çevirme başarısızsa
    mp3 yolu döner (sendVoice mp3'ü de kabul eder). Hiç üretilemezse None.
    Metin `tts_metin_temizle` ile kısaltılır — masaüstünde okunanla aynı özet.
    Dosyayı SİLMEK çağıranın işidir.
    """
    t = tts_metin_temizle(text)
    if not t:
        return None
    import asyncio
    import edge_tts

    kok = os.path.join(tempfile.gettempdir(), f'ultron_sesli_yanit_{int(time.time() * 1000)}')
    mp3 = kok + '.mp3'
    try:
        async def _gen():
            await edge_tts.Communicate(t, voice="tr-TR-AhmetNeural",
                                       rate="+4%", pitch="-8Hz").save(mp3)
        asyncio.run(_gen())
    except Exception as e:
        print(f"[Ultron TTS] Sesli yanıt üretilemedi: {e}")
        try:
            os.remove(mp3)
        except Exception:
            pass
        return None

    ogg = kok + '.ogg'
    try:
        import soundfile as sf
        data, rate = sf.read(mp3, dtype='int16')
        sf.write(ogg, data, rate, format='OGG', subtype='OPUS')
    except Exception as e:
        print(f"[Ultron TTS] OGG/Opus'a çevrilemedi, mp3 gönderilecek: {e}")
        return mp3
    try:
        os.remove(mp3)
    except Exception:
        pass
    return ogg


def dinle_ve_yaziya_cevir(device_index=None):
    """Geriye uyumlu kısa yol: küçük harf metin (veya None)."""
    metin = dinle_ve_yaziya_cevir_ayrintili(device_index)[0]
    return metin.lower() if metin else None


def dinle_ve_yaziya_cevir_ayrintili(device_index=None):
    """Mikrofondan dinler → (metin, motor, hata). Bkz. pcm_yaziya_cevir.
    Konuşma gelmezse (zaman aşımı) üçü de None — bu bir hata değil.
    device_index: PortAudio aygıt indeksi (None/-1 = sistem varsayılanı)."""
    r = _sr().Recognizer()

    r.dynamic_energy_threshold = True
    # İNSANCA DİNLEME AYARLARI:
    # pause_threshold: cümle bitti saymadan önce beklenen sessizlik (varsayılan 0.8sn
    # çok agresif — düşünme duraksamasında kesiyordu). 2sn = rahat konuşma.
    r.pause_threshold = 2.0
    r.non_speaking_duration = 0.7

    if device_index in (None, -1):
        device_index = None

    # Seçili mikrofon açılamazsa (BT kulaklık modu vb.) sistem varsayılanına düş
    if device_index is not None:
        try:
            test_mic = _sr().Microphone(device_index=device_index)
            with test_mic as _s:
                pass
        except Exception as e:
            print(f"[TAU STT] Seçili mikrofon ({device_index}) açılamadı, varsayılana geçildi: {e}")
            device_index = None

    try:
        with _sr().Microphone(device_index=device_index) as source:
            print("Dinleniyor... (Konuşabilirsiniz)")
            # Ortam gürültüsünü hızlıca ölç (uzun tutunca dinlemeye geç başlıyor)
            r.adjust_for_ambient_noise(source, duration=0.6)
            # timeout: konuşmaya başlamak için süre; phrase_time_limit: tek cümle tavanı
            audio = r.listen(source, timeout=8, phrase_time_limit=30)
    except _sr().WaitTimeoutError:
        print("Zaman aşımı: Ses algılanamadı.")
        return None, None, None
    except Exception as e:
        print(f"Mikrofon hatası: {e}")
        return None, None, f"Mikrofon hatası: {e}"

    print("Ses işleniyor...")
    metin, motor, hata = pcm_yaziya_cevir(
        audio.get_raw_data(), audio.sample_rate, audio.sample_width)
    print(f"Algılanan ({motor}): {metin}")
    return metin, motor, hata



 