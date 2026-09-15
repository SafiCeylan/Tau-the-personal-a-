# -*- coding: utf-8 -*-
"""
ULTRON — Floating Chat Bubble Component
Ultron avatarı tıklandığında beliren futuristic, şeffaf hızlı komut girişi ve yanıt balonu.
"""

from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QFrame
)


class FloatingChatBubble(QWidget):
    """Masaüstü avatarının yanında açılan hızlı komut penceresi."""
    command_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(360, 220)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Translucent dark glass container
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 5, 8, 230);
                border: 1px solid rgba(255, 26, 38, 140);
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QLabel("🤖 ULTRON NEURAL CORE", self.container)
        self.lbl_title.setStyleSheet("color: #ff4d58; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        self.btn_close = QPushButton("✕", self.container)
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff1a26;
            }
        """)
        self.btn_close.clicked.connect(self.hide)
        header_layout.addWidget(self.btn_close)

        layout.addLayout(header_layout)

        # Response area
        self.txt_response = QTextEdit(self.container)
        self.txt_response.setReadOnly(True)
        self.txt_response.setPlaceholderText("Komut bekleniyor...")
        self.txt_response.setStyleSheet("""
            QTextEdit {
                background-color: rgba(5, 2, 4, 180);
                border: 1px solid rgba(255, 26, 38, 50);
                border-radius: 6px;
                color: #e0e0e0;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 11px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.txt_response)

        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)

        self.input_cmd = QLineEdit(self.container)
        self.input_cmd.setPlaceholderText("Komut verin (örn. saat kaç, zen aç)...")
        self.input_cmd.setStyleSheet("""
            QLineEdit {
                background-color: rgba(15, 8, 12, 220);
                border: 1px solid rgba(255, 26, 38, 100);
                border-radius: 6px;
                color: #ffffff;
                padding: 6px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #ff1a26;
            }
        """)
        self.input_cmd.returnPressed.connect(self._on_submit)
        input_layout.addWidget(self.input_cmd)

        self.btn_send = QPushButton("▶", self.container)
        self.btn_send.setFixedSize(30, 28)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #ff1a26;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff4d58;
            }
        """)
        self.btn_send.clicked.connect(self._on_submit)
        input_layout.addWidget(self.btn_send)

        layout.addLayout(input_layout)
        main_layout.addWidget(self.container)

    def _on_submit(self):
        text = self.input_cmd.text().strip()
        if text:
            self.txt_response.clear()
            self.txt_response.setText(f"💬 **Kullanıcı:** {text}\n⏳ *İşleniyor...*")
            self.input_cmd.clear()
            self.command_submitted.emit(text)

    def set_response(self, text: str):
        """Ultron'dan gelen yanıtı baloncukta gösterir."""
        self.txt_response.setText(text)
        self.txt_response.moveCursor(self.txt_response.textCursor().End)

    def append_stream(self, chunk: str):
        """Yayınlanan yanıt parçalarını akıtır."""
        self.txt_response.moveCursor(self.txt_response.textCursor().End)
        self.txt_response.insertPlainText(chunk)

    def position_next_to(self, avatar_rect):
        """Avatarın konumuna göre balonu avatarın yanına veya üstüne yerleştirir."""
        x = avatar_rect.x() + avatar_rect.width() + 10
        y = avatar_rect.y() - 40
        
        # Ekran sınırları kontrolü
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        if x + self.width() > screen.width():
            x = avatar_rect.x() - self.width() - 10
        if y < 0:
            y = 10
        if y + self.height() > screen.height():
            y = screen.height() - self.height() - 10

        self.move(x, y)
