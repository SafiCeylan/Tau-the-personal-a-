import json
try:
    import requests
except ImportError:
    requests = None

def gemini_generate(prompt, api_key=None, model="gemini-1.5-flash", context=None):
    """
    Google Gemini REST API'sine doğrudan istek atar ve cevabı döner.
    API Anahtarı yoksa bilgilendirici hata mesajı verir.
    """
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        return "⚠️ Google Gemini API Anahtarı eksik! Ayarlar sayfasından API anahtarınızı girin.", context

    if requests is None:
        return "Hata: 'requests' kütüphanesi eksik.", context

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    contents = []
    if context and isinstance(context, list):
        contents.extend(context)
        
    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    ai_text = parts[0].get("text", "")
                    contents.append({
                        "role": "model",
                        "parts": [{"text": ai_text}]
                    })
                    return ai_text, contents
            return "Gemini yanıt vermedi veya boş veri döndü.", context
        else:
            return f"Google Gemini API Hatası ({response.status_code}): {response.text}", context
    except Exception as e:
        return f"Gemini Bağlantı Hatası: {str(e)}", context
