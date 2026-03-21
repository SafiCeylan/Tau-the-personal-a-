import os
import subprocess
import platform
import webbrowser
from datetime import datetime

def sistem_komutu_algila(mesaj):
    """
    Mesaj içerisindeki sistem komutlarını algılar ve çalıştırır.
    Dönen değer: (Başarı Durumu, Yanıt Mesajı)
    """
    mesaj = mesaj.lower()
    
    # 1. Uygulama Açma
    if "aç" in mesaj or "başlat" in mesaj:
        if "chrome" in mesaj or "tarayıcı" in mesaj:
            return uyg_ac("google-chrome") # Linux için genelde google-chrome veya chromium
        elif "spotify" in mesaj:
            return uyg_ac("spotify")
        elif "hesap makinesi" in mesaj:
            return uyg_ac("gnome-calculator") # Gnome için
        elif "terminal" in mesaj or "konsol" in mesaj:
            return uyg_ac("gnome-terminal")
        elif "dosya" in mesaj and "yöneticisi" in mesaj:
            return uyg_ac("nautilus")
            
    # 2. Web Siteleri
    if "youtube" in mesaj and ("aç" in mesaj or "gir" in mesaj):
        webbrowser.open("https://youtube.com")
        return True, "YouTube açılıyor..."
    
    if "google" in mesaj and ("aç" in mesaj or "gir" in mesaj):
        webbrowser.open("https://google.com")
        return True, "Google açılıyor..."

    # 3. Sistem Kontrolü (Dikkatli olmalı)
    if "bilgisayarı kapat" in mesaj:
        # Güvenlik için şimdilik sadece mesaj dönelim, direkt kapatmayalım
        return False, "Bilgisayarı kapatma yetkim var ama şu an için bu özellik güvenlik nedeniyle devre dışı."
        
    return False, None

def uyg_ac(komut):
    """Verilen komutu terminalde çalıştırarak uygulamayı açar."""
    try:
        subprocess.Popen(komut.split())
        return True, f"{komut} başlatılıyor..."
    except FileNotFoundError:
        return False, f"{komut} bulunamadı. Yüklü olduğundan emin misin?"
    except Exception as e:
        return False, f"Hata oluştu: {e}"
