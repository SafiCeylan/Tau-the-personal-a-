import json
try:
    import requests
except ImportError:
    requests = None

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
