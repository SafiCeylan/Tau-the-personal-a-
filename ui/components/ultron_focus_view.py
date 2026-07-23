import html
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QLineEdit, QPushButton,
    QScrollArea, QGraphicsOpacityEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

from ui.ai_core_widget import AICoreWidget

class FloatingMessageBubble(QFrame):
    """Holografik Ultron sohbet balonu — tam saydam havada yüzen kart"""
    def __init__(self, sender: str, text: str, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.raw_text = text
        self.displayed_text = ""
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.typewriter_timer = None
        self.init_ui()

    def init_ui(self):
        is_user = self.sender == "user"
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)

        bubble_box = QFrame()
        bubble_layout = QVBoxLayout(bubble_box)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        bubble_layout.setSpacing(6)

        if is_user:
            title = QLabel("📡 KULLANICI İLETİSİ")
            title.setStyleSheet("color: #ff4d58; font-weight: 900; font-size: 10px; letter-spacing: 1.5px;")
            bubble_box.setStyleSheet("""
                QFrame {
                    background: rgba(35, 8, 12, 0.78);
                    border: 1px solid rgba(255, 77, 88, 0.75);
                    border-radius: 12px;
                }
            """)
            bubble_layout.addWidget(title)
        else:
            title = QLabel("🔴 ULTRON NEURAL SYSTEM")
            title.setStyleSheet("color: #ff1a26; font-weight: 900; font-size: 10px; letter-spacing: 2px;")
            bubble_box.setStyleSheet("""
                QFrame {
                    background: rgba(14, 3, 5, 0.88);
                    border: 1px solid rgba(255, 26, 38, 0.85);
                    border-radius: 12px;
                }
            """)
            bubble_layout.addWidget(title)

        self.txt_lbl = QLabel()
        self.txt_lbl.setWordWrap(True)
        self.txt_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-family: Consolas, sans-serif; line-height: 1.4;")
        bubble_layout.addWidget(self.txt_lbl)

        if is_user:
            self.txt_lbl.setText(self.raw_text)
            layout.addStretch()
            layout.addWidget(bubble_box)
        else:
            # Start Typewriter Animation for Ultron responses
            self.char_index = 0
            self.typewriter_timer = QTimer(self)
            self.typewriter_timer.setInterval(15)  # Fast typewriter
            self.typewriter_timer.timeout.connect(self._typewriter_step)
            self.typewriter_timer.start()

            layout.addWidget(bubble_box)
            layout.addStretch()

    def _typewriter_step(self):
        if self.char_index <= len(self.raw_text):
            self.displayed_text = self.raw_text[:self.char_index]
            self.txt_lbl.setText(self.displayed_text)
            self.char_index += 2
        else:
            if self.typewriter_timer:
                self.typewriter_timer.stop()

    def set_fade_level(self, opacity: float):
        """0.0 (tam saydam) ile 1.0 (tam görünür) arasında opaklığı günceller"""
        self.opacity_effect.setOpacity(max(0.0, min(1.0, opacity)))


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
                padding: 10px;
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


class UltronFocusViewWidget(QWidget):
    message_sent = pyqtSignal(str)
    switch_mode_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bubbles = []
        self.init_ui()

    def add_confirmation_card(self, message_text: str, on_confirm, on_cancel):
        """Ekrana tıklanabilir güvenlik onay kartını basar"""
        card = ConfirmationCardWidget(message_text, on_confirm, on_cancel)
        count = self.bubbles_layout.count()
        self.bubbles_layout.insertWidget(count - 1, card)
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def init_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # Layer 0 (BACKGROUND): Fullscreen Animated Ultron AI Core Visualizer Canvas
        self.ai_core = AICoreWidget(self)
        grid.addWidget(self.ai_core, 0, 0)

        # Layer 1 (OVERLAY): Transparent Container for UI Controls & Floating Bubbles
        overlay_widget = QWidget(self)
        overlay_widget.setStyleSheet("background: transparent;")
        
        overlay_layout = QVBoxLayout(overlay_widget)
        overlay_layout.setContentsMargins(24, 16, 24, 16)
        overlay_layout.setSpacing(10)

        # Top Header Bar (HUD Telemetry & Mode Switcher)
        top_bar = QHBoxLayout()
        
        hud_info = QLabel("🔴 ULTRON NEURAL OVERLAY v4.0 // MATRIX STREAM ACTIVE")
        hud_info.setStyleSheet("""
            background: rgba(14, 3, 5, 0.75);
            color: #ff4d58;
            border: 1px solid rgba(255, 26, 38, 0.5);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.5px;
        """)

        mode_btn = QPushButton("🎛️ Standart Görünüme Dön")
        mode_btn.setCursor(Qt.PointingHandCursor)
        mode_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 26, 38, 0.25);
                color: #ffffff;
                border: 1px solid rgba(255, 26, 38, 0.7);
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(255, 26, 38, 0.5);
                border-color: #ff1a26;
            }
        """)
        mode_btn.clicked.connect(self.switch_mode_requested.emit)

        top_bar.addWidget(hud_info)
        top_bar.addStretch()
        top_bar.addWidget(mode_btn)
        overlay_layout.addLayout(top_bar)

        # Floating Messages Scroll Area (Floats over the center core!)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.bubbles_layout = QVBoxLayout(self.scroll_content)
        self.bubbles_layout.setContentsMargins(30, 20, 30, 10)
        self.bubbles_layout.setSpacing(14)
        self.bubbles_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        overlay_layout.addWidget(self.scroll_area, 1)

        # Quick Protocol Actions floating above input bar
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        suggestions = [
            ("⚡ YouTube Aç", "YouTube aç"),
            ("⏰ Hatırlatma Ekle", "Yarın saat 10:00'da su içmeyi hatırlat"),
            ("🎭 Tehdit Raporu", "Bugünkü duygu durumum nedir?"),
            ("🌐 Google Git", "Google aç"),
        ]

        for label, text in suggestions:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 26, 38, 0.15);
                    color: #ff4d58;
                    border: 1px solid rgba(255, 26, 38, 0.4);
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 10px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: rgba(255, 26, 38, 0.35);
                    border-color: #ff1a26;
                    color: #ffffff;
                }
            """)
            msg_text = text
            btn.clicked.connect(lambda _, t=msg_text: self.send_suggestion(t))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        overlay_layout.addLayout(quick_layout)

        # Floating Input Bar at Bottom
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: rgba(14, 3, 5, 0.94);
                border: 1px solid rgba(255, 26, 38, 0.85);
                border-radius: 18px;
                padding: 4px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 4, 14, 4)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ultron Nöral Çekirdeğine emredin...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 14px;
                font-family: Consolas, sans-serif;
                font-weight: 600;
            }
        """)
        self.input_field.returnPressed.connect(self._on_send)

        send_btn = QPushButton("⚡")
        send_btn.setFixedSize(36, 36)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: #ff1a26;
                color: #ffffff;
                border: none;
                border-radius: 18px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ff4d58;
            }
        """)
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(send_btn)

        overlay_layout.addWidget(input_frame)

        grid.addWidget(overlay_widget, 0, 0)

    def _on_send(self):
        txt = self.input_field.text().strip()
        if txt:
            self.input_field.clear()
            self.message_sent.emit(txt)

    def send_suggestion(self, text: str):
        self.message_sent.emit(text)

    def add_message(self, sender: str, text: str):
        """Yeni balonu en alta ekler ve eski balonları yukarı itip Ultron çekirdeği üstünde saydamlaştırır"""
        bubble = FloatingMessageBubble(sender, text)
        self.bubbles.append(bubble)

        count = self.bubbles_layout.count()
        self.bubbles_layout.insertWidget(count - 1, bubble)

        # Recalculate fading for all floating bubbles over the animated background
        total = len(self.bubbles)
        for idx, b in enumerate(self.bubbles):
            pos_from_end = total - 1 - idx
            if pos_from_end == 0:
                op = 1.0
            elif pos_from_end == 1:
                op = 0.70
            elif pos_from_end == 2:
                op = 0.40
            elif pos_from_end == 3:
                op = 0.18
            else:
                op = 0.0

            b.set_fade_level(op)
            if op == 0.0:
                b.hide()

        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def set_ai_state(self, state: str):
        self.ai_core.set_state(state)
