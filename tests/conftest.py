# -*- coding: utf-8 -*-
"""pytest ortak kurulumu.

QtWebEngineWidgets, QApplication OLUŞTURULMADAN önce import edilmek zorunda
(`ui.tau_window` → `ultron_focus_view` onu çekiyor). Test modülleri kendi
QApplication'ını kurduğu için, alfabetik sırada önce gelen bir modül (ör.
test_settings_view) uygulamayı kurarsa sonraki modülün `ui.tau_window` importu
"QtWebEngineWidgets must be imported ... before a QCoreApplication instance is
created" hatasıyla toplanamıyordu. Burada her şeyden önce yüklenir.
"""
try:
    from PyQt5 import QtWebEngineWidgets  # noqa: F401
except Exception:  # WebEngine kurulu değilse o testler zaten kendi hatasını verir
    pass
