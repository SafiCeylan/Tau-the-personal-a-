"""
ULTRON — Özel Kullanıcı Kısayolları Yöneticisi.

Kullanıcının Telegram veya Masaüstü arayüzünden dinamik olarak ekleyip
çıkarabileceği özel tuş kombinasyonlarını ve komutlarını saklar ve yönetir.
Veriler %APPDATA%\\ULTRON\\custom_shortcuts.json altında tutulur.
"""

import json
import os
import re
from core.paths import veri_dizini

_DOSYA_ADI = "custom_shortcuts.json"


def _dosya_yolu() -> str:
    return os.path.join(veri_dizini(), _DOSYA_ADI)


def _sadelestir(ad: str) -> str:
    """
    Buton metni ile kayıtlı adı karşılaştırılabilir yapar: baştaki emoji/simge
    süsü ve büyük/küçük harf farkı atılır. ("⭐ Photoshop" ↔ "photoshop")
    """
    t = (ad or "").strip().lower()
    return re.sub(r'^[^\w]+', '', t, flags=re.UNICODE).strip()


def yukle() -> dict:
    """Tüm özel kısayolları sözlük olarak döndürür {ad: komut}."""
    yol = _dosya_yolu()
    if not os.path.exists(yol):
        # Varsayılan başlangıç özel kısayolları
        varsayilan = {
            "⚡ VS Code Aç": "code",
            "🔍 Görev Yöneticisi": "ctrl+shift+esc",
            "🖥️ Ekran Alıntısı": "win+shift+s",
            "📋 Pano Geçmişi": "win+v"
        }
        kaydet(varsayilan)
        return varsayilan

    try:
        with open(yol, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"[Özel Kısayollar] Okuma hatası: {e}")

    return {}


def kaydet(shortcuts: dict) -> bool:
    """Özel kısayolları JSON dosyasına kaydeder."""
    yol = _dosya_yolu()
    try:
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(shortcuts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Özel Kısayollar] Kaydetme hatası: {e}")
        return False


def ekle(ad: str, komut: str) -> tuple[bool, str]:
    """
    Yeni bir özel kısayol ekler veya günceller.
    Örnek: ekle("Photoshop Aç", "ctrl+alt+shift+p")
    """
    ad = (ad or "").strip()
    komut = (komut or "").strip()

    if not ad:
        return False, "Kısayol ismi boş olamaz."
    if not komut:
        return False, "Kısayol komutu veya tuşu boş olamaz."

    shortcuts = yukle()
    shortcuts[ad] = komut
    if kaydet(shortcuts):
        return True, f"✅ **'{ad}'** kısayolu başarıyla eklendi! (`{komut}`)"
    return False, "Kısayol dosyaya kaydedilemedi."


def sil(ad: str) -> tuple[bool, str]:
    """
    Var olan bir özel kısayolu siler.

    ⚠️ TAM eşleşme. Eski sürüm alt dizi ile eşliyordu ("a" → içinde 'a' geçen
    ilk kısayolu silerdi) — yanlış kısayolu sessizce silmek, kullanıcının
    kaybettiğini fark etmediği bir hatadır.
    """
    ad = (ad or "").strip()
    hedef = _sadelestir(ad)
    shortcuts = yukle()

    hedef_key = None
    for k in shortcuts:
        if _sadelestir(k) == hedef:
            hedef_key = k
            break

    if not hedef_key:
        return False, f"❌ **'{ad}'** adında bir özel kısayol bulunamadı."

    del shortcuts[hedef_key]
    if kaydet(shortcuts):
        return True, f"🗑️ **'{hedef_key}'** kısayolu silindi."
    return False, "Kısayol silinirken hata oluştu."


def komut_bul(metin: str) -> str | None:
    """
    Gelen Telegram/Masaüstü metnini özel kısayollarla eşleştirir.

    ⚠️ TAM eşleşme (emoji süsü ve harf büyüklüğü yok sayılır). Eski sürüm
    `metin in ad` diyordu: "aç" mesajı "⚡ VS Code Aç" kısayolunu, tek harflik
    bir mesaj bile rastgele bir kısayolu tetikliyordu. Bu fonksiyon her serbest
    metinde çağrıldığı için sohbet cümleleri komuta dönüşüyordu.
    """
    hedef = _sadelestir(metin)
    if not hedef:
        return None
    for ad, komut in yukle().items():
        if _sadelestir(ad) == hedef:
            return komut
    return None
