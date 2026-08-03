"""
Ekran Görüntüsü — "ekran görüntüsü al" komutu.

mss ile tüm ekran(lar) yakalanır, Masaüstüne zaman damgalı PNG kaydedilir.
Thread-safe: Telegram worker'ından da güvenle çağrılabilir (Qt gerektirmez).
"""

import os
from datetime import datetime

from features.file_finder import _gercek_yol


def ekran_goruntusu_al():
    """Ekranı yakalar. Dönen değer: (dosya_yolu | None, mesaj)."""
    try:
        import mss
        import mss.tools
    except ImportError:
        return None, "⚠️ Ekran görüntüsü için `mss` gerekli: `pip install mss`"

    masaustu = _gercek_yol('Desktop') or os.path.expanduser('~')
    hedef_klasor = os.path.join(masaustu, "ultron fotoğraflar")
    os.makedirs(hedef_klasor, exist_ok=True)

    dosya = f"ultron_ekran_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    yol = os.path.join(hedef_klasor, dosya)

    try:
        with mss.mss() as sct:
            # monitors[0] = tüm monitörlerin birleşimi
            ekran = sct.grab(sct.monitors[0])
            mss.tools.to_png(ekran.rgb, ekran.size, output=yol)
        boyut_mb = os.path.getsize(yol) / (1024 * 1024)
        return yol, (f"📸 **Ekran görüntüsü alındı:** `{dosya}` ({boyut_mb:.1f} MB)\n"
                     f"Masaüstü → `ultron fotoğraflar` klasörüne kaydedildi.")
    except Exception as e:
        return None, f"⚠️ Ekran görüntüsü alınamadı: {e}"
