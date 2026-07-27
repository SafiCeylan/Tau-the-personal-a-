from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QCheckBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

class ReminderItemCard(QFrame):
    toggle_complete = pyqtSignal(int, bool)
    delete_requested = pyqtSignal(int)

    def __init__(self, rem_id: int, text: str, time_str: str, is_completed: bool = False, parent=None):
        super().__init__(parent)
        self.rem_id = rem_id
        self.text = text
        self.time_str = time_str
        self.is_completed = is_completed
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: rgba(22, 6, 10, 0.92);
                border: 1px solid rgba(255, 26, 38, 0.3);
                border-radius: 10px;
                padding: 4px;
            }
            QFrame:hover {
                border-color: rgba(255, 26, 38, 0.6);
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Complete Checkbox
        self.chk = QCheckBox()
        self.chk.setChecked(self.is_completed)
        self.chk.toggled.connect(lambda checked: self.toggle_complete.emit(self.rem_id, checked))

        # Text & Time
        content_box = QVBoxLayout()
        content_box.setSpacing(2)

        txt_lbl = QLabel(self.text)
        if self.is_completed:
            txt_lbl.setStyleSheet("color: #5f6368; font-size: 13px; text-decoration: line-through;")
        else:
            txt_lbl.setStyleSheet("color: #f0f2f5; font-size: 13px; font-weight: 600;")

        time_lbl = QLabel(f"⏰ {self.time_str}")
        time_lbl.setStyleSheet("color: #ff4d58; font-size: 11px;")

        content_box.addWidget(txt_lbl)
        content_box.addWidget(time_lbl)

        # Delete Button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #5f6368;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff5555;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.rem_id))

        layout.addWidget(self.chk)
        layout.addLayout(content_box, 1)
        layout.addWidget(del_btn)


class RemindersViewWidget(QWidget):
    add_reminder_signal = pyqtSignal(str) # natural language input
    toggle_complete_signal = pyqtSignal(int, bool)
    delete_reminder_signal = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.reminders = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        
        head = QLabel("⏰ Hatırlatıcı Paneli")
        head.setStyleSheet("color: #ff4d58; font-size: 20px; font-weight: 800;")
        
        sub = QLabel("Doğal dille yazılan hatırlatmaları algılar ve zamanı geldiğinde sizi uyarır")
        sub.setStyleSheet("color: #a68c90; font-size: 12px;")

        title_box.addWidget(head)
        title_box.addWidget(sub)
        layout.addLayout(title_box)

        # Add Input Bar
        add_box = QHBoxLayout()
        self.rem_input = QLineEdit()
        self.rem_input.setPlaceholderText("Örn: Yarın saat 14:00'te online toplantıya katıl")
        self.rem_input.returnPressed.connect(self._on_add_clicked)

        add_btn = QPushButton("➕ Ekle")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #99000f, stop:1 #ff1a26);
                color: #ffffff;
                border: 1px solid #ff4d58;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b80012, stop:1 #ff4d58);
            }
        """)
        add_btn.clicked.connect(self._on_add_clicked)

        add_box.addWidget(self.rem_input, 1)
        add_box.addWidget(add_btn)
        layout.addLayout(add_box)

        # Scroll Area
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

    def _on_add_clicked(self):
        text = self.rem_input.text().strip()
        if text:
            self.add_reminder_signal.emit(text)
            self.rem_input.clear()

    def set_reminders(self, reminder_list: list):
        self.reminders = reminder_list
        
        while self.cards_layout.count() > 1:
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not reminder_list:
            no_data = QLabel("Aktif hatırlatma bulunmuyor. Yeni bir hatırlatma ekleyin!")
            no_data.setStyleSheet("color: #73575c; font-size: 13px; padding: 20px;")
            self.cards_layout.insertWidget(0, no_data)
            return

        for idx, item in enumerate(reminder_list):
            rem_id = item.get('id', idx)
            txt = item.get('text', '')
            tm = item.get('time', '')
            comp = item.get('completed', False)

            card = ReminderItemCard(rem_id, txt, tm, comp)
            card.toggle_complete.connect(self.toggle_complete_signal.emit)
            card.delete_requested.connect(self.delete_reminder_signal.emit)
            self.cards_layout.insertWidget(idx, card)
