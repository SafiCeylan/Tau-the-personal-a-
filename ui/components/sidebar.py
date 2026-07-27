from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

class SidebarWidget(QFrame):
    page_changed = pyqtSignal(int)
    new_chat_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self.setFixedWidth(240)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(10)

        # 1. Ultron Brand Header
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(10)
        
        # Ultron Emblem
        emblem = QLabel("⚡")
        emblem.setFixedSize(38, 38)
        emblem.setAlignment(Qt.AlignCenter)
        emblem.setStyleSheet("""
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, fx:0.5, fy:0.5,
                stop:0 #ffffff, stop:0.55 #ff1a26, stop:1 #660008);
            color: #ffffff;
            font-weight: 900;
            font-size: 17px;
            border-radius: 9px;
            border: 1px solid #ff4d58;
        """)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        
        app_name = QLabel("ULTRON")
        app_name.setStyleSheet("color: #ff1a26; font-size: 17px; font-weight: 900; letter-spacing: 2px;")
        
        app_sub = QLabel("NEURAL CORE v3.0")
        app_sub.setStyleSheet("color: #a88e93; font-size: 9.5px; font-weight: 700; letter-spacing: 1px;")
        
        title_box.addWidget(app_name)
        title_box.addWidget(app_sub)
        
        brand_layout.addWidget(emblem)
        brand_layout.addLayout(title_box)
        brand_layout.addStretch()
        
        layout.addLayout(brand_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: rgba(255, 26, 38, 0.25); height: 1px; border: none;")
        layout.addWidget(sep)
        layout.addSpacing(4)

        # New Session Button
        self.new_chat_btn = QPushButton("🔴  YENİ OTURUM BAŞLAT")
        self.new_chat_btn.setCursor(Qt.PointingHandCursor)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 26, 38, 0.16);
                color: #ff4d58;
                border: 1px solid rgba(255, 26, 38, 0.45);
                border-radius: 8px;
                padding: 10px 12px;
                font-weight: 800;
                font-size: 11.5px;
                letter-spacing: 0.8px;
                text-align: center;
            }
            QPushButton:hover {
                background: rgba(255, 26, 38, 0.32);
                border-color: #ff1a26;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #80000a;
            }
        """)
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_chat_btn)

        layout.addSpacing(6)

        # Nav Title
        nav_label = QLabel("PROTOKOL MENÜSÜ")
        nav_label.setStyleSheet("color: #73575c; font-size: 9.5px; font-weight: 800; letter-spacing: 1.5px; padding-left: 2px;")
        layout.addWidget(nav_label)

        # Navigation Buttons (Use '&&' so Qt does not create mnemonic underscores!)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        self.nav_items = [
            ("💬 Terminal / Sohbet", 0),
            ("🌌 Ultron Odak Modu", 6),
            ("🎛️ Mod && Rutin Yöneticisi", 7),
            ("⏰ Görev && Hatırlatıcı", 1),
            ("🧠 Veri Hafızası", 2),
            ("🎭 Duygu && Tehdit Analizi", 3),
            ("📊 Sistem İstatistikleri", 4),
            ("⚙️ Çekirdek Ayarları", 5),
        ]

        self.buttons = {}
        for text, index in self.nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            
            idx = index
            btn.clicked.connect(lambda checked, i=idx: self._on_btn_clicked(i))
            
            self.btn_group.addButton(btn, index)
            layout.addWidget(btn)
            self.buttons[index] = btn

        # Default select Chat
        if 0 in self.buttons:
            self.buttons[0].setChecked(True)

        layout.addStretch()

        # Bottom Provider Status Badge
        self.status_box = QFrame()
        self.status_box.setStyleSheet("""
            QFrame {
                background: rgba(18, 5, 8, 0.9);
                border: 1px solid rgba(255, 26, 38, 0.3);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        sb_layout = QVBoxLayout(self.status_box)
        sb_layout.setContentsMargins(8, 8, 8, 8)
        sb_layout.setSpacing(4)

        status_head = QLabel("NEURAL STREAM SAĞLAYICI")
        status_head.setStyleSheet("color: #73575c; font-size: 9px; font-weight: 800; letter-spacing: 1px;")
        
        self.status_text = QLabel("🔴 Ollama (Gemma 3:4b)")
        self.status_text.setStyleSheet("color: #ff4d58; font-size: 11px; font-weight: 700;")
        
        sb_layout.addWidget(status_head)
        sb_layout.addWidget(self.status_text)

        layout.addWidget(self.status_box)

    def _on_btn_clicked(self, index):
        self.page_changed.emit(index)

    def update_provider_status(self, provider_name, model_name=""):
        if model_name:
            self.status_text.setText(f"🔴 {provider_name} ({model_name})")
        else:
            self.status_text.setText(f"🔴 {provider_name}")
