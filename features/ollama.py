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

def ollama_generate(prompt, ollama_url='http://127.0.0.1:11434', model='gemma3:4b', context=None):
    """
    Ollama API'sine istek gönderir ve cevabı döner.
    
    Args:
        prompt (str): Kullanıcı girdisi
        ollama_url (str): Ollama sunucu adresi
        model (str): Kullanılacak model adı (örn: llama3, mistral)
        context (list): Konuşma bağlamı (hafıza için)
        
    Returns:
        str: Modelin cevabı
    """
    if requests is None:
        return "Hata: 'requests' kütüphanesi eksik. Lütfen `pip install requests` komutunu çalıştırın."
        
    url = f"{ollama_url.rstrip('/')}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
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
