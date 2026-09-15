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
_DUPLEX_ACTIVE = False
_DUPLEX_LOCK = threading.Lock()


def is_duplex_voice_active() -> bool:
    with _DUPLEX_LOCK:
        return _DUPLEX_ACTIVE


def set_duplex_voice_active(active: bool) -> bool:
    global _DUPLEX_ACTIVE
    with _DUPLEX_LOCK:
        _DUPLEX_ACTIVE = active
        return _DUPLEX_ACTIVE


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

def ogg_sesi_yaziya_cevir(ogg_path: str):
    """
    Telegram sesli mesajını (OGG/Opus) yazıya çevirir.
    soundfile (libsndfile) ile PCM'e çözülür → Google STT (tr-TR).
    Dönen değer: metin veya None.
    """
    try:
        import soundfile as sf
        data, rate = sf.read(ogg_path, dtype='int16')
        if getattr(data, 'ndim', 1) > 1:
            data = data[:, 0]
        audio = _sr().AudioData(data.tobytes(), rate, 2)
        r = _sr().Recognizer()
        text = r.recognize_google(audio, language='tr-TR')
        return (text or '').strip() or None
    except _sr().UnknownValueError:
        return None
    except Exception as e:
        print(f"[TAU STT] Sesli mesaj çözülemedi: {e}")
        return None


def dinle_ve_yaziya_cevir(device_index=None):
    """Mikrofondan sesi dinler ve yazıya çevirir (Online - Google).
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
            
            print("Ses işleniyor...")
            # Google Speech API ile yazıya çevir
            text = r.recognize_google(audio, language='tr-TR')
            print(f"Algılanan: {text}")
            return text.lower()
            
    except _sr().WaitTimeoutError:
        print("Zaman aşımı: Ses algılanamadı.")
        return None
    except _sr().UnknownValueError:
        print("Anlaşılamadı.")
        return None
    except _sr().RequestError as e:
        print(f"Google Speech API hatası: {e}")
        return None
    except Exception as e:
        print(f"Mikrofon hatası: {e}")
        return None



 