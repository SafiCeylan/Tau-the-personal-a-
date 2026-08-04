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
from core.paths import veri_yolu

APP_CACHE_PATH = veri_yolu('app_cache.json')

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

    def _bas(vk, kez):
        for _ in range(kez):
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)

    if action == "mute":
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
        return True, "🔇 Sistem sesi değiştirildi."
    elif action == "set":
        # Mutlak ayar: her tuş adımı ~%2. Önce garanti 0'a indir (50 adım aşağı),
        # sonra hedefe kadar çık. Böylece "%30 yap" gerçekten %30'a ayarlar,
        # mevcut seviyenin üstüne EKLEMEZ.
        target_pct = max(0, min(100, percent if percent is not None else 50))
        _bas(VK_VOLUME_DOWN, 50)
        _bas(VK_VOLUME_UP, int(round(target_pct / 2)))
        return True, f"🔊 Sistem sesi **%{target_pct}** seviyesine ayarlandı."
    elif action == "up":
        _bas(VK_VOLUME_UP, int(percent / 2) if percent else 10)
        return True, f"🔊 Sistem sesi artırıldı."
    elif action == "down":
        _bas(VK_VOLUME_DOWN, int(percent / 2) if percent else 10)
        return True, f"🔉 Sistem sesi kısıldı."


# =========================================================================
# MEDYA KONTROLÜ — YouTube Music, Spotify, tarayıcı: hepsinde çalışır
# =========================================================================
# Windows medya tuşlarını simüle eder. Uygulamaya özel API gerekmez; hangi
# oynatıcı öndeyse/aktifse onu kontrol eder (donanım medya tuşuyla aynı yol).
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

MEDIA_ACTIONS = {
    "playpause": (VK_MEDIA_PLAY_PAUSE, "⏯️ Oynat/Duraklat gönderildi."),
    "pause": (VK_MEDIA_PLAY_PAUSE, "⏸️ Müzik duraklatıldı."),
    "play": (VK_MEDIA_PLAY_PAUSE, "▶️ Müzik devam ediyor."),
    "next": (VK_MEDIA_NEXT, "⏭️ Sonraki şarkıya geçildi."),
    "prev": (VK_MEDIA_PREV, "⏮️ Önceki şarkıya dönüldü."),
    "stop": (VK_MEDIA_STOP, "⏹️ Oynatma durduruldu."),
}


def medya_kontrol(action: str):
    """
    Medya oynatmayı kontrol eder (duraklat/devam/sonraki/önceki/durdur).

    Not: Windows medya tuşu sinyali gönderir — YouTube Music, Spotify,
    VLC, tarayıcı sekmesi fark etmez, aktif oynatıcı yanıt verir.
    """
    if sys.platform != 'win32':
        return False, "Medya kontrolü şu an sadece Windows'ta destekleniyor."

    islem = MEDIA_ACTIONS.get(action)
    if not islem:
        return False, f"Bilinmeyen medya komutu: {action}"

    vk, mesaj = islem
    KEYEVENTF_KEYUP = 0x0002
    try:
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True, mesaj
    except Exception as e:
        return False, f"Medya kontrolü başarısız: {e}"


def medya_komutu_algila(mesaj: str):
    """
    Mesajdan medya komutunu çıkarır → action adı veya None.

    ÖNEMLİ: "şarkı çal" gibi YENİ müzik başlatma istekleri buraya DÜŞMEMELİ
    (onlar PLAY_MUSIC'e gider). Burada sadece ZATEN çalan medyanın kontrolü var.
    """
    m = (mesaj or "").lower().strip()
    if not m:
        return None

    # Şarkı adı içeren "X çal" gibi istekler medya kontrolü değil, yeni oynatmadır
    if re.search(r'\b(çal|aç)\b', m) and any(
            k in m for k in ["şarkı", "müzik", "youtube", "parça", "albüm"]):
        # "müziği devam ettir/durdur" hariç — onlar kontroldür
        if not any(k in m for k in ["devam", "durdur", "duraklat", "duraklat", "geç"]):
            return None

    if any(k in m for k in ["sonraki şarkı", "şarkıyı geç", "diğer şarkı", "next",
                            "sonraki parça", "şarkı geç", "geç bunu", "bunu geç"]):
        return "next"
    # ⚠️ "geri al" BURADA DEĞİL. Türkçede "geri al" ezici çoğunlukla UNDO
    # (Ctrl+Z) demektir; önceki şarkı için "önceki şarkı"/"başa sar" denir.
    # Burada durduğu sürece "geri al" komutu klavyeye hiç ulaşamıyordu.
    if any(k in m for k in ["önceki şarkı", "bir önceki", "previous",
                            "önceki parça", "baştan çal", "başa sar"]):
        return "prev"
    if any(k in m for k in ["müziği durdur", "şarkıyı durdur", "durdur müziği",
                            "duraklat", "pause", "müziği duraklat", "sesi kes müzik"]):
        return "pause"
    if any(k in m for k in ["devam ettir", "müziği devam", "devam et müzik",
                            "resume", "kaldığı yerden", "müziği aç"]):
        return "play"
    if any(k in m for k in ["oynat/duraklat", "play pause", "playpause"]):
        return "playpause"
    if any(k in m for k in ["müziği kapat", "oynatmayı durdur", "medyayı durdur"]):
        return "stop"
    return None


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


def _zaten_acik_mi(app_name_clean: str) -> bool:
    """World State'e sorar (Faz 6). Hata olursa False — şüphedeysek işi yaparız."""
    try:
        from core.world_state import uygulama_calisiyor_mu
        return uygulama_calisiyor_mu(app_name_clean)
    except Exception as e:
        print(f"[Ultron WorldState] Durum sorulamadı: {e}")
        return False


def uyg_bul_ve_ac(app_name: str):
    """
    Uygulamayı açar. World State (Faz 6) ile zenginleştirilmiş sarmalayıcı.

    ⚠️ Uygulama ZATEN AÇIKSA komut İPTAL EDİLMEZ — başlatıcı yine çağrılır
    (Windows'ta bu mevcut pencereyi öne getirir), sadece mesaj farklı olur.
    "Zaten açık" deyip hiçbir şey yapmamak, kullanıcının komutunu sessizce
    yutmaktır; yanlış tespitte Ultron bozulmuş gibi görünür.
    """
    zaten_acik = _zaten_acik_mi(app_name.lower().strip())
    basarili, mesaj = _uyg_bul_ve_ac(app_name)

    if basarili and zaten_acik and mesaj and 'başlatılıyor' in mesaj:
        mesaj = mesaj.replace('başlatılıyor', 'zaten açıktı, öne getiriyorum')
        mesaj = mesaj.replace('🚀', 'ℹ️')
    return basarili, mesaj


def _uyg_bul_ve_ac(app_name: str):
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


def _kelime_var(mesaj: str, kelimeler) -> bool:
    """
    Kelime SINIRIYLA arar (`in` DEĞİL).

    Alt dizi araması canlıda iki kez yanlış tetikledi:
      • "sesimin ..."     → içinde "min" geçiyor → ses %10'a düşüyordu
      • "sesi kesinlikle" → içinde "kes" geçiyor → ses susturuluyordu
    Projenin `\\bac\\b` dersi burada da geçerli.
    """
    return any(re.search(r'\b' + re.escape(k) + r'\b', mesaj) for k in kelimeler)


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

    # Yazım Hatalarını Otomatik Düzelt (chorome -> chrome, spotifi -> spotify, yao -> yap vb.)
    typos = {
        r'\bchorome\b': 'chrome',
        r'\bcrom\b': 'chrome',
        r'\bspotifi\b': 'spotify',
        r'\byutube\b': 'youtube',
        r'\bhesp\b': 'hesap',
        r'\byao\b': 'yap',
        r'\byukse\b': 'yükselt',
        r'\byuksel\b': 'yükselt',
        r'\byüksel\b': 'yükselt',
        r'\barttir\b': 'artır',
        r'\barttır\b': 'artır',
    }
    for pattern, replacement in typos.items():
        mesaj = re.sub(pattern, replacement, mesaj)

    # 1. Sistem Kaynak & Durum Raporu (CPU, RAM, Disk, Pil)
    if any(k in mesaj for k in ["sistem", "donanım", "ram", "cpu", "bellek", "işlemci"]) and any(k in mesaj for k in ["durum", "bilgi", "kullanım", "rapor", "neler", "nasıl"]):
        return True, sistem_durumu_raporu()

    # 2. Birebir & Oransal Akıllı Ses Kontrolü
    #    Kapı KELİME SINIRIYLA açılır: "sesli mesaj" ses komutu değildir.
    if re.search(r'\b(ses|sesi|sesin|sesini|sesim|sesimi|sesine|sesler|sessiz|sessize|'
                 r'volume|kökle|kokle|fulle)\b', mesaj):
        # Yüzde: ya açık işaret (%, "yüzde", "... seviye") ya da bir AYARLAMA
        # fiiliyle birlikte gelen sayı. Çıplak `(\d+)` her sayıyı yüzde sayıyordu:
        # "ses 5 saniye gecikmeli geliyor" sesi %5'e çekiyordu.
        pct_match = re.search(r'(?:%|yüzde)\s*(\d{1,3})|(\d{1,3})\s*(?:%|kadar|seviye|seviyesi|seviyesine)', mesaj)
        percent = int(pct_match.group(1) or pct_match.group(2)) if pct_match else None
        if percent is None and _kelime_var(mesaj, ["yap", "ayarla", "getir", "olsun", "çek"]):
            sayi = re.search(r'\b(\d{1,3})\b', mesaj)
            percent = int(sayi.group(1)) if sayi else None
        if percent is not None:
            percent = max(0, min(100, percent))

        # Max / Full ("en yüksek", "maksimum", "max", "full", "kökle", "son ses", "tavan")
        # NOT: kelime sınırına geçince çekimli biçimler AÇIKÇA yazılmalı —
        # "ful" alt dizisi eskiden "fulle"yi de yakalıyordu, artık yakalamaz.
        if _kelime_var(mesaj, ["en yüksek", "en yuksek", "maksimum", "max", "full", "ful",
                               "fulle", "fulla", "kökle", "kokle", "köklet", "son ses",
                               "son seviye", "tavan", "tamamını aç", "tam ac", "tam aç"]):
            return sistem_sesi_kontrol("set", 100)

        # Min / Low ("en düşük", "minimum", "min", "dip")
        if _kelime_var(mesaj, ["en düşük", "en dusuk", "minimum", "min", "dip"]):
            return sistem_sesi_kontrol("set", 10 if percent is None else percent)

        # Mute
        if _kelime_var(mesaj, ["kapat", "sessiz", "sessize", "sessizle", "kapa",
                               "mute", "sıfırla", "sustur", "kes"]):
            return sistem_sesi_kontrol("mute")

        # Set / Absolute ("sesi %49 yap", "sesi 50 yap", "ses seviyesini 50 yap")
        if _kelime_var(mesaj, ["yap", "ayarla", "seviyesine getir", "seviyesine yap", "getir", "olsun"]) \
                or (percent is not None and not _kelime_var(mesaj, ["kıs", "düşür", "azalt", "yükselt", "artır", "yukselt", "arttir"])):
            return sistem_sesi_kontrol("set", percent if percent is not None else 50)

        # Volume Down
        if _kelime_var(mesaj, ["kıs", "düşür", "azalt", "indir", "dusur", "kis"]):
            return sistem_sesi_kontrol("down", percent)

        # Volume Up
        if _kelime_var(mesaj, ["aç", "yükselt", "artır", "çoğalt", "yukselt", "arttir",
                               "cogalt", "yüksel", "yuksel", "yükseltme", "yükseltin"]):
            return sistem_sesi_kontrol("up", percent)

        # ❗ Genel "ses geçiyorsa bir şey yap" kestirmesi YOK. Ne yapılacağı
        # anlaşılmadıysa ses seviyesine dokunulmaz — cümle akışın devamına
        # (ve gerekirse LLM'e) bırakılır. Sessizce sesi değiştirmek, kullanıcının
        # sormadığı bir eylemi yapmaktır.

    # 3. Bilgisayarı Kilitleme / Güvenlik
    if "bilgisayarı kilitle" in mesaj or "ekranı kilitle" in mesaj or "oturumu kilitle" in mesaj:
        return bilgisayar_kilitle()

    # 3.5 Uyku modu — Telegram menüsündeki "🌙 Uyku Modu" butonunun karşılığı.
    #     Karşılığı olmayan buton, LLM'in "uykuya aldım" diye uydurması demektir.
    if _kelime_var(mesaj, ["uykuya", "uyut", "uyku moduna"]):
        return bilgisayar_uyut()

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


def bilgisayar_uyut():
    """Bilgisayarı uyku moduna alır (hazırda bekletme açıksa hibernate olur)."""
    if sys.platform != 'win32':
        return False, "Uyku modu sadece Windows üzerinde desteklenmektedir."
    try:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return True, "🌙 Bilgisayar uyku moduna alınıyor. Uyandırmak için `kilit aç` diyebilirsin."
    except Exception as e:
        return False, f"⚠️ Uyku moduna alınamadı: {e}"


def bilgisayar_kilitle():
    if sys.platform == 'win32':
        ctypes.windll.user32.LockWorkStation()
        return True, "🔒 Bilgisayar ekranı ve oturumu kilitlendi."
    return False, "Ekran kilitleme sadece Windows üzerinde desteklenmektedir."
