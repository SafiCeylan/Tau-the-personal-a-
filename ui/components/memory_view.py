from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QComboBox, QDialog, QFormLayout
)
from PyQt5.QtCore import Qt, pyqtSignal

class MemoryItemCard(QFrame):
    delete_requested = pyqtSignal(int)

    def __init__(self, item_id: int, key: str, value: str, category: str, date_str: str = "", parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.key = key
        self.value = value
        self.category = category
        self.date_str = date_str
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: rgba(22, 7, 11, 0.88);
                border: 1px solid rgba(255, 26, 38, 0.3);
                border-radius: 8px;
                padding: 6px;
            }
            QFrame:hover {
                border-color: rgba(255, 26, 38, 0.65);
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        key_lbl = QLabel(self.key)
        key_lbl.setStyleSheet("color: #ff4d58; font-weight: 800; font-size: 14px;")

        cat_badge = QLabel(self.category or "Genel")
        cat_badge.setStyleSheet("""
            background: rgba(255, 26, 38, 0.2);
            color: #ff1a26;
            border: 1px solid rgba(255, 26, 38, 0.4);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #73575c;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff1a26;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.item_id))

        header.addWidget(key_lbl)
        header.addWidget(cat_badge)
        header.addStretch()
        header.addWidget(del_btn)

        # Value Text
        val_lbl = QLabel(self.value)
        val_lbl.setWordWrap(True)
        val_lbl.setStyleSheet("color: #f5e6e8; font-size: 13px;")

        layout.addLayout(header)
        layout.addWidget(val_lbl)

        if self.date_str:
            date_lbl = QLabel(f"📅 {self.date_str}")
            date_lbl.setStyleSheet("color: #73575c; font-size: 10px;")
            layout.addWidget(date_lbl)


class MemoryViewWidget(QWidget):
    add_memory_signal = pyqtSignal(str, str, str)
    delete_memory_signal = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.memories = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title_box = QHBoxLayout()
        head = QLabel("🧠 Ultron Veri Hafızası")
        head.setStyleSheet("color: #ff1a26; font-size: 20px; font-weight: 900; letter-spacing: 1px;")
        
        sub = QLabel("Nöral ağın kullanıcı ve sistem hakkında sakladığı bellek verileri")
        sub.setStyleSheet("color: #a88e93; font-size: 12px;")

        title_box.addWidget(head)
        title_box.addStretch()
        layout.addLayout(title_box)
        layout.addWidget(sub)

        # Filter & Search
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Veri belleğinde ara...")
        self.search_input.textChanged.connect(self.filter_memories)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Tüm Kategoriler", "Genel", "Kişisel", "Tercihler", "İş/Okul"])
        self.cat_combo.currentTextChanged.connect(self.filter_memories)

        add_btn = QPushButton("➕ Yeni Veri Ekle")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #99000f, stop:1 #ff1a26);
                color: #ffffff;
                border: 1px solid #ff4d58;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b80012, stop:1 #ff4d58);
            }
        """)
        add_btn.clicked.connect(self.show_add_dialog)

        bar.addWidget(self.search_input, 2)
        bar.addWidget(self.cat_combo, 1)
        bar.addWidget(add_btn)
        layout.addLayout(bar)

        # ScrollArea
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget, QScrollArea #qt_scrollarea_viewport { border: none; background: transparent; }")
        self.scroll.viewport().setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll, 1)

    def set_memories(self, memory_list: list):
        self.memories = memory_list
        self.render_cards(self.memories)

    def render_cards(self, memory_list: list):
        while self.cards_layout.count() > 1:
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not memory_list:
            no_data = QLabel("Veri belleğinde henüz veri bulunmuyor.")
            no_data.setStyleSheet("color: #73575c; font-size: 13px; padding: 20px;")
            self.cards_layout.insertWidget(0, no_data)
            return

        for idx, item in enumerate(memory_list):
            item_id = item.get('id', idx)
            key = item.get('key', 'Bilgi')
            val = item.get('value', '')
            cat = item.get('category', 'Genel')
            dt = item.get('date', '')

            card = MemoryItemCard(item_id, key, val, cat, dt)
            card.delete_requested.connect(self.delete_memory_signal.emit)
            self.cards_layout.insertWidget(idx, card)

    def filter_memories(self):
        query = self.search_input.text().lower()
        selected_cat = self.cat_combo.currentText()

        filtered = []
        for m in self.memories:
            k = m.get('key', '').lower()
            v = m.get('value', '').lower()
            cat = m.get('category', 'Genel')

            match_text = query in k or query in v
            match_cat = selected_cat == "Tüm Kategoriler" or cat == selected_cat

            if match_text and match_cat:
                filtered.append(m)

        self.render_cards(filtered)

    def show_add_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Hafıza Ekle")
        dialog.setFixedWidth(360)
        dialog.setStyleSheet("QDialog { background: #0c0407; }")

        d_layout = QFormLayout(dialog)
        d_layout.setContentsMargins(16, 16, 16, 16)

        key_in = QLineEdit()
        key_in.setPlaceholderText("Örn: Doğum Günü, En Sevdiği Renk")
        
        val_in = QLineEdit()
        val_in.setPlaceholderText("Örn: 15 Mayıs, Mavi")

        cat_in = QComboBox()
        cat_in.addItems(["Genel", "Kişisel", "Tercihler", "İş/Okul"])

        save_btn = QPushButton("Kaydet")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(lambda: dialog.accept())

        d_layout.addRow("Başlık/Konu:", key_in)
        d_layout.addRow("Detay/Bilgi:", val_in)
        d_layout.addRow("Kategori:", cat_in)
        d_layout.addRow("", save_btn)

        if dialog.exec_() == QDialog.Accepted:
            k = key_in.text().strip()
            v = val_in.text().strip()
            c = cat_in.currentText()
            if k and v:
                self.add_memory_signal.emit(k, v, c)
