"""
AIP Level 2 — UI Automation katmanı (pywinauto, backend="uia").

Windows'un erişilebilirlik ağacı üzerinden elementleri bulur ve fare olmadan
Invoke/SetText yapar. Çözünürlük, tema, DPI, pencere konumu değişse de çalışır.

Not: pywinauto import'u yavaştır (~1-2 sn) — bu yüzden lazy import edilir ve
tüm çağrılar worker thread'den yapılmalıdır (UI thread'ini bloklarlar).
"""

import time

_pywinauto = None
_import_failed = False


def _pwa():
    """pywinauto'yu lazy yükler; yoksa None döner."""
    global _pywinauto, _import_failed
    if _pywinauto is None and not _import_failed:
        try:
            import pywinauto  # noqa
            _pywinauto = pywinauto
        except Exception as e:
            print(f"[AIP L2] pywinauto yüklenemedi: {e}")
            _import_failed = True
    return _pywinauto


def uia_available() -> bool:
    return _pwa() is not None


def find_window(title_re: str, timeout: float = 10.0):
    """
    Başlığı regex ile eşleşen üst seviye pencereyi bekleyerek bulur.
    Dönen değer: WindowSpecification wrapper'ı veya None.
    """
    pwa = _pwa()
    if not pwa:
        return None
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            desktop = pwa.Desktop(backend="uia")
            win = desktop.window(title_re=title_re)
            if win.exists(timeout=1):
                return win
        except Exception:
            pass
        time.sleep(0.5)
    return None


def find_button(window, name_options, timeout: float = 8.0):
    """
    Pencere içinde adı verilen seçeneklerden biriyle eşleşen Button elementini bulur.
    name_options: ["Gönder", "Send"] gibi yerelleştirme alternatifleri.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for name in name_options:
            try:
                btn = window.child_window(title=name, control_type="Button")
                if btn.exists(timeout=1):
                    return btn
            except Exception:
                pass
        time.sleep(0.5)
    return None


def find_edit(window, timeout: float = 8.0):
    """Penceredeki ilk Edit (metin girişi) elementini bulur."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            edit = window.child_window(control_type="Edit", found_index=0)
            if edit.exists(timeout=1):
                return edit
        except Exception:
            pass
        time.sleep(0.5)
    return None


def invoke(element) -> bool:
    """Elementi fare olmadan tetikler (InvokePattern; olmazsa click_input'a düşmez!)."""
    try:
        element.invoke()
        return True
    except Exception:
        try:
            # Bazı elementlerde invoke yoktur; UIA 'select' veya legacy default action dene
            element.click()  # pywinauto uia click() = programatik, fare taşımaz
            return True
        except Exception as e:
            print(f"[AIP L2] Invoke başarısız: {e}")
            return False


def get_edit_text(edit) -> str:
    """Edit elementinin mevcut metnini okur."""
    try:
        return edit.get_value()
    except Exception:
        try:
            return edit.window_text()
        except Exception:
            return ""
