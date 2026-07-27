"""
AIP Level 4 — Klavye/Fare Emülasyonu (SON ÇARE).

En kırılgan katman: koordinata/odağa bağımlıdır. Bu yüzden buradaki her tuş
gönderimi ODAK KORUMALIDIR — hedef pencere önde değilse tuş GÖNDERİLMEZ.
(Yanlış pencereye Enter basmak = felaket senaryosu.)
"""

import ctypes
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
