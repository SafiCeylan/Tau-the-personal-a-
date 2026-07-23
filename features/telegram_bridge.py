"""
Telegram Köprüsü — ULTRON'a telefondan komut ver.

Ek kütüphane GEREKTIRMEZ: Telegram Bot API'sine doğrudan `requests` ile
long-polling yapılır (getUpdates timeout=20). Webhook yok, port açılmaz.

Güvenlik modeli:
  • Bot token'ı config.json'da (git'e gitmez)
  • SADECE `telegram_chat_id` ile eşleşen kullanıcı komut verebilir —
    yetkisiz herkese kendi chat id'si gösterilir ki sahibi eşleştirebilsin
  • Riskli komutlar masaüstündeki gibi ONAY ister (inline ✅/❌ butonları)
"""

import json
import re

try:
    import requests
except ImportError:
    requests = None


def _url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def api_call(token: str, method: str, http_timeout: int = 30, **params):
    """Bot API çağrısı. Başarıda 'result' içeriğini, hatada None döner.
    NOT: HTTP zaman aşımı 'http_timeout' — Telegram'ın kendi 'timeout' alanı
    (long-polling) params içinde ayrıca gidebilir, isim çakışması olmaz."""
    if requests is None:
        return None
    try:
        r = requests.post(_url(token, method), json=params, timeout=http_timeout)
        data = r.json()
        if data.get('ok'):
            return data.get('result')
        print(f"[Telegram] API hatası ({method}): {data.get('description')}")
        return None
    except Exception as e:
        print(f"[Telegram] Bağlantı hatası ({method}): {type(e).__name__}")
        return None


def send_message(token: str, chat_id, text: str, reply_markup: dict = None) -> bool:
    """
    Mesaj gönderir. Uygulamanın **kalın** biçimi Telegram'ın *kalın* biçimine
    çevrilir; Markdown parse hatasında düz metinle tekrar denenir.
    """
    text = (text or '').strip()
    if not text:
        return False
    text_md = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)[:4000]

    params = {'chat_id': chat_id, 'text': text_md, 'parse_mode': 'Markdown'}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)

    if api_call(token, 'sendMessage', **params) is not None:
        return True
    # Markdown bozuk olabilir (tek yıldız vb.) — düz metin dene
    params = {'chat_id': chat_id, 'text': text[:4000]}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    return api_call(token, 'sendMessage', **params) is not None


def get_updates(token: str, offset=None, timeout: int = 20):
    """Long-polling ile yeni güncellemeleri çeker. Hata durumunda None."""
    params = {
        'timeout': timeout,
        'allowed_updates': ['message', 'callback_query'],
    }
    if offset is not None:
        params['offset'] = offset
    return api_call(token, 'getUpdates', http_timeout=timeout + 15, **params)


def answer_callback(token: str, callback_query_id: str):
    api_call(token, 'answerCallbackQuery', http_timeout=10, callback_query_id=callback_query_id)


def onay_butonlari() -> dict:
    """Onay kartının Telegram karşılığı: inline ✅/❌ butonları."""
    return {'inline_keyboard': [[
        {'text': '✅ ONAYLA VE ÇALIŞTIR', 'callback_data': 'ultron_confirm'},
        {'text': '❌ İPTAL', 'callback_data': 'ultron_cancel'},
    ]]}


def bot_bilgisi(token: str):
    """Token doğrulama: bot kullanıcı adını döner (test butonu için)."""
    me = api_call(token, 'getMe', http_timeout=10)
    return me.get('username') if me else None
