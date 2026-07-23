"""
TAU Backend API bağlantısı için fonksiyonlar
"""

import requests
import json
import os
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

def get_tau_config():
    """TAU backend config bilgilerini al"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        backend_url = config.get('tau_backend_url')
        api_key = config.get('tau_api_key')
        timeout = config.get('tau_timeout', 30)
        endpoint = config.get('tau_endpoint', '/chat')
        
        if not backend_url:
            raise ValueError('TAU backend URL config.json dosyasında bulunamadı.')
        return backend_url, api_key, timeout, endpoint
    except Exception as e:
        raise RuntimeError(f"config.json okunamadı veya eksik: {e}")

def tau_backend_soru_sor(soru, ek_bilgiler=None, user_id=None,
                         backend_url=None, api_key=None, timeout=30, endpoint='/chat'):
    """
    TAU Backend API'ye soru sorar ve cevabı döner.
    :param soru: Kullanıcıdan gelen soru (string)
    :param ek_bilgiler: (isteğe bağlı) Ek bilgi/metin (string veya None)
    :param user_id: (isteğe bağlı) Kullanıcı ID (string veya None)
    :param backend_url/api_key/timeout/endpoint: (isteğe bağlı) Doğrudan bağlantı
        bilgileri; verilmezse config.json'dan okunur.
    :return: API'den dönen cevap (string) veya hata mesajı
    """
    if not backend_url:
        try:
            backend_url, api_key, timeout, endpoint = get_tau_config()
        except Exception as e:
            return f"TAU Backend yapılandırma hatası: {e}"

    if backend_url == "https://your-tau-backend-url.com/api":
        return "⚠️ TAU Backend URL henüz yapılandırılmamış. Ayarlar sayfasından gerçek adresi girin."
    
    # Backend URL'in sonunda / varsa kaldır
    backend_url = backend_url.rstrip('/')
    # Endpoint'in başında / yoksa ekle
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    
    full_url = backend_url + endpoint
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # API key varsa header'a ekle (Bearer token veya X-API-Key formatında)
    if api_key and api_key != "YOUR_TAU_API_KEY_HERE":
        # Önce Bearer token olarak dene, yoksa X-API-Key olarak
        if api_key.startswith('Bearer '):
            headers["Authorization"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
            # Alternatif: headers["X-API-Key"] = api_key
    
    # Request body oluştur
    data = {
        "question": soru,
        "message": soru,  # Bazı API'ler "message" kullanır
        "timestamp": datetime.now().isoformat()
    }
    
    if ek_bilgiler:
        data["context"] = ek_bilgiler
        data["additional_info"] = ek_bilgiler
    
    if user_id:
        data["user_id"] = user_id
    
    try:
        # POST request gönder
        response = requests.post(
            full_url,
            headers=headers,
            json=data,
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        
        # Backend'in response formatına göre cevabı çıkar
        # Farklı formatları destekle
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            if "answer" in result:
                return result["answer"]
            elif "response" in result:
                return result["response"]
            elif "message" in result:
                return result["message"]
            elif "text" in result:
                return result["text"]
            elif "content" in result:
                return result["content"]
            elif "data" in result and isinstance(result["data"], dict):
                # İç içe data yapısı
                data_obj = result["data"]
                if "answer" in data_obj:
                    return data_obj["answer"]
                elif "response" in data_obj:
                    return data_obj["response"]
            else:
                # Tüm string değerleri birleştir
                return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return str(result)
            
    except requests.exceptions.Timeout:
        return "⏱️ TAU Backend'e bağlanırken zaman aşımı oluştu. Lütfen tekrar deneyin."
    except requests.exceptions.ConnectionError:
        return "🔌 TAU Backend'e bağlanılamadı. Lütfen internet bağlantınızı ve backend URL'ini kontrol edin."
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else "Unknown"
        try:
            error_detail = e.response.json() if e.response else {}
            error_msg = error_detail.get("error", error_detail.get("message", str(e)))
        except:
            error_msg = str(e)
        return f"❌ TAU Backend HTTP hatası ({status_code}): {error_msg}"
    except json.JSONDecodeError:
        return f"⚠️ TAU Backend'den geçersiz yanıt alındı. Response: {response.text[:200]}"
    except Exception as e:
        return f"❌ TAU Backend hatası: {str(e)}"

def tau_backend_test_connection():
    """TAU Backend bağlantısını test et"""
    try:
        backend_url, api_key, timeout, endpoint = get_tau_config()
        if backend_url == "https://your-tau-backend-url.com/api":
            return False, "Backend URL henüz yapılandırılmamış. config.json dosyasını düzenleyin."
        
        # Basit bir test mesajı gönder
        test_response = tau_backend_soru_sor("test", user_id="test_user")
        if "hatası" in test_response.lower() or "error" in test_response.lower():
            return False, test_response
        return True, "Bağlantı başarılı!"
    except Exception as e:
        return False, f"Bağlantı testi başarısız: {e}"

