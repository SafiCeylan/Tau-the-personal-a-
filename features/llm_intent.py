# -*- coding: utf-8 -*-
"""
LLM Tabanlı Niyet Çözümleyici — regex'in kaçırdığı doğal dili yakalar.

Regex katmanı hızlı yoldur ("hava durumu", "sesi %30 yap" gibi net kalıplar);
eşleşmeyip GENERAL_CONVERSATION'a düşen mesajlar buraya gelir. Yerel LLM (Ollama)
mesajı bilinen niyetlerden birine sınıflandırır VE kanonik parametreyi çıkarır
(şarkı adı, arama sorgusu, uygulama adı). Böylece "bana motivasyon şarkısı koy"
gibi tetikleyici kelimesi olmayan komutlar da doğru yürütülür.

Güvenlik/dayanıklılık:
  • Ollama ulaşılamazsa None döner → çağıran regex sonucuyla devam eder (bozulmaz).
  • Model çöp üretirse JSON ayrıştırma toleranslıdır; geçersiz niyet reddedilir.
  • Kısa timeout — sohbet akışını kilitlemesin.
"""

import json
import re

# LLM'in dönebileceği GEÇERLİ niyetler (regex katmanıyla aynı etiketler)
GECERLI_NIYETLER = {
    "PLAY_MUSIC", "SYSTEM_CONTROL", "WEB_SEARCH", "CREATE_REMINDER",
    "WEATHER", "CURRENCY", "SCREENSHOT", "SCREEN_READ", "GENERAL_CONVERSATION",
    "MEDIA_CONTROL", "NOTE_TAKE", "TIMER", "CALCULATOR", "TIME_DATE",
}

# LLM'in dönebileceği geçerli medya aksiyonları
GECERLI_MEDYA = {"playpause", "pause", "play", "next", "prev", "stop"}

_PROMPT = """Sen bir niyet sınıflandırıcısın. Kullanıcının Türkçe mesajını AŞAĞIDAKİ \
niyetlerden BİRİNE ata ve gerekli parametreyi çıkar.

Niyetler:
- PLAY_MUSIC: müzik/şarkı çalma isteği. param: "sarki" = çalınacak şarkı/sanatçı adı.
- SYSTEM_CONTROL: uygulama açma/kapatma. param: "uygulama" = uygulama adı.
- WEB_SEARCH: internetten bilgi/araştırma isteği. param: "sorgu" = aranacak şey.
- CREATE_REMINDER: hatırlatma/alarm kurma. param yok.
- WEATHER: hava durumu sorusu. param yok.
- CURRENCY: döviz/dolar/euro kuru sorusu. param yok.
- SCREENSHOT: ekran görüntüsü alma (fotoğraf kaydetme). param yok.
- SCREEN_READ: ekranda YAZAN metni okuma/özetleme/açıklama ("ekranda ne yazıyor",
  "şu hatayı oku"). Fotoğraf değil, METİN istiyorsa buradadır. param yok.
- MEDIA_CONTROL: ÇALAN müziği kontrol. param: "aksiyon" = pause|play|next|prev|stop.
- NOTE_TAKE: not alma isteği. param: "not" = not içeriği.
- TIMER: sayaç/zamanlayıcı kurma. param: "dakika" = süre (sayı).
- CALCULATOR: matematik işlemi. param: "islem" = hesaplanacak ifade (örn "125*48").
- TIME_DATE: saat/tarih sorusu. param yok.
- GENERAL_CONVERSATION: sohbet, soru-cevap, yukarıdakilerin HİÇBİRİ değilse.

SADECE tek satır JSON döndür, açıklama yazma. Örnekler:
Mesaj: "bana biraz motivasyon şarkısı koy" -> {"intent":"PLAY_MUSIC","sarki":"motivasyon"}
Mesaj: "tarayıcıyı açar mısın" -> {"intent":"SYSTEM_CONTROL","uygulama":"chrome"}
Mesaj: "kuantum bilgisayar hakkında bilgi bul" -> {"intent":"WEB_SEARCH","sorgu":"kuantum bilgisayar"}
Mesaj: "bu şarkıyı sevmedim atla" -> {"intent":"MEDIA_CONTROL","aksiyon":"next"}
Mesaj: "biraz sessizlik olsun şunu dondur" -> {"intent":"MEDIA_CONTROL","aksiyon":"pause"}
Mesaj: "aklımda kalsın: yarın fatura ödemem lazım" -> {"intent":"NOTE_TAKE","not":"yarın fatura ödemem lazım"}
Mesaj: "on dakika sonra beni uyar" -> {"intent":"TIMER","dakika":10}
Mesaj: "yüz yirmi beş çarpı kırk sekiz kaç eder" -> {"intent":"CALCULATOR","islem":"125*48"}
Mesaj: "saat kaç oldu" -> {"intent":"TIME_DATE"}
Mesaj: "bugün kendimi yorgun hissediyorum" -> {"intent":"GENERAL_CONVERSATION"}

Mesaj: "%s" -> """


def _json_ayikla(metin: str):
    """Serbest metin içinden ilk {...} JSON bloğunu bulup ayrıştırır."""
    if not metin:
        return None
    m = re.search(r'\{.*?\}', metin, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def llm_intent_coz(mesaj: str, config: dict):
    """
    Mesajı LLM ile sınıflandırır → (intent, entities) veya None.
    entities: {"song_title": ...} / {"search_query": ...} / {"app_name": ...}
    None dönerse çağıran regex sonucunda kalmalıdır.
    """
    if not mesaj or not config:
        return None
    try:
        from features.ollama import ollama_generate
    except Exception:
        return None

    prompt = _PROMPT % mesaj.replace('"', "'")
    try:
        ans, _ctx = ollama_generate(
            prompt,
            ollama_url=config.get('ollama_url', 'http://127.0.0.1:11434'),
            model=config.get('ollama_model', 'gemma3:4b'),
        )
    except Exception as e:
        print(f"[LLM Intent] Ollama çağrısı başarısız: {e}")
        return None

    data = _json_ayikla(ans if isinstance(ans, str) else '')
    if not isinstance(data, dict):
        return None

    intent = str(data.get('intent', '')).strip().upper()
    if intent not in GECERLI_NIYETLER:
        return None

    entities = {}
    if intent == "PLAY_MUSIC" and data.get('sarki'):
        entities['song_title'] = str(data['sarki']).strip()
    elif intent == "WEB_SEARCH" and data.get('sorgu'):
        entities['search_query'] = str(data['sorgu']).strip()
    elif intent == "SYSTEM_CONTROL" and data.get('uygulama'):
        entities['app_name'] = str(data['uygulama']).strip()
    elif intent == "MEDIA_CONTROL":
        aksiyon = str(data.get('aksiyon', '')).strip().lower()
        # Geçersiz aksiyon gelirse niyeti düşür — yanlış tuş göndermektense
        # regex sonucunda kalmak daha güvenli.
        if aksiyon not in GECERLI_MEDYA:
            return None
        entities['media_action'] = aksiyon
    elif intent == "NOTE_TAKE":
        if not data.get('not'):
            return None
        entities['note_text'] = str(data['not']).strip()
    elif intent == "TIMER":
        try:
            dakika = float(data.get('dakika'))
        except (TypeError, ValueError):
            return None
        if dakika <= 0:
            return None
        entities['timer_minutes'] = dakika
    elif intent == "CALCULATOR":
        if not data.get('islem'):
            return None
        entities['expression'] = str(data['islem']).strip()

    return intent, entities
