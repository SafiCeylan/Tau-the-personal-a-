"""
Pano Sihirbazı — kopyaladığın her şeyi Ultron'dan geçir.

Komutlar:
  panoyu oku / panoda ne var        → içeriği göster
  panoyu özetle                     → LLM özetler
  panoyu çevir / ingilizceye çevir  → LLM çevirir (varsayılan İngilizce)
  panoya yaz: merhaba dünya         → panoya kopyalar
"""

import re

try:
    import pyperclip
except ImportError:
    pyperclip = None

_DILLER = {
    'ingilizce': 'İngilizce', 'türkçe': 'Türkçe', 'almanca': 'Almanca',
    'fransızca': 'Fransızca', 'ispanyolca': 'İspanyolca', 'arapça': 'Arapça',
    'rusça': 'Rusça', 'japonca': 'Japonca',
}


def pano_oku() -> str:
    if pyperclip is None:
        return ''
    try:
        return pyperclip.paste() or ''
    except Exception:
        return ''


def pano_yaz(metin: str) -> bool:
    if pyperclip is None:
        return False
    try:
        pyperclip.copy(metin)
        return True
    except Exception:
        return False


def pano_komutu(mesaj: str):
    """
    Pano komutunu çözer. Dönen değer:
      {'tip': 'direct', 'sonuc': str}                    → doğrudan cevap
      {'tip': 'ai', 'icerik': str, 'gorev': str}         → LLM'e akar
      None                                               → pano komutu değil
    """
    ml = mesaj.lower().strip()
    if not re.search(r'\bpano', ml):
        return None

    if pyperclip is None:
        return {'tip': 'direct',
                'sonuc': "⚠️ Pano erişimi için `pyperclip` gerekli: `pip install pyperclip`"}

    # Panoya yazma
    m = re.search(r'panoya\s+(?:yaz|kopyala)\s*:\s*(.+)$', mesaj, re.IGNORECASE | re.DOTALL)
    if m:
        if pano_yaz(m.group(1).strip()):
            return {'tip': 'direct', 'sonuc': "📋 Panoya kopyalandı."}
        return {'tip': 'direct', 'sonuc': "⚠️ Panoya yazılamadı."}

    icerik = pano_oku().strip()
    if not icerik:
        return {'tip': 'direct', 'sonuc': "📋 Pano boş veya metin içermiyor."}

    # LLM görevleri
    if any(k in ml for k in ['özetle', 'özet çıkar', 'özetini']):
        return {'tip': 'ai', 'icerik': icerik,
                'gorev': 'Bu metni Türkçe olarak madde madde, kısa ve net özetle.'}

    if 'çevir' in ml:
        hedef = 'İngilizce'
        for anahtar, ad in _DILLER.items():
            if anahtar in ml:
                hedef = ad
                break
        return {'tip': 'ai', 'icerik': icerik,
                'gorev': f'Bu metni {hedef} diline çevir. Sadece çeviriyi yaz.'}

    if any(k in ml for k in ['açıkla', 'ne demek', 'anlamı']):
        return {'tip': 'ai', 'icerik': icerik,
                'gorev': 'Bu metni basit Türkçeyle açıkla.'}

    # Varsayılan: oku/göster
    kesik = icerik[:1500]
    not_ = "\n\n*(ilk 1500 karakter gösterildi)*" if len(icerik) > 1500 else ""
    return {'tip': 'direct',
            'sonuc': f"📋 **PANO İÇERİĞİ:**\n```\n{kesik}\n```{not_}"}
