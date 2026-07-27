import html
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit, QPushButton,
    QLabel, QFrame, QScrollArea, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from ui.ai_core_widget import AICoreWidget


class HistoryLineEdit(QLineEdit):
    """Terminal tarzı komut geçmişi olan giriş kutusu.

    Yukarı ok → önceki gönderilen komutlar (eskiye doğru),
    Aşağı ok → sonraki komutlar; en sona gelince yazılmakta olan taslağa döner.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = []
        self._index = None
        self._draft = ""

    def add_to_history(self, text: str):
        text = (text or "").strip()
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            if len(self._history) > 100:
                self._history = self._history[-100:]
        self._index = None
        self._draft = ""

    def _uygula(self, metin: str):
        self.setText(metin)
        self.setCursorPosition(len(metin))

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Up and self._history:
            if self._index is None:
                self._draft = self.text()
                self._index = len(self._history) - 1
            elif self._index > 0:
                self._index -= 1
            self._uygula(self._history[self._index])
            return
        if key == Qt.Key_Down and self._index is not None:
            if self._index < len(self._history) - 1:
                self._index += 1
                self._uygula(self._history[self._index])
            else:
                self._index = None
                self._uygula(self._draft)
            return
        super().keyPressEvent(event)


class ChatBubble(QWidget):
    """Ultron Sci-Fi Compact Chat Bubble"""
    def __init__(self, sender: str, text: str, timestamp: str = "", parent=None):
        super().__init__(parent)
        self.sender = sender
        self.raw_text = text
        self.timestamp = timestamp
        self.init_ui()

    def init_ui(self):
        is_user = self.sender == "user"
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(0)

        bubble_box = QFrame()
        bubble_box.setObjectName("bubbleBox")
        bubble_box.setMaximumWidth(720)
        bubble_layout = QVBoxLayout(bubble_box)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)

        # Header Layout
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        if is_user:
            avatar = QLabel("👤")
            avatar.setStyleSheet("border: none; background: transparent; font-size: 11px;")
            sender_title = QLabel("KULLANICI")
            sender_title.setStyleSheet("border: none; background: transparent; color: #ff4d58; font-weight: 800; font-size: 10.5px; letter-spacing: 1px;")
            bubble_box.setStyleSheet("""
                QFrame#bubbleBox {
                    background: rgba(36, 10, 15, 0.9);
                    border: 1px solid rgba(255, 77, 88, 0.45);
                    border-top-right-radius: 2px;
                    border-top-left-radius: 10px;
                    border-bottom-left-radius: 10px;
                    border-bottom-right-radius: 10px;
                }
            """)
            header_layout.addWidget(avatar)
            header_layout.addWidget(sender_title)
            header_layout.addStretch()
        else:
            avatar = QLabel("🔴")
            avatar.setStyleSheet("border: none; background: transparent; font-size: 11px;")
            sender_title = QLabel("ULTRON NEURAL CORE")
            sender_title.setStyleSheet("border: none; background: transparent; color: #ff1a26; font-weight: 900; font-size: 10.5px; letter-spacing: 1.2px;")
            bubble_box.setStyleSheet("""
                QFrame#bubbleBox {
                    background: rgba(18, 5, 8, 0.95);
                    border: 1px solid rgba(255, 26, 38, 0.4);
                    border-top-left-radius: 2px;
                    border-top-right-radius: 10px;
                    border-bottom-left-radius: 10px;
                    border-bottom-right-radius: 10px;
                }
            """)
            header_layout.addWidget(avatar)
            header_layout.addWidget(sender_title)
            header_layout.addStretch()

        if self.timestamp:
            time_lbl = QLabel(self.timestamp)
            time_lbl.setStyleSheet("border: none; background: transparent; color: #73575c; font-size: 10px; font-weight: 600;")
            header_layout.addWidget(time_lbl)

        bubble_layout.addLayout(header_layout)

        # Content Text Browser
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                color: #f5e6e8;
                font-size: 12.5px;
                line-height: 1.4;
                padding: 0px;
                margin: 0px;
            }
        """)

        self._render_text(self.raw_text)
        bubble_layout.addWidget(self.content_browser)

        if is_user:
            main_layout.addStretch()
            main_layout.addWidget(bubble_box)
        else:
            main_layout.addWidget(bubble_box)
            main_layout.addStretch()

    def _render_text(self, text: str):
        self.content_browser.setHtml(self.format_markdown(text))
        self.content_browser.document().adjustSize()
        doc_height = int(self.content_browser.document().size().height()) + 6
        self.content_browser.setFixedHeight(max(20, doc_height))

    def update_text(self, text: str):
        self.raw_text = text
        self._render_text(text)

    def format_markdown(self, text: str) -> str:
        escaped = html.escape(text)

        # Bold & Italic
        escaped = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #ff4d58;">\1</b>', escaped)
        escaped = re.sub(r'\*(.*?)\*', r'<i>\1</i>', escaped)

        # Code blocks
        def code_block_replacer(match):
            code_content = match.group(1).strip()
            return f'''
            <div style="background-color: #0b0204; border: 1px solid rgba(255,26,38,0.4); border-radius: 5px; padding: 8px 10px; margin: 6px 0; font-family: Consolas, monospace; font-size: 12px; color: #ff4d58;">
                <pre style="margin:0; white-space: pre-wrap;">{code_content}</pre>
            </div>
            '''

        escaped = re.sub(r'```(?:[a-zA-Z]*\n)?(.*?)```', code_block_replacer, escaped, flags=re.DOTALL)
        
        # Inline code
        escaped = re.sub(r'`(.*?)`', r'<code style="background: rgba(255,26,38,0.2); color: #ff4d58; padding: 1px 4px; border-radius: 3px; font-family: Consolas;">\1</code>', escaped)

        escaped = escaped.replace("\n", "<br>")
        
        return f'<div style="color: #f5e6e8; font-family: Consolas, Segoe UI, sans-serif;">{escaped}</div>'


class ConfirmationCardWidget(QFrame):
    """Holografik Ultron Güvenlik Onay Kartı — Tıklanabilir Onay / İptal Butonları"""
    def __init__(self, message_text: str, on_confirm, on_cancel, parent=None):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.init_ui(message_text)

    def init_ui(self, message_text: str):
        self.setStyleSheet("""
            QFrame {
                background: rgba(30, 5, 8, 0.95);
                border: 1px solid #ff1a26;
                border-radius: 10px;
                padding: 10px;
                margin: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel("⚠️ ULTRON GÜVENLİK PROTOKOLÜ ONAYI GEREKLİ")
        title.setStyleSheet("border: none; background: transparent; color: #ff4d58; font-size: 11px; font-weight: 900; letter-spacing: 1.5px;")
        layout.addWidget(title)

        body = QLabel(message_text)
        body.setWordWrap(True)
        body.setStyleSheet("border: none; background: transparent; color: #ffffff; font-size: 12.5px; font-family: Consolas, sans-serif;")
        layout.addWidget(body)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        confirm_btn = QPushButton("✅ EVET, İŞLEMİ ÇALIŞTIR")
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: #ff1a26;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: #ff4d58;
            }
        """)
        confirm_btn.clicked.connect(self._do_confirm)

        cancel_btn = QPushButton("❌ İPTAL ET")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
            }
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


class ChatViewWidget(QWidget):
    message_sent = pyqtSignal(str)
    mic_clicked = pyqtSignal()
    voice_input_requested = pyqtSignal()
    mode_switch_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def add_confirmation_card(self, message_text: str, on_confirm, on_cancel):
        card = ConfirmationCardWidget(message_text, on_confirm, on_cancel)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, card)
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(10)

        # 1. Ultron Core Visualizer Container
        self.core_container = QFrame()
        self.core_container.setStyleSheet("""
            QFrame {
                background: rgba(14, 4, 7, 0.85);
                border: 1px solid rgba(255, 26, 38, 0.35);
                border-radius: 10px;
            }
        """)
        core_layout = QVBoxLayout(self.core_container)
        core_layout.setContentsMargins(4, 4, 4, 4)

        self.ai_core = AICoreWidget()
        self.ai_core.setFixedHeight(135)
        core_layout.addWidget(self.ai_core)

        main_layout.addWidget(self.core_container)

        # Quick Suggestions Bar
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        suggestions = [
            ("⏰ Hatırlatma Ekle", "Yarın saat 10:00'da su içmeyi hatırlat"),
            ("📇 WhatsApp Rehberi", "whatsapp kişileri listele"),
            ("🌐 YouTube Aç", "YouTube aç"),
            ("❓ Ultron Yetenekleri", "Bana yeteneklerini anlat"),
        ]

        for label, text in suggestions:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 26, 38, 0.12);
                    color: #ff4d58;
                    border: 1px solid rgba(255, 26, 38, 0.35);
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: rgba(255, 26, 38, 0.28);
                    border-color: #ff1a26;
                    color: #ffffff;
                }
            """)
            msg_text = text
            btn.clicked.connect(lambda _, t=msg_text: self.send_suggestion(t))
            quick_layout.addWidget(btn)

        # 🎵 Medya kontrol butonları — doğrudan çalışır (sohbete mesaj yazmaz),
        # sonuç yanlarındaki etikette kısa süre gösterilir.
        quick_layout.addSpacing(12)
        for label, aksiyon, ipucu in (
            ("⏮", "prev", "Önceki şarkı"),
            ("⏯", "playpause", "Duraklat / Devam et"),
            ("⏭", "next", "Sonraki şarkı"),
        ):
            mbtn = QPushButton(label)
            mbtn.setCursor(Qt.PointingHandCursor)
            mbtn.setToolTip(f"{ipucu} (YouTube Music, Spotify, tarayıcı — hepsinde çalışır)")
            mbtn.setFixedWidth(38)
            mbtn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 26, 38, 0.12);
                    color: #ff4d58;
                    border: 1px solid rgba(255, 26, 38, 0.35);
                    border-radius: 6px;
                    padding: 5px 4px;
                    font-size: 13px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: rgba(255, 26, 38, 0.28);
                    border-color: #ff1a26;
                    color: #ffffff;
                }
            """)
            mbtn.clicked.connect(lambda _, a=aksiyon: self._medya_kontrol_et(a))
            quick_layout.addWidget(mbtn)

        self.media_status = QLabel("")
        self.media_status.setStyleSheet("color: #a68c90; font-size: 11px;")
        quick_layout.addWidget(self.media_status)

        quick_layout.addStretch()
        main_layout.addLayout(quick_layout)

        # 2. Scrollable Messages Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #060305;
            }
            QScrollArea > QWidget > QWidget {
                background: #060305;
            }
        """)
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: #060305;")
        self.messages_layout = QVBoxLayout(self.scroll_content)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # 3. Input Toolbar
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background: rgba(14, 4, 7, 0.95);
                border: 1px solid rgba(255, 26, 38, 0.45);
                border-radius: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(8, 6, 8, 6)
        input_layout.setSpacing(8)

        # Mic Button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(34, 34)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setToolTip("Sesli Komut Ver")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 26, 38, 0.15);
                border: 1px solid rgba(255, 26, 38, 0.4);
                border-radius: 6px;
                font-size: 15px;
            }
            QPushButton:hover {
                background: rgba(255, 26, 38, 0.35);
                border-color: #ff1a26;
            }
        """)
        self.mic_btn.clicked.connect(self.mic_clicked.emit)

        # LineEdit
        self.input_field = HistoryLineEdit()
        self.input_field.setPlaceholderText("Ultron Çekirdeğine komut verin...  (↑ önceki komut)")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #f5e6e8;
                font-size: 13px;
                font-family: Consolas, sans-serif;
            }
        """)
        self.input_field.returnPressed.connect(self._handle_send)

        # Send Button
        self.send_btn = QPushButton("ÇALIŞTIR ➔")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #99000f, stop:1 #ff1a26);
                color: #ffffff;
                border: 1px solid #ff4d58;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 800;
                letter-spacing: 1px;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b80012, stop:1 #ff4d58);
                border-color: #ff1a26;
            }
        """)
        self.send_btn.clicked.connect(self._handle_send)

        input_layout.addWidget(self.mic_btn)
        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(self.send_btn)

        main_layout.addWidget(input_container)

    def _handle_send(self):
        text = self.input_field.text().strip()
        if text:
            self.input_field.add_to_history(text)
            self.input_field.clear()
            self.message_sent.emit(text)

    def send_suggestion(self, text: str):
        self.input_field.add_to_history(text)
        self.message_sent.emit(text)

    def _medya_kontrol_et(self, aksiyon: str):
        """Medya butonları: tuş sinyalini doğrudan gönderir, sohbete mesaj yazmaz.
        Sonuç etikette 3 saniye görünür."""
        try:
            from features.actions.system_control import medya_kontrol
            _basarili, mesaj = medya_kontrol(aksiyon)
        except Exception as e:
            mesaj = f"Medya kontrolü başarısız: {e}"
        self.media_status.setText(mesaj)
        QTimer.singleShot(3000, lambda: self.media_status.setText(""))

    def add_message(self, sender: str, text: str, timestamp: str = ""):
        bubble = ChatBubble(sender, text, timestamp)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, self.scroll_to_bottom)
        return bubble

    def scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_ai_state(self, state: str):
        self.ai_core.set_state(state)
