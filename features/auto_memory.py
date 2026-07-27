"""
Otomatik Hafıza Öğrenme — kullanıcı kendinden bahsedince ULTRON kendiliğinden not alır.

Yakalanan kalıplar:
  "benim adım Mehmet"            → adım = Mehmet
  "en sevdiğim dizi Dark"        → en sevdiğim dizi = Dark
  "25 yaşındayım"                → yaşım = 25
  "mesleğim yazılımcı"           → mesleğim = yazılımcı
  "ankara'da yaşıyorum"          → şehrim = ankara  (+ hava durumu şehri güncellenir!)
  "hatırla: anahtar = değer"     → açık kayıt

Kayıtlar memory tablosuna 'Otomatik' kategorisiyle yazılır; MemoryContextLayer
bunları her LLM çağrısında bağlama koyar — yani Ultron gerçekten "öğrenir".
"""

import json
import os
import re

from core.paths import veri_yolu

USER_DATA_PATH = veri_yolu('user_data.json')

# (regex, anahtar_şablonu) — şablonda {1} = grup 1
_KALIPLAR = [
    (r"\bbenim adım\s+([\wçğıöşü]+)", "adım", 1),
    (r"\bben\s+([\wçğıöşü]+)\s*[,.]?\s*(?:yım|yim|im|ım)\b", None, None),  # belirsiz — atla
    (r"\ben sevdiğim\s+([\wçğıöşü]+)\s+(.+?)[.!]?$", "en sevdiğim {1}", 2),
    (r"\b(\d{1,2})\s+yaşındayım", "yaşım", 1),
    (r"\bmesleğim\s+(.+?)[.!]?$", "mesleğim", 1),
    (r"\b([\wçğıöşü]+)\s+olarak çalışıyorum", "mesleğim", 1),
    (r"\b([\wçğıöşü]+)['’]?[dt][ea]\s+yaşıyorum", "şehrim", 1),
    (r"\bşehrim\s+([\wçğıöşü]+)", "şehrim", 1),
]


def _sehir_kaydet(sehir: str):
    """Öğrenilen şehri hava durumu servisine de köprüle (user_data.json 'sehir')."""
    try:
        data = {}
        if os.path.exists(USER_DATA_PATH):
            with open(USER_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data['sehir'] = sehir
        with open(USER_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AutoMemory] Şehir kaydedilemedi: {e}")


def _hafizaya_yaz(cursor, conn, key: str, value: str):
    cursor.execute("""
        INSERT INTO memory (key, value, category)
        VALUES (?, ?, 'Otomatik')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value,
            category = excluded.category, created_at = CURRENT_TIMESTAMP
    """, (key, value))
    conn.commit()


def hafiza_ogren(mesaj: str, cursor, conn):
    """
    Mesajda öğrenilecek kişisel bilgi arar; bulursa kaydeder.
    Dönen değer: onay metni veya None (bir şey öğrenilmediyse).
    """
    if cursor is None or conn is None:
        return None
    ml = mesaj.lower().strip()

    # Açık komut: "hatırla: anahtar = değer" (en yüksek öncelik)
    m = re.search(r'hatırla\s*:\s*(.+?)\s*=\s*(.+)$', mesaj, re.IGNORECASE)
    if m:
        key, value = m.group(1).strip().lower(), m.group(2).strip()
        _hafizaya_yaz(cursor, conn, key, value)
        return f"🧠 **Hafızama kaydettim:** {key} = {value}"

    for kalip, key_sablon, deger_grubu in _KALIPLAR:
        if key_sablon is None:
            continue
        # Orijinal metinde IGNORECASE ara — değerin yazımı korunur ("Dark" → "Dark")
        m = re.search(kalip, mesaj, re.IGNORECASE)
        if not m:
            continue
        key = (key_sablon.replace('{1}', m.group(1).lower())
               if '{1}' in key_sablon else key_sablon)
        value = m.group(deger_grubu).strip().strip('.!?')
        if not value or len(value) > 120:
            continue
        _hafizaya_yaz(cursor, conn, key, value)
        if key == 'şehrim':
            _sehir_kaydet(value)
            return (f"🧠 **Hafızama kaydettim:** şehrim = {value.title()}\n"
                    f"🌤️ Hava durumu artık {value.title()} için gösterilecek.")
        return f"🧠 **Hafızama kaydettim:** {key} = {value}"

    return None
