# Arşivlenmiş eski arayüzler

Bu klasör, TAU'nun tek ve resmi arayüzü `ui/tau_window.py` (native PyQt5) ile
birleştirilmeden önce projede bir arada var olan üç ayrı arayüz denemesini
içerir:

- `main_window.py` + `main_window_backup.py` — klasik PyQt5 tab tabanlı arayüz
- `modern_main_window.py` + `web_interface.html` + `style.css` + `css/` + `icons/` + `webfonts/` — QWebEngine tabanlı "modern" web arayüzü
- `main_web.py` + `web_ui/` — ayrı bir QWebEngine denemesi
- `start_web_ui.bat` — yukarıdaki `main_web.py`'yi başlatan eski script

Hiçbiri artık uygulama tarafından import edilmiyor veya kullanılmıyor.
Sadece referans/geçmiş amacıyla saklanmaktadır; silinmesi güvenlidir.
