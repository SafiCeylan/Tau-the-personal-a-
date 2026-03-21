import json
try:
    import requests
except ImportError:
    requests = None

def kobold_generate(prompt, kobold_url='http://localhost:5001', model=None, context=None):
    """
    KoboldCPP API'sine (OpenAI uyumlu) istek gönderir ve cevabı döner.
    
    Args:
        prompt (str): Kullanıcı girdisi
        kobold_url (str): KoboldCPP sunucu adresi (varsayılan: http://localhost:5001)
        model (str): Kullanılacak model adı (KoboldCPP'de genellikle yok sayılır ama uyumluluk için tutuyoruz)
        context (list): Konuşma geçmişi (list of dicts). 
                        Eğer Ollama'dan gelen int listesi ise sıfırlanır.
        
    Returns:
        str: Modelin cevabı
        list: Güncellenmiş konuşma geçmişi (context)
    """
    if requests is None:
        return "Hata: 'requests' kütüphanesi eksik.", None
        
    # URL'i düzelt
    url = f"{kobold_url.rstrip('/')}/v1/chat/completions"
    
    # Context yönetimi
    messages = []
    
    # Eğer context geçerli bir liste ise ve içinde dict varsa (OpenAI formatı)
    if context and isinstance(context, list) and len(context) > 0:
        if isinstance(context[0], dict) and 'role' in context[0]:
            messages = context
        else:
            # Ollama formatı (int listesi) veya geçersiz format
            # Geçmişi sıfırla ama sistem mesajı ekle (isteğe bağlı)
            pass
            
    # Eğer geçmiş boşsa sistem mesajı ekleyelim (opsiyonel, modele göre değişir)
    if not messages:
        messages.append({"role": "system", "content": "Sen yardımsever ve zeki bir asistansın. Türkçe konuşuyorsun."})
    
    # Yeni mesajı ekle
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "koboldcpp", # Genellikle önemsizdir ama gerekli olabilir
        "messages": messages,
        "max_tokens": 512, # Cevap uzunluğu limiti
        "stream": False,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120) # Kobold bazen yavaş olabilir
        
        if response.status_code == 200:
            data = response.json()
            
            # OpenAI formatında cevap: choices[0].message.content
            if 'choices' in data and len(data['choices']) > 0:
                ai_message = data['choices'][0]['message']['content']
                
                # Cevabı geçmişe ekle
                messages.append({"role": "assistant", "content": ai_message})
                
                return ai_message, messages
            else:
                return f"KoboldCPP beklenmeyen format döndü: {json.dumps(data)}", context
        else:
            return f"KoboldCPP Hatası: {response.status_code} - {response.text}", context
            
    except requests.exceptions.ConnectionError:
        return "Bağlantı Hatası: KoboldCPP çalışıyor mu? (http://localhost:5001)", context
    except Exception as e:
        return f"KoboldCPP isteği sırasında hata: {str(e)}", context
