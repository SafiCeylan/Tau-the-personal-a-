import json
import os

USER_DATA_FILE = 'user_data.json'

def save_to_json(key, value):
    """Belirtilen anahtar ve değeri JSON dosyasına kaydeder/günceller."""
    data = {}
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    data[key] = value
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_from_json(key):
    """Belirtilen anahtara karşılık gelen değeri JSON dosyasından okur."""
    if not os.path.exists(USER_DATA_FILE):
        return None
    with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return None
    return data.get(key)


def list_json_data():
    """Tüm kullanıcı verilerini JSON dosyasından listeler."""
    if not os.path.exists(USER_DATA_FILE):
        return {}
    with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}
    return data 