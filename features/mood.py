# -*- coding: utf-8 -*-
"""
Duygu / Ruh Hali Analizi.

Eski sürüm yalnızca ~25 sabit kelimeyi substring olarak arıyordu; Türkçe ekleri
("mutluyum", "üzülüyorum"), olumsuzlamayı ("mutlu değilim") ve emojileri kaçırdığı
için neredeyse her mesaj 'belirsiz' dönüyor ve hiç kaydedilmiyordu.

Yeni sürüm:
  • Ağırlıklı Türkçe duygu sözlüğü (kök eşleme → ekli hâlleri de yakalar)
  • Olumsuzlama tespiti: "iyi değilim", "hiç mutlu değil" → kutbu ters çevirir
  • Emoji duyarlılığı
  • Yoğunlaştırıcılar ("çok", "aşırı") skoru büyütür
  • İsteğe bağlı LLM doğrulaması (ruh_hali_analiz_llm) — çevrimdışı da çalışır
"""

import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Ağırlıklı duygu sözlüğü — anahtarlar KÖK'tür, ekli hâller de eşleşir
# ("mutlu" → "mutluyum", "mutluydum"; "üz" → "üzgün", "üzülüyorum", "üzüldüm")
# ---------------------------------------------------------------------------
POZITIF = {
    'mutlu': 2, 'mutluluk': 2, 'sevin': 2, 'harika': 2, 'muhteşem': 3, 'süper': 2,
    'güzel': 1, 'iyi': 1, 'keyif': 2, 'neşe': 2, 'enerjik': 2, 'huzur': 2,
    'heyecan': 2, 'gurur': 2, 'başar': 2, 'kazan': 1, 'sev': 1, 'teşekkür': 1,
    'sağol': 1, 'umut': 2, 'rahatla': 1, 'gül': 1, 'eğlen': 2, 'memnun': 2,
    'şükür': 2, 'harikulade': 3, 'muazzam': 3, 'mükemmel': 3, 'sevgi': 2,
    'coşku': 3, 'tatmin': 2, 'iyimser': 2, 'minnettar': 2, 'ferah': 1,
}
NEGATIF = {
    'üzgün': 2, 'üzül': 2, 'üzüntü': 2, 'kötü': 2, 'berbat': 3, 'yorgun': 1,
    'stres': 2, 'endişe': 2, 'kork': 2, 'kayg': 2, 'sıkıl': 1, 'bık': 2,
    'depres': 3, 'mutsuz': 3, 'ağla': 2, 'öfke': 2, 'kız': 1, 'sinir': 2,
    'nefret': 3, 'yalnız': 2, 'çaresiz': 3, 'umutsuz': 3, 'bunal': 2,
    'panik': 3, 'acı': 2, 'pişman': 2, 'hayal kırıklığı': 3, 'bezgin': 2,
    'tükenmiş': 2, 'gergin': 2, 'huzursuz': 2, 'perişan': 3, 'moral': 1,
    'ağır': 1, 'zor': 1, 'sorun': 1, 'dert': 2, 'keder': 3, 'hüzün': 2,
}
NOTR = {
    'normal': 1, 'sakin': 1, 'rahat': 1, 'durgun': 1, 'sessiz': 1,
    'idare': 1, 'fena değil': 1, 'ortalama': 1,
}

# Emoji kutupları
POZITIF_EMOJI = '😊😀😃😄😁🙂😍🥰😎🤗😌👍❤️💚💙😂🤣🥳✨🎉'
NEGATIF_EMOJI = '😢😭😔😞😟😠😡🤬😣😖😩😫😤💔😥😰😨😱🥺'

# Olumsuzlama işaretçileri — bir duygu kökünden hemen sonra/yakınında olursa kutup döner
OLUMSUZ = ('değil', 'yok', 'hiç', 'asla', 'ne yazık')

# Yoğunlaştırıcılar
YOGUN = ('çok', 'aşırı', 'son derece', 'baya', 'bayağı', 'inanılmaz', 'resmen', 'fena halde')


def _kok_gecti(kok: str, mesaj: str) -> bool:
    """Kök kelime mesajda geçiyor mu? Kelime başı sınırıyla ekli hâlleri de yakalar."""
    return re.search(r'\b' + re.escape(kok), mesaj) is not None


def _olumsuzlama_var(mesaj: str, kok: str) -> bool:
    """Duygu kökünün yakınında (±3 kelime) bir olumsuzlama işaretçisi var mı?"""
    kelimeler = mesaj.split()
    for i, kel in enumerate(kelimeler):
        if kok in kel:
            pencere = kelimeler[max(0, i - 2): i + 4]
            if any(neg in ' '.join(pencere) for neg in OLUMSUZ):
                return True
    return False


def ruh_hali_analiz(mesaj):
    """
    Mesajdan ruh hali analizi yapar → (ruh_hali, skor).
    ruh_hali: 'pozitif' | 'negatif' | 'nötr' | 'belirsiz'
    """
    if not mesaj:
        return 'belirsiz', 0
    m = mesaj.lower()

    yogunluk = 2 if any(y in m for y in YOGUN) else 1

    poz = neg = notr = 0

    for kok, agirlik in POZITIF.items():
        if _kok_gecti(kok, m):
            if _olumsuzlama_var(m, kok):
                neg += agirlik      # "mutlu değilim" → negatif
            else:
                poz += agirlik

    for kok, agirlik in NEGATIF.items():
        if _kok_gecti(kok, m):
            if _olumsuzlama_var(m, kok):
                poz += 1            # "kötü değil" → hafif pozitif
            else:
                neg += agirlik

    for kok, agirlik in NOTR.items():
        if _kok_gecti(kok, m):
            notr += agirlik

    # Emoji katkısı
    poz += sum(1 for ch in mesaj if ch in POZITIF_EMOJI)
    neg += sum(1 for ch in mesaj if ch in NEGATIF_EMOJI)

    poz *= yogunluk
    neg *= yogunluk

    if poz > neg and poz > notr:
        return 'pozitif', poz
    if neg > poz and neg > notr:
        return 'negatif', neg
    if notr > 0 and notr >= poz and notr >= neg:
        return 'nötr', notr
    return 'belirsiz', 0


def ruh_hali_analiz_llm(mesaj, config=None):
    """
    LLM ile daha isabetli duygu sınıflandırması. Ollama gerektirir; ulaşılamazsa
    otomatik olarak anahtar-kelime analizine (ruh_hali_analiz) düşer.
    Dönüş: (ruh_hali, skor). skor LLM yolunda güven göstergesidir (0-3).
    """
    config = config or {}
    try:
        from features.ollama import ollama_generate
    except Exception:
        return ruh_hali_analiz(mesaj)

    prompt = (
        "Aşağıdaki Türkçe mesajın duygusunu sınıflandır. "
        "SADECE tek kelime yanıtla: pozitif, negatif, nötr veya belirsiz.\n"
        f"Mesaj: \"{mesaj}\"\nCevap:"
    )
    try:
        ans, _ctx = ollama_generate(
            prompt,
            ollama_url=config.get('ollama_url', 'http://127.0.0.1:11434'),
            model=config.get('ollama_model', 'gemma3:4b'),
        )
        etiket = (ans or '').strip().lower()
        for gecerli in ('pozitif', 'negatif', 'nötr', 'notr', 'belirsiz'):
            if gecerli in etiket:
                return ('nötr' if gecerli == 'notr' else gecerli), 3
    except Exception as e:
        print(f"[Mood LLM] Sınıflandırma başarısız, kelime analizine düşülüyor: {e}")
    return ruh_hali_analiz(mesaj)


def ruh_hali_kaydet(cursor, conn, ruh_hali, mesaj):
    """Ruh hali verisini kaydeder."""
    try:
        cursor.execute("""
            INSERT INTO ruh_hali_gecmisi (ruh_hali, mesaj, tarih)
            VALUES (?, ?, ?)
        """, (ruh_hali, mesaj, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ruh hali kaydedilirken hata: {e}")
        return False
