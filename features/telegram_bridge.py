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
import os
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


def ana_menu_klavyesi() -> dict:
    """Telegram Ana Kategori Menüsü."""
    return {
        "keyboard": [
            [{"text": "🖥️ Pencere & Gezinme"}, {"text": "✍️ Yazı & Düzenleme"}],
            [{"text": "🌐 Tarayıcı & Sekme"}, {"text": "🎵 Medya & Ses"}],
            [{"text": "💻 Sistem & Güç"}, {"text": "📊 Bilgi & Brifing"}],
            [{"text": "⭐ Özel Kısayollarım"}, {"text": "📸 Ekran Görüntüsü Al"}, {"text": "🎛️ Menüyü Kapat"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def ozel_klavye() -> dict:
    """Kullanıcının eklediği dinamik özel kısayollar menüsü."""
    from features import custom_shortcuts
    shortcuts = custom_shortcuts.yukle()

    buttons = []
    current_row = []
    for ad in shortcuts.keys():
        btn_text = ad if ad.startswith(("⚡", "🔍", "🖥️", "📋", "⭐", "⌨️")) else f"⭐ {ad}"
        current_row.append({"text": btn_text})
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)

    # Yönetim Butonları
    buttons.append([{"text": "➕ Kısayol Ekle"}, {"text": "🗑️ Kısayol Sil"}])
    buttons.append([{"text": "🏠 Ana Menü"}])

    return {
        "keyboard": buttons,
        "resize_keyboard": True,
        "is_persistent": True
    }


def pencere_gezinme_klavyesi() -> dict:
    """Pencere ve Masaüstü Gezinme Menüsü."""
    return {
        "keyboard": [
            [{"text": "🔄 Alt+Tab"}, {"text": "🔙 Alt+Shift+Tab"}, {"text": "🖥️ Win+D"}],
            [{"text": "📁 Win+E"}, {"text": "📋 Win+V"}, {"text": "📸 Win+Shift+S"}],
            [{"text": "⚙️ Ctrl+Shift+Esc"}, {"text": "❌ Alt+F4"}, {"text": "🔒 Win+L"}],
            [{"text": "⬆️ Win+Up"}, {"text": "⬇️ Win+Down"}, {"text": "⬅️ Win+Left"}, {"text": "➡️ Win+Right"}],
            [{"text": "🏠 Ana Menü"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def yazi_duzenleme_klavyesi() -> dict:
    """Yazı ve Düzenleme Menüsü."""
    return {
        "keyboard": [
            [{"text": "📋 Ctrl+C"}, {"text": "📋 Ctrl+V"}, {"text": "✂️ Ctrl+X"}],
            [{"text": "↩️ Ctrl+Z"}, {"text": "↪️ Ctrl+Y"}, {"text": "🅰️ Ctrl+A"}],
            [{"text": "💾 Ctrl+S"}, {"text": "🔍 Ctrl+F"}, {"text": "🖨️ Ctrl+P"}],
            [{"text": "↵ Enter"}, {"text": "⌨️ Alt+Enter"}, {"text": "↹ Tab"}],
            [{"text": "⎋ Escape"}, {"text": "🔙 Backspace"}, {"text": "🗑️ Delete"}],
            [{"text": "🏠 Ana Menü"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def tarayici_klavyesi() -> dict:
    """Tarayıcı ve Sekme Yönetim Menüsü."""
    return {
        "keyboard": [
            [{"text": "➕ Ctrl+T"}, {"text": "❌ Ctrl+W"}, {"text": "↩️ Ctrl+Shift+T"}],
            [{"text": "➡️ Ctrl+Tab"}, {"text": "⬅️ Ctrl+Shift+Tab"}, {"text": "🔄 F5"}],
            [{"text": "🌐 Ctrl+N"}, {"text": "🕵️ Ctrl+Shift+N"}, {"text": "🖥️ F11"}],
            [{"text": "🏠 Ana Menü"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def medya_klavyesi() -> dict:
    """Ekran ve Medya Yönetim Menüsü."""
    return {
        "keyboard": [
            [{"text": "📸 Ekran Görüntüsü Al"}, {"text": "⏯️ Oynat/Duraklat"}],
            [{"text": "🔊 Ses Yükselt (%10)"}, {"text": "🔉 Ses Düşür (%10)"}, {"text": "🔇 Sesi Sustur"}],
            [{"text": "⏭️ Sonraki Şarkı"}, {"text": "⏮️ Önceki Şarkı"}],
            [{"text": "🏠 Ana Menü"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def sistem_klavyesi() -> dict:
    """Sistem ve Uygulama Yönetim Menüsü."""
    return {
        "keyboard": [
            [{"text": "📊 Sistem Durumu"}, {"text": "🌐 İnternet Kontrolü"}],
            [{"text": "🌐 Chrome'u Aç"}, {"text": "💻 Terminal / CMD Aç"}],
            [{"text": "📂 İndirilenler Klasörü"}, {"text": "🧮 Hesap Makinesi Aç"}],
            [{"text": "🔒 PC Kilitle"}, {"text": "🌙 Uyku Modu"}],
            [{"text": "🏠 Ana Menü"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def brifing_klavyesi() -> dict:
    """Bilgi, Brifing ve Not Menüsü."""
    return {
        "keyboard": [
            [{"text": "☀️ Sabah Brifingi"}, {"text": "🌦️ Hava Durumu"}],
            [{"text": "💱 Dolar & Euro Kuru"}, {"text": "📰 Son Haberler"}],
            [{"text": "⏰ Hatırlatmalarım"}, {"text": "📋 Notlarım"}],
            [{"text": "🏠 Ana Menü"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def set_bot_commands(token: str) -> bool:
    """Telegram istemcisindeki slash (/) komut menüsünü kaydeder."""
    commands = [
        {"command": "menu", "description": "🏠 Ana Menü ve Tüm Kategoriler"},
        {"command": "pencere", "description": "🖥️ Pencere & Gezinme (Alt+Tab, Win+D, Win+E)"},
        {"command": "duzenleme", "description": "✍️ Yazı & Düzenleme (Ctrl+C, Ctrl+V, Ctrl+Z)"},
        {"command": "tarayici", "description": "🌐 Tarayıcı & Sekme (Ctrl+T, Ctrl+W, F5)"},
        {"command": "medya", "description": "🎵 Medya & Ses (Oynat, Duraklat, Ses)"},
        {"command": "sistem", "description": "📊 Sistem durumu (CPU/RAM/Disk)"},
        {"command": "sistem_menu", "description": "💻 Sistem & Güç menüsü (Chrome, CMD, güç)"},
        {"command": "brifing_menu", "description": "📊 Brifing & Bilgi Servisleri"},
        {"command": "menu_kapat", "description": "🎛️ Hızlı buton takımını gizle"},
        {"command": "alt_tab", "description": "🔄 Alt+Tab bas (Sonraki pencere)"},
        {"command": "win_d", "description": "🖥️ Win+D bas (Masaüstünü göster)"},
        {"command": "win_e", "description": "📁 Win+E bas (Dosya Gezgini)"},
        {"command": "ekran", "description": "📸 Ekran görüntüsü al ve gönder"},
        {"command": "enter", "description": "↵ Enter tuşuna bas"},
        {"command": "alt_f4", "description": "❌ Alt+F4 pencere kapat"},
        {"command": "brifing", "description": "☀️ Sabah Brifingi al"}
    ]
    res = api_call(token, "setMyCommands", commands=commands)
    return res is not None


def send_photo(token: str, chat_id, photo_path: str, caption: str = '') -> bool:
    """Fotoğraf gönderir (multipart upload)."""
    if requests is None or not os.path.exists(photo_path):
        return False
    try:
        with open(photo_path, 'rb') as f:
            r = requests.post(
                _url(token, 'sendPhoto'),
                data={'chat_id': chat_id, 'caption': (caption or '')[:1000]},
                files={'photo': f},
                timeout=60,
            )
        return bool(r.json().get('ok'))
    except Exception as e:
        print(f"[Telegram] Foto gönderilemedi: {type(e).__name__}")
        return False


def send_document(token: str, chat_id, dosya_yolu: str, caption: str = ''):
    """
    PC'deki dosyayı telefona gönderir (multipart upload).
    Dönüş: (başarılı_mı, mesaj). Bot API yükleme sınırı 50 MB.
    """
    if requests is None:
        return False, "requests kütüphanesi yok."
    if not os.path.isfile(dosya_yolu):
        return False, "Dosya bulunamadı."

    boyut = os.path.getsize(dosya_yolu)
    if boyut > 50 * 1024 * 1024:
        return False, (f"Dosya {boyut / 1024 / 1024:.0f} MB — Telegram bot sınırı 50 MB. "
                       f"Mail ile göndermeyi deneyebilirsin.")
    try:
        with open(dosya_yolu, 'rb') as f:
            r = requests.post(
                _url(token, 'sendDocument'),
                data={'chat_id': chat_id, 'caption': (caption or '')[:1000]},
                files={'document': (os.path.basename(dosya_yolu), f)},
                timeout=180,
            )
        data = r.json()
        if data.get('ok'):
            return True, "gönderildi"
        return False, str(data.get('description') or 'Telegram reddetti')
    except Exception as e:
        return False, f"{type(e).__name__}"


def get_file_path(token: str, file_id: str):
    """file_id → sunucudaki dosya yolu (indirme için)."""
    res = api_call(token, 'getFile', http_timeout=15, file_id=file_id)
    return res.get('file_path') if res else None


def download_file(token: str, file_path: str, dest: str) -> bool:
    """Telegram sunucusundaki dosyayı diske indirir (bot API sınırı: 20MB)."""
    if requests is None:
        return False
    try:
        url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[Telegram] Dosya indirilemedi: {type(e).__name__}")
        return False


def bot_bilgisi(token: str):
    """Token doğrulama: bot kullanıcı adını döner (test butonu için)."""
    me = api_call(token, 'getMe', http_timeout=10)
    return me.get('username') if me else None
