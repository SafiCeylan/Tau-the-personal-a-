import os
import json
import psutil
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QUrl, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel


class FocusBridge(QObject):
    """Python-JS Bridge for Web-based Ultron Focus Overlay"""
    message_sent = pyqtSignal(str)
    switch_mode_requested = pyqtSignal()
    min_window_requested = pyqtSignal()
    max_window_requested = pyqtSignal()
    close_window_requested = pyqtSignal()
    voice_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # psutil'in ilk ölçümü her zaman 0.0 döner — burada bir kez ısıtıyoruz
        # ki arayüzdeki ilk CPU değeri yanlış olmasın.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
        self._last_cpu = 0.0
        self._last_ram = 0.0

    @pyqtSlot(result=str)
    def get_initial_state(self):
        return json.dumps({
            "status": "active",
            "system_name": "ULTRON NEURAL OVERLAY v4.0",
            "matrix_stream": "ACTIVE",
            "state": "IDLE",
            "core_health": 99,
            "telegram_bot": "@Ultrontau_bot",
            "welcome_message": "Ben ULTRON Nöral Çekirdeği. Sistem protokolleri aktif. Nasıl bir komut vermek istersiniz?"
        })

    @pyqtSlot(result=str)
    def get_telemetry(self):
        # Ölçüm alınamazsa uydurma değer basmayız; son bilinen değerde kalırız.
        try:
            self._last_cpu = psutil.cpu_percent(interval=None)
            self._last_ram = psutil.virtual_memory().percent
        except Exception:
            pass

        cpu = self._last_cpu
        ram = self._last_ram
        freq_str = f"{4.20 + (cpu / 100.0) * 0.6:.2f}GHz"
        temp_str = f"{300 + int(cpu * 0.8)}K"

        return json.dumps({
            "cpu": cpu,
            "ram": ram,
            "core_load": min(99, max(12, int(cpu * 0.95 + 15))),
            "freq": freq_str,
            "temp": temp_str
        })

    @pyqtSlot(str, result=str)
    def send_command(self, text):
        """Komutu ana pencereye iletir. Cevap ASENKRON gelir (add_message ile);
        burada sahte bir 'başarılı' metni döndürmeyiz."""
        if not text or not text.strip():
            return json.dumps({"status": "error", "message": "Boş komut."})
        self.message_sent.emit(text.strip())
        return json.dumps({"status": "ok"})

    @pyqtSlot(str, result=str)
    def execute_quick_action(self, action_id):
        actions = {
            "youtube": "YouTube aç",
            "google": "Google aç",
            "threat": "Bugünkü duygu durumum nedir?",
            "reminder": "Yarın saat 10:00'da su içmeyi hatırlat",
            "telemetry": "Sistem durumunu göster",
            "chat": "Ultron merhaba"
        }
        cmd = actions.get(action_id, action_id)
        if not cmd:
            return json.dumps({"status": "error", "message": "Tanımsız hızlı işlem."})
        self.message_sent.emit(cmd)
        return json.dumps({"status": "ok", "command": cmd})

    @pyqtSlot(result=str)
    def start_voice_input(self):
        """Komut kutusu boşken mikrofon butonu buraya düşer."""
        self.voice_requested.emit()
        return json.dumps({"status": "ok"})

    @pyqtSlot(str, result=str)
    def toggle_view_mode(self, mode):
        self.switch_mode_requested.emit()
        return json.dumps({"status": "ok", "mode": mode})

    @pyqtSlot()
    def minimize_window(self):
        self.min_window_requested.emit()

    @pyqtSlot()
    def maximize_window(self):
        self.max_window_requested.emit()

    @pyqtSlot()
    def close_window(self):
        self.close_window_requested.emit()


class ConfirmationCardWidget(QFrame):
    """Holografik Ultron Güvenlik Onay Kartı Overlay"""
    def __init__(self, message_text: str, on_confirm, on_cancel, parent=None):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.init_ui(message_text)

    def init_ui(self, message_text: str):
        self.setStyleSheet("""
            QFrame {
                background: rgba(30, 5, 8, 0.95);
                border: 2px solid #ff1a26;
                border-radius: 14px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("⚠️ ULTRON GÜVENLİK PROTOKOLÜ ONAYI GEREKLİ")
        title.setStyleSheet("color: #ff4d58; font-size: 11px; font-weight: 900; letter-spacing: 1.5px;")
        layout.addWidget(title)

        self.body = QLabel(message_text)
        self.body.setWordWrap(True)
        self.body.setStyleSheet("color: #ffffff; font-size: 13px; font-family: Consolas, sans-serif;")
        layout.addWidget(self.body)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        confirm_btn = QPushButton("✅ EVET, İŞLEMİ ÇALIŞTIR")
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: #ff1a26;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #ff4d58; }
        """)
        confirm_btn.clicked.connect(self._do_confirm)

        cancel_btn = QPushButton("❌ İPTAL ET")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.3); }
        """)
        cancel_btn.clicked.connect(self._do_cancel)

        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _do_confirm(self):
        self.hide()
        if self.on_confirm:
            self.on_confirm()

    def _do_cancel(self):
        self.hide()
        if self.on_cancel:
            self.on_cancel()


class UltronFocusViewWidget(QWidget):
    """Direct 1:1 Web Engine Ultron Focus View Widget"""
    message_sent = pyqtSignal(str)
    switch_mode_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    maximize_requested = pyqtSignal()
    close_requested = pyqtSignal()
    voice_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_ready = False
        self._js_queue = []
        self._confirm_card = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        from PyQt5.QtGui import QColor
        self.setStyleSheet("background-color: #030408;")

        self.web_view = QWebEngineView(self)
        self.web_view.setContextMenuPolicy(Qt.NoContextMenu)
        self.web_view.setStyleSheet("background-color: #030408;")
        self.web_view.page().setBackgroundColor(QColor("#030408"))

        # Setup QWebChannel Bridge
        self.bridge = FocusBridge(self)
        self.bridge.message_sent.connect(self.message_sent.emit)
        self.bridge.switch_mode_requested.connect(self.switch_mode_requested.emit)
        self.bridge.min_window_requested.connect(self.minimize_requested.emit)
        self.bridge.max_window_requested.connect(self.maximize_requested.emit)
        self.bridge.close_window_requested.connect(self.close_requested.emit)
        self.bridge.voice_requested.connect(self.voice_requested.emit)

        self.channel = QWebChannel(self)
        self.channel.registerObject("pybridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Sayfa yüklenmeden çalıştırılan JS sessizce kaybolur → kuyruğa alıyoruz.
        self.web_view.loadFinished.connect(self._on_load_finished)

        # Load html file from ui/focus_web/index.html
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(base_dir, "focus_web", "index.html")
        self.web_view.load(QUrl.fromLocalFile(html_path))

        layout.addWidget(self.web_view)

    # ------------------------------------------------------------------
    # JS köprüsü (Python → sayfa)
    # ------------------------------------------------------------------
    def _on_load_finished(self, ok: bool):
        if not ok:
            print("[ULTRON] Odak sayfası yüklenemedi (focus_web/index.html).")
            return
        self._page_ready = True
        queued, self._js_queue = self._js_queue, []
        for code in queued:
            self.web_view.page().runJavaScript(code)

    def _run_js(self, code: str):
        if self._page_ready:
            self.web_view.page().runJavaScript(code)
        elif len(self._js_queue) < 200:
            self._js_queue.append(code)

    def add_message(self, sender: str, text: str):
        safe_text = json.dumps(text)
        fn = "appendUserMsg" if sender == "user" else "appendSystemMsg"
        self._run_js(f"if (typeof window.{fn} === 'function') window.{fn}({safe_text});")

    def set_ai_state(self, state: str):
        safe_state = json.dumps(str(state).upper())
        self._run_js(f"if (typeof window.setCoreState === 'function') window.setCoreState({safe_state});")

    # --- Canlı akış (Ollama streaming) ---
    def begin_stream(self):
        self._run_js("if (typeof window.beginStreamMsg === 'function') window.beginStreamMsg();")

    def update_stream(self, partial: str):
        safe = json.dumps(partial)
        self._run_js(f"if (typeof window.updateStreamMsg === 'function') window.updateStreamMsg({safe});")

    def end_stream(self, full_text: str):
        safe = json.dumps(full_text)
        self._run_js(f"if (typeof window.endStreamMsg === 'function') window.endStreamMsg({safe});")

    def set_active(self, active: bool):
        """Sayfa görünmüyorken 3D render ve telemetri anketini durdurur."""
        flag = "true" if active else "false"
        self._run_js(f"if (typeof window.setUltronActive === 'function') window.setUltronActive({flag});")

    # ------------------------------------------------------------------
    # Güvenlik onay kartı (web sayfasının ÜSTÜNDE duran Qt katmanı)
    # ------------------------------------------------------------------
    def add_confirmation_card(self, message_text: str, on_confirm, on_cancel):
        self.hide_confirmation_card()

        def _wrap(cb):
            def _inner():
                self.hide_confirmation_card()
                if cb:
                    cb()
            return _inner

        card = ConfirmationCardWidget(message_text, _wrap(on_confirm), _wrap(on_cancel), self)
        self._confirm_card = card
        self._place_confirmation_card()
        card.show()
        card.raise_()

    def hide_confirmation_card(self):
        if self._confirm_card is not None:
            card, self._confirm_card = self._confirm_card, None
            card.hide()
            card.deleteLater()

    def _place_confirmation_card(self):
        """Kart eskiden (0,0)'da boyutsuz duruyordu — ortala ve komut çubuğunun
        üstüne yerleştir."""
        card = self._confirm_card
        if card is None:
            return
        width = max(360, min(720, self.width() - 80))
        card.setFixedWidth(width)
        card.body.setFixedWidth(width - 44)
        card.adjustSize()
        x = max(0, (self.width() - card.width()) // 2)
        y = max(20, self.height() - card.height() - 120)
        card.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_confirmation_card()

    # Sayfa değişimini QStackedWidget zaten show/hide olayıyla bildirir —
    # duraklatmayı buna bağlamak switch_page çağrısına güvenmekten daha sağlam.
    def showEvent(self, event):
        super().showEvent(event)
        self.set_active(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.set_active(False)
