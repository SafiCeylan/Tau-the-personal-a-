"""
AIP — Verification Engine.

"İşlem yapıldı" demek yetmez; gerçekten yapıldı mı kontrol edilir.
Doğrulayıcılar Optional[bool] döner:
    True  → doğrulandı
    False → doğrulanamadı (Decision Engine bir alt seviyeye geçer)
    None  → doğrulama bu ortamda mümkün değil (sonuç yine kabul edilir)
"""

import time
from typing import Optional

from core.interaction import level2_uia


def verify_edit_cleared(title_re: str, timeout: float = 6.0) -> Optional[bool]:
    """
    Mesaj gönderimi doğrulaması: gönderim başarılıysa pencerede metin kutusu
    boşalmış olmalıdır (WhatsApp, Discord vb. gönderince kutuyu temizler).
    """
    if not level2_uia.uia_available():
        return None
    win = level2_uia.find_window(title_re, timeout=3)
    if win is None:
        return None
    deadline = time.time() + timeout
    while time.time() < deadline:
        edit = level2_uia.find_edit(win, timeout=2)
        if edit is None:
            return None
        text = (level2_uia.get_edit_text(edit) or "").strip()
        if text == "":
            return True
        time.sleep(0.7)
    return False
