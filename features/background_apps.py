"""
Arka Plan Uygulamaları Yönetim Motoru (Background Apps Manager).

1. Arka planda çalışan kullanıcı uygulamalarını tespit eder, temiz numaralı liste oluşturur.
2. Numaraya (örn. "3'ü kapat") veya isme (örn. "Zen kapat") göre uygulamaları sonlandırır.
3. İnteraktif konuşma takibi ("Başka kapatmamı istediğin var mı?") sunar.

⚠️ EN ÖNEMLİ KURAL — BU MODÜL SADECE AÇIK BİR KAPATMA KOMUTUYLA ÖLDÜRÜR.
   `arka_plan_komutu_isle()` ilgisiz cümlelerde None döner, akış bozulmaz.
   Eskiden "bekleyen soru" bayrağı kalıcıydı ve SYSTEM_CONTROL'e düşen HER mesaj
   katile giriyordu; içeride de cümledeki herhangi bir sayı liste indeksi
   sayılıyordu. Sonuç: "saat 3'te hatırlat" listedeki 3. uygulamayı kapatıyor,
   "chrome aç" (Chrome zaten açıkken) Chrome'u öldürüyordu.
   Bu yüzden: (a) bayrak TEK TURLUK, (b) sayı yalnız kapatma fiiliyle birlikte
   veya cevap sırasında tek başına geçerli, (c) cümlede açma fiili varsa kapatma
   HİÇ denenmez.
"""

import re
import sys
import psutil
from typing import List, Dict, Any, Optional, Tuple

# Sistem ve altyapı süreçleri (kullanıcıya gösterilmez)
SYSTEM_EXCLUDE = {
    'explorer.exe', 'svchost.exe', 'lsass.exe', 'csrss.exe', 'smss.exe',
    'services.exe', 'wininit.exe', 'winlogon.exe', 'taskhostw.exe',
    'dwm.exe', 'sihost.exe', 'ctfmon.exe', 'fontdrvhost.exe', 'searchhost.exe',
    'startmenuexperiencehost.exe', 'shellexperiencehost.exe', 'runtimebroker.exe',
    'system', 'idle', 'system idle process', 'conhost.exe', 'py.exe', 'python.exe',
    'pytest.exe', 'pythonw.exe', 'ultron.exe', 'registry', 'memory compression',
    'securityhealthservice.exe', 'mpcmdrun.exe', 'msmpeng.exe', 'searchindexer.exe',
    'spoolsv.exe', 'igfxcuiservice.exe', 'audiodg.exe', 'smartscreen.exe',
    'wlanext.exe', 'searchprotocolhost.exe', 'searchfilterhost.exe', 'applicationframehost.exe',
    'language_server.exe', 'wslservice.exe', 'nvcontainer.exe', 'mscopilot_proxy.exe',
    'systemsettings.exe', 'textinputhost.exe', 'lockapp.exe', 'crossdeviceservice.exe',
    'crossdeviceresume.exe', 'widgetservice.exe', 'widgets.exe', 'monotificationux.exe',
    'nis_srv.exe', 'nissrv.exe', 'gameinputredistservice.exe', 'gamingservices.exe',
    'gamingservicesnet.exe', 'igcc.exe', 'igcctray.exe', 'servicehost.exe', 'uihost.exe',
    # Gömülü tarayıcı / yardımcı süreçler: kullanıcı uygulaması değil, bileşen.
    'msedgewebview2.exe', 'crashpad_handler.exe', 'wmiprvse.exe', 'dllhost.exe',
    'unsecapp.exe', 'backgroundtaskhost.exe', 'phoneexperiencehost.exe',
}

# Şık uygulama adı eşlemeleri
APP_DISPLAY_NAMES = {
    "zen.exe": "Zen Browser",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave Browser",
    "opera.exe": "Opera",
    "code.exe": "VS Code",
    "spotify.exe": "Spotify",
    "telegram.exe": "Telegram",
    "whatsapp.exe": "WhatsApp",
    "discord.exe": "Discord",
    "notepad.exe": "Not Defteri",
    "vlc.exe": "VLC Media Player",
    "claude.exe": "Claude Desktop",
    "snippingtool.exe": "Ekran Alıntısı Aracı",
    "nextcloud.exe": "Nextcloud",
    "ollama app.exe": "Ollama AI Engine",
    "docker desktop.exe": "Docker Desktop",
    "docker.exe": "Docker Desktop",
    "com.docker.backend.exe": "Docker Engine",
    "calculatorapp.exe": "Hesap Makinesi",
    "steam.exe": "Steam",
}

# Kanal başına son liste ve "başka var mı?" bayrağı. Telefondan gelen "3'ü kapat",
# masaüstünde yapılmış listelemenin 3. uygulamasını kapatmasın (projedeki
# `ctx.kanal` konvansiyonu — features/file_send.py ile aynı gerekçe).
_SON_LISTE: Dict[str, List[Dict[str, Any]]] = {}
_BEKLEYEN_SORU: Dict[str, bool] = {}

_KAPATMA_FIILLERI = r'kapat\w*|kapaat\w*|kapatt\w*|sonlandır\w*|sonlandir\w*|bitir\w*|öldür\w*|oldur\w*'
_ACMA_FIILLERI = r'\b(aç|ac|açar|başlat\w*|baslat\w*|çalıştır\w*|calistir\w*|geç|gec|getir)\b'
_VAZGECME = r'\b(hayır|hayir|yok|yeter|istemiyorum|kapatma|gerek\s+yok|boş\s+ver|bos\s+ver|iptal|sağol|sagol|teşekkür\w*|tesekkur\w*|tamam)\b'
# Sayı + (en fazla birkaç ek/karakter) + kapatma fiili → "3'ü kapat", "2'yi de kapat"
_SAYI_KAPAT = re.compile(r'\b(\d{1,2})\b[^\d]{0,10}?\b(?:' + _KAPATMA_FIILLERI + r')', re.IGNORECASE)
# Cevap sırasında tek başına numara → "3", "3'ü", "2."
_SADECE_SAYI = re.compile(r'^\s*(\d{1,2})\s*[\.\'’]?\s*[a-zçğıöşü]{0,4}\s*$', re.IGNORECASE)
# Listeleme istekleri
_LISTELEME = re.compile(r'arka\s*plan|çalışan\s+uygulama|calisan\s+uygulama|neler\s+açık|'
                        r'neler\s+çalışıyor|hangi\s+uygulamalar', re.IGNORECASE)


def _pencereli_pidler() -> set:
    """Görünür ve başlıklı bir penceresi olan süreçlerin PID'leri."""
    if sys.platform != 'win32':
        return set()
    try:
        import ctypes
        user32 = ctypes.windll.user32
        pids = set()

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                pids.add(pid.value)
            return True

        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(CMPFUNC(enum_cb), 0)
        return pids
    except Exception:
        return set()


def çalışan_uygulamaları_getir() -> List[Dict[str, Any]]:
    """
    Arka planda çalışan KULLANICI uygulamalarını döner.

    Filtre: görünür penceresi olan süreçler + bilinen masaüstü uygulamaları.
    (Aksi halde `msedgewebview2.exe`, `node.exe`, "System Idle Process" gibi
    altyapı süreçleri kullanıcı uygulamasıymış gibi numaralı listeye giriyordu.)
    """
    pencereli = _pencereli_pidler()
    kayitlar: Dict[str, Dict[str, Any]] = {}

    for p in psutil.process_iter(['pid', 'name', 'exe', 'memory_info']):
        try:
            name = p.info['name']
            if not name:
                continue
            n_lower = name.lower()
            if n_lower in SYSTEM_EXCLUDE or 'ultron' in n_lower or 'python' in n_lower:
                continue

            exe_path = (p.info['exe'] or '').lower()
            if exe_path.startswith('c:\\windows\\system32') or exe_path.startswith('c:\\windows\\syswow64'):
                continue

            bilinen = n_lower in APP_DISPLAY_NAMES
            # Windows'ta pencere sahibi olmayan ve bilinmeyen süreçler listelenmez.
            if pencereli and not bilinen and p.info['pid'] not in pencereli:
                continue

            mem_mb = round((p.info['memory_info'].rss if p.info['memory_info'] else 0) / (1024 * 1024), 1)
            mevcut = kayitlar.get(n_lower)
            if mevcut:
                # Aynı uygulamanın çok süreçli hâli (Chrome sekmeleri) tek satır,
                # RAM'i toplanmış görünsün.
                mevcut['mem_mb'] = round(mevcut['mem_mb'] + mem_mb, 1)
                if p.info['pid'] in pencereli:
                    mevcut['pid'] = p.info['pid']
                continue

            kayitlar[n_lower] = {
                "proc_name": name,
                "display_name": APP_DISPLAY_NAMES.get(n_lower) or name.replace('.exe', '').capitalize(),
                "pid": p.info['pid'],
                "mem_mb": mem_mb,
                "exe": p.info['exe'] or "",
            }
        except Exception:
            pass

    return list(kayitlar.values())


def _liste_metni(apps: List[Dict[str, Any]], baslik: str = "📱 **ARKA PLANDA ÇALIŞAN UYGULAMALAR:**") -> str:
    satirlar = [baslik + "\n"]
    for idx, app in enumerate(apps, 1):
        satirlar.append(f"{idx}. 💻 **{app['display_name']}** (`{app['proc_name']}`) — RAM: `{app['mem_mb']} MB`")
    satirlar.append("\n💡 *Kapatmak istediğin uygulamanın adını veya numarasını söyleyebilirsin "
                    "(Örn: `3'ü kapat`, `Docker kapat`).*")
    return "\n".join(satirlar)


def arka_plan_listesi_olustur(kanal: str = "desktop") -> str:
    """Arka planda çalışan uygulamaları numaralı liste olarak hazırlar."""
    apps = çalışan_uygulamaları_getir()
    _SON_LISTE[kanal] = apps
    _BEKLEYEN_SORU[kanal] = bool(apps)

    if not apps:
        return "ℹ️ Arka planda çalışan harici kullanıcı uygulaması bulunamadı."
    return _liste_metni(apps)


def _hedef_coz(mesaj: str, kanal: str, bekleyen: bool) -> Optional[Dict[str, Any]]:
    """Cümleden kapatılacak uygulamayı çözer. Emin değilse None (hiçbir şey öldürülmez)."""
    liste = _SON_LISTE.get(kanal) or []
    kapatma_var = re.search(_KAPATMA_FIILLERI, mesaj, re.IGNORECASE) is not None

    # 1. Numara — YALNIZCA kapatma fiiliyle birlikte ya da soruya verilen
    #    tek kelimelik cevapta. ("saat 3'te hatırlat" burada hedef üretmez.)
    num_eslesme = _SAYI_KAPAT.search(mesaj) if kapatma_var else None
    if not num_eslesme and bekleyen:
        num_eslesme = _SADECE_SAYI.match(mesaj)
    if num_eslesme:
        idx = int(num_eslesme.group(1)) - 1
        if 0 <= idx < len(liste):
            return liste[idx]
        return None

    # 2. İsim — yalnızca açık kapatma fiili varsa.
    if kapatma_var:
        for app in liste:
            disp = app['display_name'].lower()
            proc = app['proc_name'].lower().replace('.exe', '')
            if disp in mesaj or (len(proc) >= 3 and proc in mesaj):
                return app
    return None


def arka_plan_uygulamasi_kapat(mesaj: str, kanal: str = "desktop") -> Tuple[bool, str]:
    """Numarayla veya adıyla uygulamayı kapatır ve sonraki adımı sorar."""
    m = (mesaj or "").strip()
    m_lower = m.lower()

    # Bayrak TEK TURLUK: soruya verilen cevap okunur okunmaz düşer. Böylece
    # bir sonraki alakasız cümle katile giremez.
    bekleyen = _BEKLEYEN_SORU.get(kanal, False)
    _BEKLEYEN_SORU[kanal] = False

    kapatma_var = re.search(_KAPATMA_FIILLERI, m_lower) is not None

    # "hayır / gerek yok / tamam" → süreci bitir (kapatma fiili yoksa)
    if not kapatma_var and re.search(_VAZGECME, m_lower):
        return True, "👍 Anlaşıldı! Diğer uygulamalar açık bırakıldı."

    # Açma/odaklanma cümlesi asla kapatma sayılmaz ("chrome aç", "zen'e geç")
    if re.search(_ACMA_FIILLERI, m_lower) and not kapatma_var:
        return False, "🔍 Kapatma komutu anlaşılmadı."

    if not _SON_LISTE.get(kanal):
        _SON_LISTE[kanal] = çalışan_uygulamaları_getir()

    # Docker: tek uygulama değil, süreç ailesi
    if "docker" in m_lower and kapatma_var:
        from features.actions.system_control import surec_kapat
        surec_kapat("Docker Desktop.exe", "Docker Desktop")
        surec_kapat("com.docker.backend.exe", "Docker Engine")
        surec_kapat("docker", "Docker", parcali=True)
        _SON_LISTE[kanal] = çalışan_uygulamaları_getir()
        cevap = "✅ **Docker Desktop** ve ilişkili tüm süreçleri sonlandırıldı."
        if _SON_LISTE[kanal]:
            _BEKLEYEN_SORU[kanal] = True
            cevap += "\n\n" + _liste_metni(_SON_LISTE[kanal],
                                           "❓ **Başka kapatmamı istediğin var mı? Güncel liste:**")
        return True, cevap

    hedef_app = _hedef_coz(m_lower, kanal, bekleyen)

    if not hedef_app:
        return False, ("🔍 Kapatılacak uygulama bulunamadı. Lütfen listedeki bir numarayı veya "
                       "uygulama adını söyleyin (Örn: `3'ü kapat` veya `Docker kapat`).")

    from features.actions.system_control import surec_kapat
    surec_kapat(hedef_app['proc_name'], hedef_app['display_name'])

    # Liste her kapatmadan sonra DEĞİŞİR; numaralar kaymasın diye güncel hâli
    # kullanıcıya tekrar gösterilir. (Eskiden sessizce yenileniyordu ve
    # "2'yi de kapat" kullanıcının gördüğünden başka uygulamayı vuruyordu.)
    _SON_LISTE[kanal] = çalışan_uygulamaları_getir()

    if _SON_LISTE[kanal]:
        _BEKLEYEN_SORU[kanal] = True
        return True, (f"✅ **{hedef_app['display_name']}** kapatıldı.\n\n"
                      + _liste_metni(_SON_LISTE[kanal],
                                     "❓ **Başka kapatmamı istediğin var mı? Güncel liste:**"))

    return True, f"✅ **{hedef_app['display_name']}** kapatıldı. Arka planda çalışan başka uygulama kalmadı!"


def bekleyen_kapatma_sorusu_var_mi(kanal: str = "desktop") -> bool:
    return _BEKLEYEN_SORU.get(kanal, False)


def arka_plan_komutu_isle(mesaj: str, kanal: str = "desktop") -> Optional[Tuple[bool, str]]:
    """
    TEK GİRİŞ NOKTASI — hem `sistem_komutu_algila` hem araç defteri burayı çağırır.
    (İkiz mantık iki yerde durunca biri düzeltilip diğeri eskiyordu.)

    Komut arka plan yönetimiyle ilgili değilse **None** döner; akış bozulmaz.
    """
    m = (mesaj or "").strip()
    if not m:
        return None
    m_lower = m.lower()

    if _LISTELEME.search(m_lower):
        return True, arka_plan_listesi_olustur(kanal)

    bekleyen = _BEKLEYEN_SORU.get(kanal, False)
    kapatma_var = re.search(_KAPATMA_FIILLERI, m_lower) is not None
    acma_var = re.search(_ACMA_FIILLERI, m_lower) is not None

    # Açık kapatma komutu (numara veya isimle) → sadece listedeki bir hedefe
    # denk geliyorsa üstlenilir; yoksa None dönüp normal akışa bırakılır.
    if kapatma_var and not acma_var:
        if not _SON_LISTE.get(kanal):
            _SON_LISTE[kanal] = çalışan_uygulamaları_getir()
        if _hedef_coz(m_lower, kanal, bekleyen):
            return arka_plan_uygulamasi_kapat(m, kanal)
        return None

    # "Başka var mı?" sorusuna verilen kısa cevap ("2", "hayır")
    if bekleyen and (_SADECE_SAYI.match(m_lower) or re.search(_VAZGECME, m_lower)):
        return arka_plan_uygulamasi_kapat(m, kanal)

    return None
