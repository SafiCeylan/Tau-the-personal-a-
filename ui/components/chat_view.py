import html
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit, QPushButton,
    QLabel, QFrame, QScrollArea, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from ui.ai_core_widget import AICoreWidget

class ChatBubble(QFrame):
    """Ultron Sci-Fi Chat Bubble"""
    def __init__(self, sender: str, text: str, timestamp: str = "", parent=None):
        super().__init__(parent)
        self.sender = sender
        self.raw_text = text
        self.timestamp = timestamp
        self.init_ui()

    def init_ui(self):
        is_user = self.sender == "user"
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        bubble_box = QFrame()
        bubble_layout = QVBoxLayout(bubble_box)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(6)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        if is_user:
            avatar = QLabel("👤")
            sender_title = QLabel("KULLANICI")
            sender_title.setStyleSheet("color: #ff4d58; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
            bubble_box.setStyleSheet("""
                QFrame {
                    background: rgba(40, 10, 15, 0.85);
                    border: 1px solid rgba(255, 26, 38, 0.45);
                    border-top-right-radius: 2px;
                    border-top-left-radius: 12px;
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                }
            """)
            header_layout.addWidget(sender_title)
            header_layout.addWidget(avatar)
            header_layout.addStretch()
        else:
            avatar = QLabel("🔴")
            sender_title = QLabel("ULTRON NEURAL CORE")
            sender_title.setStyleSheet("color: #ff1a26; font-weight: 900; font-size: 11px; letter-spacing: 1.5px;")
            bubble_box.setStyleSheet("""
                QFrame {
                    background: rgba(18, 5, 8, 0.95);
                    border: 1px solid rgba(255, 26, 38, 0.35);
                    border-top-left-radius: 2px;
                    border-top-right-radius: 12px;
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                }
            """)
            header_layout.addWidget(avatar)
            header_layout.addWidget(sender_title)
            header_layout.addStretch()

        if self.timestamp:
            time_lbl = QLabel(self.timestamp)
            time_lbl.setStyleSheet("color: #73575c; font-size: 10px;")
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
                font-size: 13px;
                line-height: 1.5;
            }
        """)

        self._render_text(self.raw_text)
        bubble_layout.addWidget(self.content_browser)

        if is_user:
            layout.addStretch()
            layout.addWidget(bubble_box)
        else:
            layout.addWidget(bubble_box)
            layout.addStretch()

    def _render_text(self, text: str):
        """Metni işleyip yüksekliği yeniden hesaplar.
        NOT: Üst sınır YOK — uzun cevaplar kesilmez; dış scroll alanı kaydırır."""
        self.content_browser.setHtml(self.format_markdown(text))
        self.content_browser.document().adjustSize()
        doc_height = int(self.content_browser.document().size().height()) + 15
        self.content_browser.setFixedHeight(max(30, doc_height))

    def update_text(self, text: str):
        """Streaming için: balon içeriğini canlı günceller."""
        self.raw_text = text
        self._render_text(text)

    def format_markdown(self, text: str) -> str:
        """Ultron Red Markdown formatting."""
        escaped = html.escape(text)

        # Bold & Italic
        escaped = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #ff4d58;">\1</b>', escaped)
        escaped = re.sub(r'\*(.*?)\*', r'<i>\1</i>', escaped)

        # Code blocks ```code```
        def code_block_replacer(match):
            code_content = match.group(1).strip()
            return f'''
            <div style="background-color: #0b0204; border: 1px solid rgba(255,26,38,0.4); border-radius: 6px; padding: 10px; margin: 8px 0; font-family: Consolas, monospace; font-size: 12px; color: #ff4d58;">
                <pre style="margin:0; white-space: pre-wrap;">{code_content}</pre>
            </div>
            '''

        escaped = re.sub(r'```(?:[a-zA-Z]*\n)?(.*?)```', code_block_replacer, escaped, flags=re.DOTALL)
        
        # Inline code `code`
        escaped = re.sub(r'`(.*?)`', r'<code style="background: rgba(255,26,38,0.2); color: #ff4d58; padding: 2px 5px; border-radius: 4px; font-family: Consolas;">\1</code>', escaped)

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
                border: 2px solid #ff1a26;
                border-radius: 14px;
                padding: 12px;
                margin: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("⚠️ ULTRON GÜVENLİK PROTOKOLÜ ONAYI GEREKLİ")
        title.setStyleSheet("color: #ff4d58; font-size: 11px; font-weight: 900; letter-spacing: 1.5px;")
        layout.addWidget(title)

        body = QLabel(message_text)
        body.setWordWrap(True)
        body.setStyleSheet("color: #ffffff; font-size: 13px; font-family: Consolas, sans-serif;")
        layout.addWidget(body)

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
            QPushButton:hover {
                background: #ff4d58;
            }
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
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.3);
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
        """Standard ChatView ekranına tıklanabilir güvenlik onay kartını basar"""
        card = ConfirmationCardWidget(message_text, on_confirm, on_cancel)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, card)
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # 1. Ultron Core Visualizer Container
        self.core_container = QFrame()
        self.core_container.setStyleSheet("""
            background: rgba(14, 4, 7, 0.7);
            border: 1px solid rgba(255, 26, 38, 0.25);
            border-radius: 12px;
        """)
        core_layout = QVBoxLayout(self.core_container)
        core_layout.setContentsMargins(8, 8, 8, 8)

        self.ai_core = AICoreWidget()
        self.ai_core.setFixedHeight(180)
        core_layout.addWidget(self.ai_core)

        main_layout.addWidget(self.core_container)

        # Quick Suggestions / Protocols Bar
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        suggestions = [
            ("⏰ Hatırlatma Ekle", "Yarın saat 10:00'da su içmeyi hatırlat"),
            ("📱 WhatsApp Rehberi", "whatsapp kişileri listele"),
            ("🌐 YouTube Aç", "YouTube aç"),
            ("❓ Ultron Yetenekleri", "Bana yeteneklerini anlat"),
        ]

        for label, text in suggestions:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 26, 38, 0.1);
                    color: #ff4d58;
                    border: 1px solid rgba(255, 26, 38, 0.3);
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: rgba(255, 26, 38, 0.25);
                    border-color: #ff1a26;
                    color: #ffffff;
                }
            """)
            msg_text = text
            btn.clicked.connect(lambda _, t=msg_text: self.send_suggestion(t))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        main_layout.addLayout(quick_layout)

        # 2. Scrollable Messages Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(self.scroll_content)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # 3. Input Toolbar
        input_container = QFrame()
        input_container.setStyleSheet("""
            background: rgba(14, 4, 7, 0.95);
            border: 1px solid rgba(255, 26, 38, 0.4);
            border-radius: 10px;
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(8, 6, 8, 6)
        input_layout.setSpacing(8)

        # Mic Button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setToolTip("Sesli Komut Ver")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 26, 38, 0.15);
                border: 1px solid rgba(255, 26, 38, 0.35);
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255, 26, 38, 0.35);
                border-color: #ff1a26;
            }
        """)
        self.mic_btn.clicked.connect(self.mic_clicked.emit)

        # LineEdit
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ultron Çekirdeğine komut verin...")
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
                padding: 8px 16px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b80012, stop:1 #ff4d58);
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
            self.input_field.clear()
            self.message_sent.emit(text)

    def send_suggestion(self, text: str):
        self.message_sent.emit(text)

    def add_message(self, sender: str, text: str, timestamp: str = ""):
        bubble = ChatBubble(sender, text, timestamp)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, self.scroll_to_bottom)
        return bubble  # streaming güncellemeleri için referans

    def scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_ai_state(self, state: str):
        self.ai_core.set_state(state)
