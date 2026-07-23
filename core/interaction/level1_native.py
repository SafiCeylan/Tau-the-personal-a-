"""
AIP Level 1 — Native API katmanı.

Fare hareket etmez, buton aranmaz, OCR yoktur. İşletim sisteminin / uygulamanın
resmi arayüzleri kullanılır: URI şemaları (whatsapp:, spotify:), shell:AppsFolder,
os.startfile. Mevcut pycaw ses kontrolü ve uygulama başlatma kodları da kavramsal
olarak bu seviyeye aittir (features/actions/system_control.py içinde yaşarlar).
"""

import os
import subprocess
import sys


def open_uri(uri: str) -> bool:
    """URI şeması ile uygulamayı/derin bağlantıyı açar (whatsapp://send?... vb.)."""
    try:
        if sys.platform == 'win32':
            os.startfile(uri)
        else:
            subprocess.Popen(['xdg-open', uri])
        return True
    except Exception as e:
        print(f"[AIP L1] URI açılamadı ({uri[:40]}...): {e}")
        return False


def launch_appid(app_id: str) -> bool:
    """Get-StartApps AppID'si ile başlatır (UWP/Store dahil)."""
    try:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return True
    except Exception as e:
        print(f"[AIP L1] AppID başlatılamadı: {e}")
        return False
