import os
import speech_recognition as sr
from gtts import gTTS
import pygame
import time

import subprocess

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
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filename)
        except Exception as e:
            print(f"gTTS ses oluşturma hatası: {e}")
            return

        # 1. Yöntem: Pygame ile oynatmayı dene
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            
            # Çalma bitene kadar bekle
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            pygame.mixer.quit()
            
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

def dinle_ve_yaziya_cevir():
    """Mikrofondan sesi dinler ve yazıya çevirir (Online - Google)"""
    r = sr.Recognizer()
    
    r.dynamic_energy_threshold = True
    
    try:
        with sr.Microphone() as source:
            print("Dinleniyor... (Konuşabilirsiniz)")
            # Ortam gürültüsünü ayarla (Biraz daha uzun süre dinlesin)
            r.adjust_for_ambient_noise(source, duration=1.0)
            # Sesi dinle
            audio = r.listen(source, timeout=5, phrase_time_limit=15)
            
            print("Ses işleniyor...")
            # Google Speech API ile yazıya çevir
            text = r.recognize_google(audio, language='tr-TR')
            print(f"Algılanan: {text}")
            return text.lower()
            
    except sr.WaitTimeoutError:
        print("Zaman aşımı: Ses algılanamadı.")
        return None
    except sr.UnknownValueError:
        print("Anlaşılamadı.")
        return None
    except sr.RequestError as e:
        print(f"Google Speech API hatası: {e}")
        return None
    except Exception as e:
        print(f"Mikrofon hatası: {e}")
        return None

 