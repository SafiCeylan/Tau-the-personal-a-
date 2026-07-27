import json
try:
    import requests
except ImportError:
    requests = None


def ollama_chat_stream(prompt, ollama_url='http://127.0.0.1:11434',
                       model='gemma3:4b', on_token=None):
    """
    Modern /api/chat endpoint'i ile STREAMING üretim.
    Her gelen parça için on_token(delta) çağrılır; tam metin döner.

    Not: Çok turlu bağlam enriched_prompt içinde taşınır (PromptGenerator'ın
    [GEÇMİŞ SOHBET BAĞLAMI] bloğu) — burada ayrıca messages geçmişi tutulmaz,
    böylece aynı geçmişin iki kanaldan gitmesi (token israfı) önlenir.
    """
    if requests is None:
        raise RuntimeError("'requests' kütüphanesi eksik.")

    url = f"{ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        # Düşük sıcaklık: küçük modellerde (3B-4B) Türkçe tutarlılığı artırır
        "options": {"temperature": 0.5, "top_p": 0.9},
    }

    parcalar = []
    with requests.post(url, json=payload, stream=True, timeout=(10, 300)) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            delta = (data.get('message') or {}).get('content', '')
            if delta:
                parcalar.append(delta)
                if on_token:
                    on_token(delta)
            if data.get('done'):
                break
    return ''.join(parcalar)

def ollama_json(prompt, sema, ollama_url='http://127.0.0.1:11434',
                model='qwen2.5:7b', timeout=180):
    """
    ŞEMAYA ZORLANMIŞ JSON üretimi (planner'ın omurgası).

    Ollama'nın `format` alanına bir JSON şeması verilirse model çıktıyı o şemaya
    UYMAYA ZORLANIR (grammar-constrained decoding). Serbest metin isteyip sonra
    JSON ayıklamaya çalışmaktan çok daha güvenilirdir: "plan üretti ama JSON
    bozuk" hata sınıfının tamamı ortadan kalkar.

    Sıcaklık 0: plan üretimi yaratıcılık değil, ayrıştırma işidir.

    Zaman aşımı sohbetten UZUN tutulur — 7B model soğuk başlangıçta uzun bir
    planı 60 saniyede yetiştiremeyebilir.

    Dönüş: (sozluk, hata_mesaji). Başarıda hata None'dır.
    """
    if requests is None:
        return None, "'requests' kütüphanesi eksik."

    url = f"{ollama_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": sema,
        "options": {"temperature": 0},
    }

    try:
        cevap = requests.post(url, json=payload, timeout=timeout)
        cevap.raise_for_status()
        ham = cevap.json().get('response', '')
    except requests.exceptions.ConnectionError:
        return None, "Ollama'ya bağlanılamadı (çalışıyor mu?)."
    except requests.exceptions.Timeout:
        return None, f"Ollama {timeout} saniyede cevap vermedi."
    except Exception as e:
        return None, f"Ollama hatası: {e}"

    try:
        return json.loads(ham), None
    except Exception as e:
        # Şema zorlamasına rağmen bozuk çıktı — model şemayı desteklemiyor olabilir
        return None, f"JSON ayrıştırılamadı: {e} — ham çıktı: {ham[:200]}"


def ollama_generate(prompt, ollama_url='http://127.0.0.1:11434', model='gemma3:4b',
                    context=None, temperature=0.5):
    """
    Ollama API'sine istek gönderir ve cevabı döner.

    Args:
        prompt (str): Kullanıcı girdisi
        ollama_url (str): Ollama sunucu adresi
        model (str): Kullanılacak model adı (örn: llama3, mistral)
        context (list): Konuşma bağlamı (hafıza için)
        temperature (float): Düşük değer (0.3-0.6) küçük modellerde tutarlılığı
            artırır, saçmalama/şahıs karışıklığını azaltır.

    Returns:
        str: Modelin cevabı
    """
    if requests is None:
        return "Hata: 'requests' kütüphanesi eksik. Lütfen `pip install requests` komutunu çalıştırın."

    url = f"{ollama_url.rstrip('/')}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "top_p": 0.9},
    }

    if context:
        payload["context"] = context
        
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # Ollama /api/generate endpoint'i 'response' anahtarı döner
        if 'response' in data:
            return data['response'], data.get('context', [])
        else:
            return f"Ollama beklenmeyen format döndü: {list(data.keys())}", None
            
    except requests.exceptions.ConnectionError:
        return "Bağlantı Hatası: Ollama uygulaması çalışıyor mu? (http://127.0.0.1:11434)", None
    except Exception as e:
        return f"Ollama hatası: {str(e)}", None
