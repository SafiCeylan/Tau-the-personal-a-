"""
AIP Level 4 — Klavye/Fare Emülasyonu (SON ÇARE).

En kırılgan katman: koordinata/odağa bağımlıdır. Bu yüzden buradaki her tuş
gönderimi ODAK KORUMALIDIR — hedef pencere önde değilse tuş GÖNDERİLMEZ.
(Yanlış pencereye Enter basmak = felaket senaryosu.)
"""

import ctypes
import re
import sys
import time

VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def foreground_window_title() -> str:
    """Şu an odaklı (önde) olan pencerenin başlığını döner."""
    if sys.platform != 'win32':
        return ""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def wait_for_foreground(title_contains: str, timeout: float = 10.0) -> bool:
    """Hedef pencere öne gelene kadar bekler. Gelmezse False (tuş gönderme!)."""
    deadline = time.time() + timeout
    needle = title_contains.lower()
    while time.time() < deadline:
        if needle in foreground_window_title().lower():
            return True
        time.sleep(0.4)
    return False


def press_enter(require_title_contains: str = None, timeout: float = 10.0) -> bool:
    """
    Odak korumalı Enter: require_title_contains verilmişse, o pencere önde
    olmadan ASLA tuş gönderilmez.
    """
    if sys.platform != 'win32':
        return False
    if require_title_contains:
        if not wait_for_foreground(require_title_contains, timeout):
            print(f"[AIP L4] Odak koruması: '{require_title_contains}' önde değil, Enter iptal.")
            return False
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
    return True


def press_paste(require_title_contains: str = None, timeout: float = 10.0) -> bool:
    """
    Odak korumalı Ctrl+V. Panoya konan DOSYAYI hedef uygulamaya yapıştırmak için
    kullanılır (WhatsApp'a dosya ekleme). Enter ile aynı koruma: hedef pencere
    önde değilse tuş GÖNDERİLMEZ — yanlış pencereye yapıştırmak veri sızdırabilir.
    """
    if sys.platform != 'win32':
        return False
    if require_title_contains:
        if not wait_for_foreground(require_title_contains, timeout):
            print(f"[AIP L4] Odak koruması: '{require_title_contains}' önde değil, Ctrl+V iptal.")
            return False
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    return True


VK_MAP = {
    'control': 0x11, 'ctrl': 0x11, 'strg': 0x11,
    'alt': 0x12, 'menu': 0x12,
    'shift': 0x10,
    'win': 0x5B, 'windows': 0x5B,
    'enter': 0x0D, 'return': 0x0D, 'entera': 0x0D,
    'esc': 0x1B, 'escape': 0x1B,
    'tab': 0x09,
    'space': 0x20, 'bosluk': 0x20, 'boşluk': 0x20,
    'backspace': 0x08, 'sil': 0x08,
    'delete': 0x2E, 'del': 0x2E,
    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
    'printscreen': 0x2C, 'prtscr': 0x2C, 'prtsc': 0x2C, 'snapshot': 0x2C,
    'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'pgup': 0x21, 'pagedown': 0x22, 'pgdn': 0x22,
    'insert': 0x2D, 'ins': 0x2D,
    'capslock': 0x14, 'numlock': 0x90, 'scrolllock': 0x91,
    'volume_mute': 0xAD, 'mute': 0xAD,
    'volume_down': 0xAE, 'voldown': 0xAE,
    'volume_up': 0xAF, 'volup': 0xAF,
    'media_next': 0xB0, 'nexttrack': 0xB0,
    'media_prev': 0xB1, 'prevtrack': 0xB1,
    'media_stop': 0xB2,
    'media_play_pause': 0xB3, 'playpause': 0xB3,
}
for ch in 'abcdefghijklmnopqrstuvwxyz':
    VK_MAP[ch] = ord(ch.upper())
for num in '0123456789':
    VK_MAP[num] = ord(num)
for i in range(1, 13):
    VK_MAP[f'f{i}'] = 0x6F + i


def execute_native_hotkey(mods: list, keys: list) -> bool:
    """Win32 hardware level keybd_event execution for modifier hotkeys."""
    if sys.platform != 'win32':
        return False
    mod_vks = [VK_MAP[m] for m in mods if m in VK_MAP]
    key_vks = [VK_MAP[k] for k in keys if k in VK_MAP]

    if not (mod_vks or key_vks):
        return False

    try:
        # 1. Press all modifier keys
        for vk in mod_vks:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)

        # 2. Press & release target key items
        for vk in key_vks:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.02)
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)

        # 3. Release modifier keys in reverse order
        time.sleep(0.03)
        for vk in reversed(mod_vks):
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

        return True
    except Exception as e:
        print(f"[AIP L4] Native hotkey error: {e}")
        return False


KEYEVENTF_SCANCODE = 0x0008


def send_pure_scancode(vk: int):
    """
    Saf Donanım Tara Kodu (Pure Hardware Scan Code).
    Windows Winlogon / Kilit Ekranı (LogonUI) sanal VK kodlarını tamamen engeller.
    bVk parametresi 0 verilmeli ve dwFlags = KEYEVENTF_SCANCODE olmalıdır.
    Bu sinyal işletim sistemine fiziksel klavye tuşu olarak ulaşır.
    """
    if sys.platform != 'win32':
        return
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)

    # Physical Key Down (bVk = 0, wScan = scan, dwFlags = KEYEVENTF_SCANCODE)
    ctypes.windll.user32.keybd_event(0, scan, KEYEVENTF_SCANCODE, 0)
    time.sleep(0.04)
    # Physical Key Up (bVk = 0, wScan = scan, dwFlags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)
    ctypes.windll.user32.keybd_event(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
    time.sleep(0.04)


def check_is_admin() -> bool:
    """Sürecin Yönetici (Administrator) yetkisiyle çalışıp çalışmadığını kontrol eder."""
    if sys.platform != 'win32':
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def pin_maskele(pin: str) -> str:
    """
    PIN/şifreyi mesajda GÖSTERME. Dönen mesaj Telegram'a (bulut) gidiyor ve
    `sohbet_gecmisi` tablosuna loglanıyor — düz metin PIN iki yerde kalıcı olurdu.
    Sadece uzunluk bilgisi verilir, karakterler verilmez.
    """
    if not pin:
        return "(sadece ekran uyandırıldı)"
    return "•" * len(pin) + f" ({len(pin)} karakter)"


def unlock_windows_screen(pin_or_pass: str = "") -> tuple[bool, str]:
    """
    Windows kilit / uyku ekranını saf donanım tara kodları (Pure ScanCode) ile uyandırır,
    kilit animasyonu (1.2s) sonrası PIN/şifreyi yazar ve Enter ile kilit açar.
    """
    if sys.platform != 'win32':
        return False, "Kilit açma sadece Windows sistemlerde desteklenmektedir."

    is_admin = check_is_admin()

    try:
        # 1. Ekranı uyandır (Saf Donanım ScanCode ile Space bas)
        send_pure_scancode(0x20)

        # 2. Windows kilit ekranı kayma animasyonu ve PIN kutusunun odağı için 1.2 sn bekle
        time.sleep(1.2)

        # 3. Varsa PIN/şifre karakterlerini saf donanım scancode ile yaz
        if pin_or_pass:
            for char in pin_or_pass:
                char_lower = char.lower()
                if char_lower in VK_MAP:
                    vk = VK_MAP[char_lower]
                    send_pure_scancode(vk)

            # 4. PIN sonrası Enter basıp kilidi aç
            time.sleep(0.2)
            send_pure_scancode(VK_RETURN)

        admin_note = "" if is_admin else "\n\n⚠️ **[GÜVENLİK NOTU]** Windows Kilit Ekranı (Winlogon Security Desktop), varsayılan kullanıcı seviyesinde tuş kısıtlamasına sahip olabilir. Tam uyumluluk için ULTRON'un **Yönetici Olarak Çalıştırılması** önerilir."

        return True, (
            f"🔓 **[WINDOWS KİLİT AÇMA DİZİSİ GÖNDERİLDİ]**\n"
            f"• Ekran uyarısı: `SPACE` (Pure Hardware ScanCode)\n"
            f"• Animasyon beklemesi: `1.2 sn` tamamlandı.\n"
            f"• PIN/Şifre: `{pin_maskele(pin_or_pass)}` (Hardware ScanCode)\n"
            f"• Tamamlama: `ENTER` basıldı.{admin_note}"
        )
    except Exception as e:
        print(f"[AIP L4] Unlock error: {e}")
        return False, f"Kilit açılırken hata oluştu: {e}"


# =========================================================================
# RİSK SINIFLANDIRMASI
#
# Klavye emülasyonu tek başına "güvenli" değildir: hangi pencerenin önde
# olduğunu ULTRON seçmiyor, kullanıcı da telefondayken göremiyor. Geri
# alınamayan tuşlar bu yüzden güvenlik katmanında ONAY kartına bağlanır
# (`SecurityAnalyzerLayer` bu fonksiyonu çağırır — kural TEK yerde dursun).
# =========================================================================
TEHLIKELI_KALIPLAR = (
    (r'\balt\s*\+\s*f4\b', 'pencere kapatma (Alt+F4)'),
    (r'\bctrl\s*\+\s*shift\s*\+\s*w\b', 'tüm pencereyi kapatma (Ctrl+Shift+W)'),
    (r'\bctrl\s*\+\s*w\b', 'sekme/pencere kapatma (Ctrl+W)'),
    (r'\bctrl\s*\+\s*q\b', 'uygulamadan çıkış (Ctrl+Q)'),
    (r'\bwin\s*\+\s*l\b', 'oturum kilitleme (Win+L)'),
    (r'\b(delete|del)\b', 'silme tuşu (Delete)'),
    (r'\bkilit\s*(aç|ac)\b', 'Windows kilit ekranını açma'),
    (r'^(şifre|sifre|pin)\s*(gir)?\s*:', 'PIN/şifre girişi'),
    (r'^(yaz|type)\s*:', 'ekrana serbest metin yazma'),
    (r'\byaz$', 'ekrana serbest metin yazma'),
)


# Bir cümlenin "tuş isteği" sayılması için gereken AÇIK işaretler.
# Niyet katmanı da onaylı komut yürütücüsü de BURAYI kullanır — kalıp
# iki yere kopyalanırsa biri güncellenir, diğeri sessizce eskir.
KLAVYE_KALIPLARI = (
    r'^(yaz\s*:|type\s*:|tuş\s*:|tus\s*:|klavye\s*:|press\s*:|kilit\s*:|şifre\s*:|sifre\s*:|pin\s*:)',
    r'\bkili(t|di)\s*(aç|ac)\b',
    r'\b(ctrl|alt|shift|win|windows)\s*\+\s*[a-z0-9]',
    # Artı işaretini yazmayan kullanıcı: "ctrl c yap", "alt tab". İkinci parça
    # BİLİNEN bir tuş olmalı — yoksa "alt satır", "alt tarafta" da yakalanırdı.
    r'\b(ctrl|alt|shift|win|windows)\s+(?:[a-z0-9]|f\d{1,2}|tab|esc|enter|del|delete|space)\b',
    r'\b(tuş|tus|klavye|kombinasyon)\w*\s+(bas|bastır|bastir|gönder|yolla)\b',
    # Tuş adı + eylem. `\s*` ekiyle "f5 e bas" (ayrı yazılmış ek) de girer;
    # önceden yalnızca bitişik/kesme işaretli hâli ("f5'e bas") kabul ediliyordu.
    r"\b(enter|space|tab|esc|escape|backspace|delete|insert|home|end|pgup|pgdn"
    r"|yukarı|yukari|aşağı|asagi|f\d{1,2})(?:\s*'?[a-zçğıöşü]{0,3})?"
    r"\s*(ok|tuşuna|tusuna)?\s*(bas|bastır|bastir|gönder|yolla)\b",
    # Salt rakam + enter ("1234 enter"): sohbet cümlesi olamaz, PIN/kod yazma biçimi.
    r"^[0-9\s]+enter('?a)?$",
)


def klavye_komutu_mu(metin: str) -> bool:
    """Cümle açık bir tuş isteği mi? ('yeni tab aç' DEĞİL, 'tab bas' EVET)

    Kalıplara ek olarak doğal dil kısayolları da ("kopyala", "geri al",
    "sekmeyi kapat") buradan geçer — kullanıcı `ctrl+c` yazmak zorunda değil.
    """
    t = (metin or '').strip().lower()
    if any(re.search(kalip, t) for kalip in KLAVYE_KALIPLARI):
        return True
    return dogal_kisayol_coz(t) is not None


def riskli_tus_mu(metin: str) -> tuple[bool, str]:
    """Geri alınamayan tuş isteklerini işaretler → (riskli_mi, sebep)."""
    t = (metin or '').strip().lower()
    for kalip, sebep in TEHLIKELI_KALIPLAR:
        if re.search(kalip, t):
            return True, sebep
    return False, ''


KULLANIM_REHBERI = (
    "⌨️ **Tuş isteği anlaşılmadı — hiçbir tuşa basılmadı.**\n"
    "Desteklenen biçimler:\n"
    "• `tuş: ctrl+s` — tuş kombinasyonu\n"
    "• `enter bas` · `alt+f4 bas` · `f5 bas`\n"
    "• `yaz: merhaba dünya` — ekrana metin yazar\n"
    "• `1234 enter` — rakamları yazıp Enter'a basar\n"
    "• `kilit aç: 1234` — kilit ekranını açar"
)

# send_keys sembolleri. Windows tuşunun send_keys karşılığı yok (None) —
# o kombinasyonlar yalnızca native keybd_event yoluyla gönderilebilir.
_MOD_MAP = {'ctrl': '^', 'control': '^', 'strg': '^', 'alt': '%', 'shift': '+',
            'win': None, 'windows': None}
_KEY_MAP = {
    'enter': '{ENTER}', 'return': '{ENTER}', 'entera': '{ENTER}',
    'esc': '{ESC}', 'escape': '{ESC}', 'tab': '{TAB}',
    'space': '{SPACE}', 'bosluk': '{SPACE}', 'boşluk': '{SPACE}',
    'backspace': '{BACKSPACE}', 'sil': '{BACKSPACE}',
    'delete': '{DELETE}', 'del': '{DELETE}',
    'up': '{UP}', 'down': '{DOWN}', 'left': '{LEFT}', 'right': '{RIGHT}',
    # Türkçe yön tuşları — "yukarı ok bas" gibi cümleler için
    'yukari': '{UP}', 'yukarı': '{UP}', 'asagi': '{DOWN}', 'aşağı': '{DOWN}',
    'sol': '{LEFT}', 'sag': '{RIGHT}', 'sağ': '{RIGHT}',
    # Gezinme tuşları — hiç tanımlı değildi
    'home': '{HOME}', 'end': '{END}',
    'pgup': '{PGUP}', 'pgdn': '{PGDN}', 'pageup': '{PGUP}', 'pagedown': '{PGDN}',
    'insert': '{INSERT}', 'ins': '{INSERT}',
    'printscreen': '{PRTSC}', 'prtsc': '{PRTSC}',
}

# ---------------------------------------------------------------------------
# DOĞAL DİL KISAYOLLARI
#
# Kimse "ctrl+c bas" demez; "kopyala" der. Bu tablo günlük Türkçeyi kanonik
# kombinasyona çevirir. Kapı (`KLAVYE_KALIPLARI`) da buradan üretilir, yani
# yeni bir satır eklemek hem anlamayı hem yürütmeyi aynı anda açar.
#
# ⚠️ ÇAKIŞMAYA DİKKAT: buraya eklenen ifade başka bir niyetin cümlesini
# çalmamalı. Bu yüzden "bul" (dosya arama), "kapat" (uygulama kapatma) ve
# "seç" gibi çıplak fiiller BİLEREK yok — sadece tek anlama gelen kalıplar var.
# ---------------------------------------------------------------------------
_DOGAL_KISAYOLLAR = (
    (r'\bhepsini\s+se[çc]|t[üu]m[üu]n[üu]\s+se[çc]', 'ctrl+a'),
    (r'\bgeri\s+al\b|\bundo\b', 'ctrl+z'),
    (r'\bileri\s+al\b|\byinele\b|\bredo\b', 'ctrl+y'),
    (r'\bkopyala\b', 'ctrl+c'),
    (r'\byap[ıi]şt[ıi]r\b|\byapistir\b', 'ctrl+v'),
    # Sadece ÇIPLAK "kes" — "sesi kes" ses kısma komutudur, Ctrl+X değil.
    (r'^\s*kes\s*$|\bmetni\s+kes\b', 'ctrl+x'),
    (r'\bkaydet\b', 'ctrl+s'),
    (r'\byazd[ıi]r\b', 'ctrl+p'),
    (r'\bsekmeyi\s+kapat\b', 'ctrl+w'),
    (r'\byeni\s+sekme\b', 'ctrl+t'),
    (r'\bkapanan\s+sekmeyi\s+a[çc]\b', 'ctrl+shift+t'),
    (r'\byenile\b|\bsayfay[ıi]\s+yenile\b', 'f5'),
    (r'\btam\s+ekran\b', 'f11'),
    (r'\bg[öo]rev\s+y[öo]neticisi', 'ctrl+shift+esc'),
    # ⚠️ "masaüstünü göster" BİLEREK yok: o cümle "masaüstündeki dosyaları
    # listele" anlamına da geliyor ve dosya kapısı onu haklı olarak alıyor.
    # Win+D için tek anlama gelen ifadeler kullanılır.
    (r'\bmasa[üu]st[üu]ne\s+d[öo]n\b|\bt[üu]m\s+pencereleri\s+k[üu][çc][üu]lt\b', 'win+d'),
    (r'\buygulama\s+de[ğg]i[şs]tir\b|\balt\s*tab\b', 'alt+tab'),
    (r'\bsayfa\s+ba[şs][ıi]na\s+git\b|\bba[şs]a\s+git\b', 'ctrl+home'),
    (r'\bsayfa\s+sonuna\s+git\b|\bsona\s+git\b', 'ctrl+end'),
    (r'\bsayfa\s+a[şs]a[ğg][ıi]\b', 'pgdn'),
    (r'\bsayfa\s+yukar[ıi]\b', 'pgup'),
    (r'\byak[ıi]nla[şs]t[ıi]r\b', 'ctrl+plus'),
    (r'\buzakla[şs]t[ıi]r\b', 'ctrl+minus'),
)


def dogal_kisayol_coz(metin: str):
    """'kopyala' → 'ctrl+c'. Eşleşme yoksa None."""
    m = (metin or '').lower().strip()
    if not m:
        return None
    for kalip, kombinasyon in _DOGAL_KISAYOLLAR:
        if re.search(kalip, m):
            return kombinasyon
    return None


def _bosluklu_kombinasyon(metin: str) -> str:
    """'ctrl c' → 'ctrl+c'. Artı işaretini yazmayan kullanıcı için.

    Sadece İLK kelime bir değiştirici tuşsa uygulanır — "shift ile yaz" gibi
    cümleler yanlışlıkla kombinasyona çevrilmesin.
    """
    parcalar = metin.split()
    if len(parcalar) < 2 or '+' in metin:
        return metin
    if parcalar[0].lower() in _MOD_MAP and all(len(p) <= 12 for p in parcalar):
        return '+'.join(parcalar)
    return metin


def yaziyi_kacir(metin: str) -> str:
    """
    send_keys ÖZEL KARAKTERLERİNİ düz metne çevirir.

    pywinauto'da `^`=Ctrl, `%`=Alt, `+`=Shift, `~`=Enter, `{}`/`()` grup demektir.
    Ham metni kaçırmadan göndermek, "merhaba %50" yazdırmak isterken ALT
    kombinasyonu bastırmak anlamına gelir.
    """
    ozel = {'{': '{{}', '}': '{}}', '^': '{^}', '%': '{%}', '+': '{+}',
            '~': '{~}', '(': '{(}', ')': '{)}', '[': '{[}', ']': '{]}'}
    return ''.join(ozel.get(ch, ch) for ch in metin)


def _kilit_niyeti_coz(raw: str):
    """
    Kilit açma isteğini AÇIK niyetle çözer → PIN metni ya da None.

    ⚠️ Gevşek ayrıştırma tehlikelidir: eski sürüm "şifre nedir" cümlesinde
    "nedir" kelimesini PIN sanıp ekrana yazıyordu. Bu yüzden yalnızca
    "kilit aç" ifadesi ya da iki nokta ile verilen açık PIN kabul edilir.
    """
    t = raw.strip()

    # "kilit aç: 1234" / "kilit ac : 1234"
    m = re.match(r'^kilit\s*(?:aç|ac)\s*(?:gir)?\s*:\s*(\S+)$', t, re.IGNORECASE)
    if m:
        return m.group(1)

    # "şifre: 1234" / "pin gir: 1234" — iki nokta ZORUNLU
    m = re.match(r'^(?:şifre|sifre|pin)\s*(?:gir)?\s*:\s*(\S+)$', t, re.IGNORECASE)
    if m:
        return m.group(1)

    # "1234 ile kilit aç"
    m = re.match(r'^(\S+)\s+ile\s+kilit\s*(?:aç|ac)$', t, re.IGNORECASE)
    if m:
        return m.group(1)

    # Sadece ekranı uyandır: "kilit aç", "kilidi aç"
    if re.match(r'^kili(?:t|di)\s*(?:aç|ac)$', t, re.IGNORECASE):
        return ''

    return None


def _send_keys_gonder(pattern: str, combo_text: str, active_title: str,
                      with_spaces: bool = False) -> tuple[bool, str]:
    """send_keys sarmalayıcısı. Başarısızlıkta BAŞARISIZ döner — 'gönderildi' demez."""
    try:
        from pywinauto.keyboard import send_keys
    except Exception as e:
        return False, f"⌨️ Klavye gönderimi için `pywinauto` gerekli: {e}"

    try:
        send_keys(pattern, pause=0.05, with_spaces=with_spaces)
    except Exception as e:
        print(f"[AIP L4] Keyboard send_keys hatası: {e}")
        # ❗ Eski sürüm burada körlemesine ENTER basıp yine "gönderildi" diyordu.
        # Hangi pencerenin önde olduğu bilinmezken hata sonrası Enter basmak,
        # rastgele bir diyaloğu onaylamaktır.
        return False, (
            f"⌨️ **Tuş gönderilemedi.**\n"
            f"• Girdi: `{combo_text}`\n"
            f"• Denenen kalıp: `{pattern}`\n"
            f"• Hata: {e}"
        )

    return True, (
        f"⌨️ **[KLAVYE İNPUTU GÖNDERİLDİ]**\n"
        f"• Girdi: `{combo_text}`\n"
        f"• Basılan Kalıp: `{pattern}`\n"
        f"• Aktif Pencere: **{active_title}**"
    )


def send_keyboard_input(combo_text: str) -> tuple[bool, str]:
    """
    Uzaktan klavye tuşu veya tuş kombinasyonu basar.

    ⚠️ ANLAŞILMAYAN GİRDİ YAZILMAZ. Eski sürüm çözemediği cümleyi olduğu gibi
    `send_keys`e veriyordu; "klavye bozuldu" gibi bir mesaj aktif pencereye
    harfi harfine yazılıyordu. Artık kullanım rehberi dönülür, tuş basılmaz.

    Örnekler:
      - 'ctrl+enter'      → sadece Ctrl+Enter
      - 'enter bas'       → sadece Enter (ekrana 'enter bas' YAZMAZ)
      - '1234 enter'      → 1234 yazar, Enter basar
      - 'yaz: merhaba'    → metin yazar (özel karakterler kaçırılır)
      - 'kilit aç: 1234'  → kilit ekranını uyandırır, PIN girer
    """
    if sys.platform != 'win32':
        return False, "Klavye tuş emülasyonu sadece Windows sistemlerde desteklenmektedir."

    if not combo_text or not combo_text.strip():
        return False, "Görünür bir tuş veya kombinasyon belirtilmedi."

    active_title = foreground_window_title() or "Masaüstü/Aktif Pencere"
    raw_clean = combo_text.strip()

    # 1. Kilit açma — YALNIZCA açık niyette
    pin = _kilit_niyeti_coz(raw_clean)
    if pin is not None:
        return unlock_windows_screen(pin)

    # 2. Ön ek ayıklama ("tuş: ctrl+s")
    for prefix in ('tuş:', 'tus:', 'klavye:', 'press:', 'komut:'):
        if raw_clean.lower().startswith(prefix):
            raw_clean = raw_clean[len(prefix):].strip()
            break

    # 3. Türkçe dolgu eylemlerini temizle ('bas', 'yap', 'gönder', 'yolla', 'tıkla')
    raw_clean = re.sub(r'\s+(bas|bastır|bastir|yap|gönder|yolla|tıkla)$', '',
                       raw_clean, flags=re.IGNORECASE).strip()

    # 3.5 Doğal dil kısayolu mu? ("kopyala" → ctrl+c, "sekmeyi kapat" → ctrl+w)
    #     Metin yazma isteğinden ÖNCE bakılır ama 'yaz:' ön ekli cümleler
    #     zaten aşağıda ayrı ele alınıyor; burada onlara dokunulmaz.
    if not re.match(r'^(?:yaz|type)\s*:', raw_clean, re.IGNORECASE):
        dogal = dogal_kisayol_coz(raw_clean)
        if dogal:
            raw_clean = dogal
        else:
            # "ctrl c" → "ctrl+c" (artı işaretini yazmayan kullanıcı)
            raw_clean = _bosluklu_kombinasyon(raw_clean)

    # 4. Sonda enter var mı? ("1234 enter'a bas")
    press_enter_at_end = False
    enter_match = re.search(r"\s+(enter|enter'a|entera)$", raw_clean, re.IGNORECASE)
    if enter_match:
        press_enter_at_end = True
        raw_clean = raw_clean[:enter_match.start()].strip()

    text_clean = raw_clean.lower()

    # 5. Açık metin yazma isteği: 'yaz: X' veya 'X yaz'
    yazilacak = None
    m_yaz = re.match(r'^(?:yaz|type)\s*:\s*(.+)$', raw_clean, re.IGNORECASE)
    if m_yaz:
        yazilacak = m_yaz.group(1).strip()
    else:
        m_yaz2 = re.match(r'^(.*\S)\s+yaz$', raw_clean, re.IGNORECASE)
        if m_yaz2:
            yazilacak = m_yaz2.group(1).strip()

    if yazilacak:
        pattern = yaziyi_kacir(yazilacak) + ('{ENTER}' if press_enter_at_end else '')
        return _send_keys_gonder(pattern, combo_text, active_title, with_spaces=True)

    # 6. Tuş / kombinasyon eşleştirme
    parts = [p.strip() for p in text_clean.replace('-', '+').split('+') if p.strip()]
    found_mods, found_keys = [], []
    is_combo = bool(parts)

    for part in parts:
        if part in _MOD_MAP:
            found_mods.append(part)
        elif part in _KEY_MAP or \
                (part.startswith('f') and part[1:].isdigit() and 1 <= int(part[1:]) <= 12) or \
                (len(part) == 1 and part.isalnum()):
            found_keys.append(part)
        else:
            is_combo = False
            break

    if is_combo and (found_mods or found_keys):
        if press_enter_at_end and 'enter' not in found_keys:
            found_keys.append('enter')

        # Modifier kombinasyonlarında Win32 hardware keybd_event önceliklidir
        if found_mods and execute_native_hotkey(found_mods, found_keys):
            return True, (
                f"⌨️ **[KLAVYE İNPUTU GÖNDERİLDİ]**\n"
                f"• Girdi: `{combo_text}`\n"
                f"• Tuş Kombinasyonu: `{' + '.join(found_mods + found_keys).upper()}`\n"
                f"• Aktif Pencere: **{active_title}**"
            )

        if any(_MOD_MAP[m] is None for m in found_mods):
            # Win+X yalnızca native yoldan gider; oraya düştüysek gönderilememiştir.
            return False, (
                f"⌨️ **Tuş gönderilemedi.**\n• Girdi: `{combo_text}`\n"
                f"• Windows tuşu kombinasyonu bu ortamda emüle edilemiyor."
            )

        pattern = ''.join(_MOD_MAP[m] for m in found_mods) + ''.join(
            _KEY_MAP.get(k, '{' + k.upper() + '}' if k.startswith('f') and k[1:].isdigit()
                         else yaziyi_kacir(k))
            for k in found_keys
        )
        return _send_keys_gonder(pattern, combo_text, active_title)

    # 7. Rakam dizisi + Enter ("1234 enter") — belgelenmiş PIN/kod yazma biçimi.
    #    Yalnızca rakam olduğu için send_keys özel karakteri içeremez.
    if press_enter_at_end and re.fullmatch(r'[0-9\s]+', raw_clean or ''):
        pattern = re.sub(r'\s+', '', raw_clean) + '{ENTER}'
        return _send_keys_gonder(pattern, combo_text, active_title)

    # 8. Çözülemedi → HİÇBİR TUŞA BASMA
    return False, KULLANIM_REHBERI

