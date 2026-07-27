# -*- coding: utf-8 -*-
"""
Hafıza Erişimi (RAG) — mesaja EN ALAKALI hafızaları yüzeye çıkarır.

Önceki davranış: kullanıcının kaydettiği hafızalardan yalnızca "en son 10"u
(alakadan bağımsız) prompt'a dökülüyordu. 50 kayıt varsa çoğu ilgisiz olduğundan
LLM'in doğru bilgiyi görme şansı düşüktü.

Bu modül mesaja göre alaka puanı hesaplar ve en iyi K kaydı döner:
  • Çevrimdışı skorlayıcı (varsayılan): Türkçe-duyarlı kelime örtüşmesi + kök eşleme.
    Yeni model/bağımlılık GEREKTİRMEZ, herkeste çalışır.
  • Opsiyonel embedding yolu: config'te 'embed_model' tanımlıysa Ollama embeddings
    ile anlamsal benzerlik (vektörler süreç içi cache'lenir). Ulaşılamazsa otomatik
    olarak çevrimdışı skorlayıcıya düşer.
"""

import re
import math

# Skorlamada gürültü yaratan çok sık Türkçe kelimeler (elenir)
_STOPWORDS = {
    've', 'ile', 'bir', 'bu', 'şu', 'o', 'da', 'de', 'ki', 'mi', 'mı', 'mu', 'mü',
    'için', 'gibi', 'ama', 'çok', 'ne', 'nasıl', 'neden', 'kim', 'nedir', 'kaç',
    'ben', 'sen', 'biz', 'siz', 'onlar', 'benim', 'senin', 'var', 'yok', 'the', 'a',
}

# Süreç içi embedding cache: {metin: vektör}
_EMBED_CACHE = {}


def _tokenlar(metin: str):
    """Metni küçük harfli, stopword'süz kelimelere böler."""
    kelimeler = re.findall(r'\w+', (metin or '').lower())
    return [k for k in kelimeler if k not in _STOPWORDS and len(k) >= 2]


def _eslesir(a: str, b: str) -> bool:
    """İki kelime aynı kökten mi? Türkçe çekimi yakalamak için ön-ek eşleşmesi:
    biri diğerinin başlangıcıysa eşleşir ("kedi"~"kedimin", "araba"~"arabam")."""
    if a == b:
        return True
    kisa, uzun = (a, b) if len(a) <= len(b) else (b, a)
    return len(kisa) >= 3 and uzun.startswith(kisa)


def _kelime_skoru(mesaj: str, hafiza: str) -> float:
    """Mesaj ile hafıza arasındaki kelime örtüşme puanı (0+). Yüksek = daha alakalı."""
    m_tok = _tokenlar(mesaj)
    h_tok = _tokenlar(hafiza)
    if not m_tok or not h_tok:
        return 0.0
    eslesme = sum(1 for mt in m_tok if any(_eslesir(mt, ht) for ht in h_tok))
    if not eslesme:
        return 0.0
    return eslesme / math.sqrt(len(m_tok) * len(h_tok))


# ---------------------------------------------------------------------------
# Opsiyonel embedding yolu (Ollama)
# ---------------------------------------------------------------------------
def _embed(metin: str, config: dict):
    """Metni vektöre çevirir (cache'li). Başarısızsa None."""
    if metin in _EMBED_CACHE:
        return _EMBED_CACHE[metin]
    try:
        import requests
    except Exception:
        return None
    try:
        url = config.get('ollama_url', 'http://127.0.0.1:11434').rstrip('/') + '/api/embeddings'
        r = requests.post(url, json={
            'model': config.get('embed_model'),
            'prompt': metin,
        }, timeout=15)
        r.raise_for_status()
        vec = r.json().get('embedding')
        if vec:
            _EMBED_CACHE[metin] = vec
            return vec
    except Exception as e:
        print(f"[Memory RAG] Embedding alınamadı, kelime skoruna düşülüyor: {e}")
    return None


def _kosinus(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    nokta = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return nokta / (na * nb) if na and nb else 0.0


def alakali_hafizalar(mesaj: str, hafizalar, config: dict = None, k: int = 6):
    """
    hafizalar: [(key, value, category), ...] veya ["key: value", ...]
    Dönüş: en alakalı k hafıza → ["key: value", ...] (skor > 0 olanlar).
    Hiç alakalı yoksa en yeni k kayda düşer (boş prompt'tan iyidir).
    """
    config = config or {}
    if not hafizalar:
        return []

    # Girişi "key: value" düz metne normalize et
    duz = []
    for h in hafizalar:
        if isinstance(h, (tuple, list)):
            key, value = h[0], h[1]
            duz.append(f"{key}: {value}")
        else:
            duz.append(str(h))

    # Embedding yolu (opsiyonel)
    if config.get('embed_model'):
        mvec = _embed(mesaj, config)
        if mvec:
            puanli = []
            for metin in duz:
                hvec = _embed(metin, config)
                puanli.append((_kosinus(mvec, hvec) if hvec else 0.0, metin))
            puanli.sort(key=lambda x: x[0], reverse=True)
            secilen = [m for s, m in puanli if s > 0.3][:k]
            return secilen or duz[:k]

    # Çevrimdışı kelime skorlayıcı (varsayılan)
    puanli = [(_kelime_skoru(mesaj, metin), metin) for metin in duz]
    puanli.sort(key=lambda x: x[0], reverse=True)
    alakali = [m for s, m in puanli if s > 0][:k]
    return alakali or duz[:k]
