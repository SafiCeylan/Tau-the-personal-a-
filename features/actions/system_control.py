import os
import sys
import subprocess
import platform
import webbrowser
import ctypes
import psutil
import re
import json
import threading
import time
from datetime import datetime

# Bulunan uygulamaların cache'i — her seferinde yavaş disk taraması yapılmasın
APP_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'app_cache.json'
)

# Windows PyCaw Volume API Support
try:
    from pycaw.pycaw import AudioUtilities
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False


def sistem_sesi_getir() -> int:
    """Mevcut Windows ana ses seviyesini yüzde (0-100) olarak döndürür."""
    if PYCAW_AVAILABLE and sys.platform == 'win32':
        try:
            speakers = AudioUtilities.GetSpeakers()
            volume = speakers.EndpointVolume
            return round(volume.GetMasterVolumeLevelScalar() * 100)
        except Exception as e:
            print(f"[Ultron Volume Read Error]: {e}")
    return 50  # Varsayılan fallback


def sistem_sesi_kontrol(action: str, percent: int = None):
    """
    PyCaw ve Win32 API ile Birebir Mutlak (Absolute) ve Oransal Ses Kontrolü.
    """
    if sys.platform != 'win32':
        return False, "Ses kontrolü sadece Windows işletim sisteminde desteklenmektedir."

    # "sesi ayarla" gibi yüzdesiz mutlak ayar komutlarında makul varsayılan kullan
    if action == "set" and percent is None:
        percent = 50

    current_vol = sistem_sesi_getir()

    if PYCAW_AVAILABLE:
        try:
            speakers = AudioUtilities.GetSpeakers()
            volume = speakers.EndpointVolume

            if action == "mute":
                volume.SetMute(1, None)
                return True, "🔇 Sistem sesi sessize alındı."

            elif action == "set" and percent is not None:
                target_pct = max(0, min(100, percent))
                volume.SetMute(0, None)
                volume.SetMasterVolumeLevelScalar(target_pct / 100.0, None)
                return True, f"🔊 Sistem sesi **%{target_pct}** seviyesine ayarlandı."

            elif action == "down":
                delta = percent if percent is not None else 15
                target_pct = max(0, current_vol - delta)
                volume.SetMute(0, None)
                volume.SetMasterVolumeLevelScalar(target_pct / 100.0, None)
                return True, f"🔉 Sistem sesi %{current_vol} seviyesinden **%{target_pct}** seviyesine düşürüldü."

            elif action == "up":
                delta = percent if percent is not None else 15
                target_pct = min(100, current_vol + delta)
                volume.SetMute(0, None)
                volume.SetMasterVolumeLevelScalar(target_pct / 100.0, None)
                return True, f"🔊 Sistem sesi %{current_vol} seviyesinden **%{target_pct}** seviyesine yükseltildi."

        except Exception as e:
            print(f"[Ultron PyCaw Error]: {e}")

    # Fallback to keybd_event Hardware Signals if PyCaw encounters issues
    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF
    KEYEVENTF_KEYUP = 0x0002

    if action == "mute":
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
        return True, "🔇 Sistem sesi değiştirildi."
    elif action in ("set", "up"):
        steps = int(percent / 2) if percent else 10
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)
        return True, f"🔊 Sistem sesi artırıldı."
    elif action == "down":
        steps = int(percent / 2) if percent else 10
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)
        return True, f"🔉 Sistem sesi kısıldı."


def _load_app_cache() -> dict:
    try:
        with open(APP_CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_app_cache(cache: dict):
    try:
        with open(APP_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Ultron AppCache] Cache yazılamadı: {e}")


def _get_start_apps() -> dict:
    """
    PowerShell Get-StartApps ile yüklü TÜM uygulamaları listeler.
    Microsoft Store (UWP) uygulamaları dahildir (WhatsApp, Spotify Store sürümü vb.)
    — bunların Başlat Menüsü'nde .lnk dosyası olmadığından dizin taramasıyla bulunamazlar.
    Dönen değer: {uygulama_adı_küçük_harf: AppID}
    """
    if sys.platform != 'win32':
        return {}
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"],
            capture_output=True, timeout=15, creationflags=flags
        )
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout.decode('utf-8', errors='replace'))
            if isinstance(data, dict):
                data = [data]
            return {
                item['Name'].lower().strip(): item['AppID']
                for item in data
                if item.get('Name') and item.get('AppID')
            }
    except Exception as e:
        print(f"[Ultron StartApps] Uygulama listesi alınamadı: {e}")
    return {}


def _launch_appid(app_id: str):
    """AppID üzerinden başlatır — klasik uygulamalar ve UWP/Store uygulamaları için çalışır."""
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])


def uyg_bul_ve_ac(app_name: str):
    """
    Uygulama bulma sırası:
      0. Cache (önceden bulunanlar — anında açılış)
      1. Get-StartApps (UWP/Store dahil tüm Başlat Menüsü uygulamaları, ~1-2 sn)
      2. Dizin taraması (.lnk / .exe — Program Files, AppData; yavaş fallback)
      3. Bilinen sabit komutlar (spotify:, calc vb.)
    """
    app_name_clean = app_name.lower().strip()

    # 0. Cache: daha önce bulunduysa anında aç
    cache = _load_app_cache()
    cached = cache.get(app_name_clean)
    if cached:
        try:
            if cached.get('type') == 'appid':
                _launch_appid(cached['target'])
                return True, f"🚀 **{app_name.title()}** uygulaması başlatılıyor..."
            if os.path.exists(cached.get('target', '')):
                os.startfile(cached['target'])
                return True, f"🚀 **{app_name.title()}** uygulaması başlatılıyor...\n`[{os.path.basename(cached['target'])}]`"
        except Exception:
            pass
        # Ölü cache kaydı — temizle ve normal aramaya devam et
        cache.pop(app_name_clean, None)
        _save_app_cache(cache)

    # 1. Get-StartApps: UWP/Store uygulamaları dahil (WhatsApp bugu burada çözülür)
    start_apps = _get_start_apps()
    matched_appid = None
    matched_name = None
    # Eşleşme önceliği: tam eşleşme > adın başında > adın içinde herhangi bir yerde.
    # ("zen" araması "kayıt defteri düZENleyicisi"ne değil "Zen" tarayıcısına gitmeli)
    if app_name_clean in start_apps:
        matched_appid = start_apps[app_name_clean]
        matched_name = app_name_clean
    else:
        for name, app_id in start_apps.items():
            if name.startswith(app_name_clean):
                matched_appid = app_id
                matched_name = name
                break
        if not matched_appid:
            for name, app_id in start_apps.items():
                if app_name_clean in name:
                    matched_appid = app_id
                    matched_name = name
                    break

    if matched_appid:
        try:
            _launch_appid(matched_appid)
            cache[app_name_clean] = {'type': 'appid', 'target': matched_appid}
            _save_app_cache(cache)
            return True, f"🚀 **{app_name.title()}** uygulaması başlatılıyor...\n`[{matched_name}]`"
        except Exception as e:
            print(f"[Ultron AppLaunch] AppID başlatma hatası: {e}")

    # 2. Klasik dizin taraması (.lnk / .exe)
    search_dirs = [
        os.path.expandvars(r'%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs'),
        os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs'),
        os.path.expandvars(r'%LOCALAPPDATA%\Programs'),
        r'C:\Program Files',
        r'C:\Program Files (x86)',
    ]

    matched_path = None

    for s_dir in search_dirs:
        if os.path.exists(s_dir):
            for root, dirs, files in os.walk(s_dir):
                for f in files:
                    if f.lower().endswith(('.lnk', '.exe')):
                        f_name = os.path.splitext(f)[0].lower()
                        if app_name_clean == f_name or app_name_clean in f_name:
                            matched_path = os.path.join(root, f)
                            break
                if matched_path:
                    break
        if matched_path:
            break

    if matched_path and sys.platform == 'win32':
        try:
            os.startfile(matched_path)
            cache[app_name_clean] = {'type': 'path', 'target': matched_path}
            _save_app_cache(cache)
            return True, f"🚀 **{app_name.title()}** uygulaması başlatılıyor...\n`[{os.path.basename(matched_path)}]`"
        except Exception as e:
            try:
                subprocess.Popen([matched_path], shell=True)
                cache[app_name_clean] = {'type': 'path', 'target': matched_path}
                _save_app_cache(cache)
                return True, f"🚀 **{app_name.title()}** uygulaması başlatılıyor..."
            except Exception as ex:
                return False, f"Uygulama çalıştırılırken hata: {ex}"

    # Standard Fallback Commands
    if "chrome" in app_name_clean or "google" in app_name_clean:
        webbrowser.open("https://google.com")
        return True, "🌐 Google Chrome başlatılıyor..."
    elif "spotify" in app_name_clean:
        os.system("start spotify:")
        return True, "🎵 Spotify başlatılıyor..."
    elif "hesap" in app_name_clean:
        os.system("calc.exe")
        return True, "🧮 Hesap Makinesi başlatılıyor..."
    elif "not" in app_name_clean:
        os.system("notepad.exe")
        return True, "📝 Not Defteri başlatılıyor..."

    return False, f"⚠️ **'{app_name}'** uygulaması Windows Başlat Menüsünde veya dizinlerde bulunamadı. Lütfen uygulamanın bilgisayarınızda yüklü olduğundan emin olunuz."


def sistem_komutu_algila(mesaj: str):
    """
    Mesaj içerisindeki Windows sistem komutlarını algılar ve çalıştırır.
    Dönen değer: (Başarı Durumu, Yanıt Mesajı)
    """
    # WhatsApp / E-posta komutları — lowercase'ten ÖNCE (mesaj metni korunmalı).
    # Güvenlik onayı sonrası gönderimler de bu yoldan yürütülür.
    try:
        from features.actions.whatsapp_control import whatsapp_komutu_algila
        handled, resp = whatsapp_komutu_algila(mesaj)
        if handled:
            return True, resp
    except Exception as e:
        print(f"[Ultron WhatsApp] Komut işlenirken hata: {e}")
    try:
        from features.email_control import email_komutu_algila
        handled, resp = email_komutu_algila(mesaj)
        if handled:
            return True, resp
    except Exception as e:
        print(f"[Ultron Email] Komut işlenirken hata: {e}")

    mesaj = mesaj.lower().strip()
    is_windows = sys.platform == 'win32' or os.name == 'nt'

    # Yazım Hatalarını Otomatik Düzelt (chorome -> chrome, spotifi -> spotify)
    typos = {
        r'\bchorome\b': 'chrome',
        r'\bcrom\b': 'chrome',
        r'\bspotifi\b': 'spotify',
        r'\byutube\b': 'youtube',
        r'\bhesp\b': 'hesap',
    }
    for pattern, replacement in typos.items():
        mesaj = re.sub(pattern, replacement, mesaj)

    # 1. Sistem Kaynak & Durum Raporu (CPU, RAM, Disk, Pil)
    if any(k in mesaj for k in ["sistem", "donanım", "ram", "cpu", "bellek", "işlemci"]) and any(k in mesaj for k in ["durum", "bilgi", "kullanım", "rapor", "neler", "nasıl"]):
        return True, sistem_durumu_raporu()

    # 2. Birebir & Oransal Akıllı Ses Kontrolü
    if "ses" in mesaj or "volume" in mesaj:
        pct_match = re.search(r'(?:%|yüzde)\s*(\d+)|(\d+)\s*(?:%|kadar)', mesaj)
        percent = int(pct_match.group(1) or pct_match.group(2)) if pct_match else None

        if any(k in mesaj for k in ["kapat", "sessiz", "kapa", "mute", "sıfırla"]):
            return sistem_sesi_kontrol("mute")

        # "sesi %49 yap" / "sesi 50 yap" -> ABSOLUTE SET
        if any(k in mesaj for k in ["yap", "ayarla", "seviyesine getir"]) or (percent is not None and not any(k in mesaj for k in ["kıs", "düşür", "azalt", "yükselt", "artır"])):
            return sistem_sesi_kontrol("set", percent)

        if any(k in mesaj for k in ["kıs", "düşür", "azalt"]):
            return sistem_sesi_kontrol("down", percent)

        if any(k in mesaj for k in ["aç", "yükselt", "artır", "çoğalt"]):
            return sistem_sesi_kontrol("up", percent)

    # 3. Bilgisayarı Kilitleme / Güvenlik
    if "bilgisayarı kilitle" in mesaj or "ekranı kilitle" in mesaj or "oturumu kilitle" in mesaj:
        return bilgisayar_kilitle()

    # 4. Süreç / Uygulama Kapatma (Process Termination)
    if "kapat" in mesaj or "sonlandır" in mesaj or "durdur" in mesaj:
        if "chrome" in mesaj or "tarayıcı" in mesaj:
            return surec_kapat("chrome.exe", "Google Chrome")
        elif "spotify" in mesaj:
            return surec_kapat("Spotify.exe", "Spotify")
        elif "hesap makinesi" in mesaj or "calculator" in mesaj:
            return surec_kapat("CalculatorApp.exe", "Hesap Makinesi")
        elif "not defteri" in mesaj or "notepad" in mesaj:
            return surec_kapat("notepad.exe", "Not Defteri")
        elif "discord" in mesaj:
            return surec_kapat("Discord.exe", "Discord")
        elif "steam" in mesaj:
            return surec_kapat("steam.exe", "Steam")
        elif "zen" in mesaj:
            return surec_kapat("zen.exe", "Zen Browser")
        elif "claude" in mesaj:
            return surec_kapat("claude.exe", "Claude Desktop")

    # 5. Evrensel Uygulama Açma / Başlatma (Zen, Claude, VS Code, Discord, Chrome, Spotify vb.)
    if any(k in mesaj for k in ["aç", "başlat", "çalıştır"]):
        app_name = mesaj
        for kw in ["aç", "başlat", "çalıştır", "uygulamasını", "uygulaması"]:
            app_name = app_name.replace(kw, "")
        app_name = app_name.strip()
        if app_name:
            success, resp = uyg_bul_ve_ac(app_name)
            if success:
                return success, resp

    # 6. YouTube Music & Müzik/Şarkı Çalma Komutları
    muzik_tetik = (
        any(k in mesaj for k in ["youtube music", "youtube müzik", "müzik çal", "şarkı çal",
                                 "müzik aç", "şarkı aç", "çal:"])
        or (re.search(r'\bçal\b', mesaj) and any(k in mesaj for k in ["şarkı", "müzik", "youtube"]))
        or mesaj.endswith(" çal")
    )
    if muzik_tetik:
        # Önce doğal kalıp: "X şarkısını/parçasını ... çal" → şarkı adı X
        m = re.search(r'^(.*?)\s+(?:adlı\s+|isimli\s+)?(?:şarkısını|şarkıyı|şarkısı|parçasını|parçayı|parçası)\b', mesaj)
        if m and m.group(1).strip():
            sarki_sorgu = m.group(1).strip()
        else:
            sarki_sorgu = mesaj
            triggers = ["youtube music'ten", "youtube müzik'ten", "youtube music'den",
                        "youtube müzik'den", "youtube music'te", "youtube müzik'te",
                        "youtube music", "youtube müzik", "müzik çal", "şarkı çal",
                        "müzik aç", "şarkı aç", "çal:", "youtube'dan", "youtube"]
            for trigger in triggers:
                sarki_sorgu = sarki_sorgu.replace(trigger, "")
            # Kalan bağlaç ve fiilleri temizle
            sarki_sorgu = re.sub(r'\b(ile|müzikte|müzikten|üzerinden|oynat|çal)\b', ' ', sarki_sorgu)
        if sarki_sorgu.endswith("çal"):
            sarki_sorgu = sarki_sorgu[:-3]
        sarki_sorgu = re.sub(r'\s+', ' ', sarki_sorgu).strip().strip("'").strip()

        if not sarki_sorgu:
            webbrowser.open("https://music.youtube.com")
            return True, "🎵 **YouTube Music** açılıyor..."

        return sarki_otomatik_baslat(sarki_sorgu)

    # 7. Genel Web Siteleri
    if "youtube" in mesaj and ("aç" in mesaj or "gir" in mesaj):
        webbrowser.open("https://youtube.com")
        return True, "🌐 YouTube açılıyor..."
    
    if "google" in mesaj and ("aç" in mesaj or "gir" in mesaj):
        webbrowser.open("https://google.com")
        return True, "🌐 Google açılıyor..."

    # 8. Bilgisayarı Kapatma Manuel Onayı
    if "evet bilgisayarı kapat" in mesaj:
        if is_windows:
            subprocess.run("shutdown /s /t 15", shell=True)
            return True, "🔴 **SİSTEM KAPANIYOR:** Bilgisayarınız 15 saniye içinde kapatılacaktır."
        return True, "🔴 Bilgisayarı kapatma komutu verildi."

    if "bilgisayarı kapat" in mesaj:
        return False, "⚠️ Bilgisayarı kapatma işlemi kritik risk içerir. Lütfen 'evet bilgisayarı kapat' yazınız."

    return False, None


def surec_kapat(process_name, display_name):
    """Verilen isimdeki Windows sürecini bulur ve kapatır."""
    found = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                proc.kill()
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if sys.platform == 'win32':
        try:
            res = subprocess.run(f"taskkill /F /IM {process_name}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                found = True
        except Exception:
            pass

    if found:
        return True, f"🛑 **{display_name}** uygulaması başarıyla sonlandırıldı."
    else:
        return True, f"ℹ️ **{display_name}** şu anda çalışmıyor."


def sarki_otomatik_baslat(sarki_sorgu: str):
    import urllib.parse
    import requests

    encoded_q = urllib.parse.quote(sarki_sorgu)
    first_id = None
    try:
        url = f"https://www.youtube.com/results?search_query={encoded_q}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            v_ids = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', res.text)
            if v_ids:
                first_id = v_ids[0]
    except Exception as e:
        print(f"[Ultron Song Player Error]: {e}")

    if first_id:
        play_url = f"https://music.youtube.com/watch?v={first_id}"
        webbrowser.open(play_url)

        def _trigger_play():
            # AIP Level 4 disiplini: Space tuşu SADECE YouTube Music sekmesi
            # gerçekten öndeyse gönderilir (körlemesine tuş basma yok).
            time.sleep(2.2)
            if sys.platform == 'win32':
                from core.interaction import level4_input
                VK_SPACE = 0x20
                VK_MEDIA_PLAY_PAUSE = 0xCD
                KEYEVENTF_KEYUP = 0x0002

                if level4_input.wait_for_foreground("youtube music", timeout=8):
                    ctypes.windll.user32.keybd_event(VK_SPACE, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)
                    time.sleep(0.05)
                else:
                    print("[Ultron Music] YouTube Music sekmesi öne gelmedi — Space gönderilmedi.")

                # Medya tuşu globaldir (aktif medya oturumuna gider) — odaktan bağımsız güvenlidir
                ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)

        threading.Thread(target=_trigger_play, daemon=True).start()
        return True, f"🎵 **YouTube Music** üzerinden **'{sarki_sorgu.title()}'** şarkısı doğrudan başlatılıyor..."

    webbrowser.open(f"https://music.youtube.com/search?q={encoded_q}")
    return True, f"🎵 **YouTube Music** üzerinden **'{sarki_sorgu.title()}'** aranıyor..."


def sistem_durumu_raporu():
    try:
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:' if sys.platform == 'win32' else '/')

        ram_used_gb = round(ram.used / (1024**3), 1)
        ram_total_gb = round(ram.total / (1024**3), 1)

        disk_free_gb = round(disk.free / (1024**3), 1)
        disk_total_gb = round(disk.total / (1024**3), 1)

        battery_info = ""
        battery = psutil.sensors_battery()
        if battery:
            plugged = "Şarjda ⚡" if battery.power_plugged else "Pilde 🔋"
            battery_info = f"\n• Pil Durumu: %{battery.percent} ({plugged})"

        return (
            f"📊 **ULTRON TELEMETRİ RAPORU**\n\n"
            f"• CPU Yükü: **%{cpu}**\n"
            f"• RAM Kullanımı: **%{ram.percent}** ({ram_used_gb} GB / {ram_total_gb} GB)\n"
            f"• C: Disk Boş Alan: **{disk_free_gb} GB** / {disk_total_gb} GB"
            f"{battery_info}"
        )
    except Exception as e:
        return f"Sistem bilgisi alınırken hata: {e}"


def bilgisayar_kilitle():
    if sys.platform == 'win32':
        ctypes.windll.user32.LockWorkStation()
        return True, "🔒 Bilgisayar ekranı ve oturumu kilitlendi."
    return False, "Ekran kilitleme sadece Windows üzerinde desteklenmektedir."
