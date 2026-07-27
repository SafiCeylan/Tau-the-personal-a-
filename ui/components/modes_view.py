import json
import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QDialog, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal


class ModeEditorDialog(QDialog):
    """Yeni Mod Ekleme veya Düzenleme Penceresi"""
    def __init__(self, db_manager, mode_data=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.mode_data = mode_data
        self.actions = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Mod Editörü — ULTRON Core")
        self.resize(480, 520)
        self.setStyleSheet("""
            QDialog {
                background: #0e0305;
                color: #ffffff;
                font-family: Consolas, sans-serif;
            }
            QLabel {
                color: #ff4d58;
                font-weight: bold;
                font-size: 12px;
            }
            QLineEdit, QTextEdit {
                background: rgba(30, 8, 12, 0.9);
                border: 1px solid rgba(255, 26, 38, 0.5);
                border-radius: 6px;
                color: #ffffff;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #ff1a26;
            }
            QPushButton {
                background: #ff1a26;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ff4d58;
            }
            QListWidget {
                background: rgba(20, 5, 8, 0.9);
                border: 1px solid rgba(255, 26, 38, 0.3);
                border-radius: 6px;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title_lbl = QLabel("🎛️ YENİ OTONOM MOD / RUTİN OLUŞTUR")
        title_lbl.setStyleSheet("font-size: 15px; color: #ff1a26; font-weight: 900; letter-spacing: 1px;")
        layout.addWidget(title_lbl)

        # Mode Name
        layout.addWidget(QLabel("Mod Adı:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Yazılım Modu, Yayıncı Modu")
        layout.addWidget(self.name_input)

        # Trigger Keyword
        layout.addWidget(QLabel("Tetikleyici Anahtar Kelime (Yazıldığı an başlatılır):"))
        self.trigger_input = QLineEdit()
        self.trigger_input.setPlaceholderText("Örn: yazılım modunu başlat, yayın modu")
        layout.addWidget(self.trigger_input)

        # Description
        layout.addWidget(QLabel("Açıklama:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Örn: VS Code açar, sesi %30 yapar")
        layout.addWidget(self.desc_input)

        # Actions Steps Section
        layout.addWidget(QLabel("Otonom Aksiyon Adımları:"))
        step_input_layout = QHBoxLayout()
        self.step_input = QLineEdit()
        self.step_input.setPlaceholderText("Örn: sesi %40 yap, chrome aç")
        add_step_btn = QPushButton("➕ Adım Ekle")
        add_step_btn.clicked.connect(self._add_step)
        step_input_layout.addWidget(self.step_input)
        step_input_layout.addWidget(add_step_btn)
        layout.addLayout(step_input_layout)

        self.steps_list = QListWidget()
        layout.addWidget(self.steps_list)

        # Pre-fill data if editing
        if self.mode_data:
            self.name_input.setText(self.mode_data.get('name', ''))
            self.trigger_input.setText(self.mode_data.get('trigger_keyword', ''))
            self.desc_input.setText(self.mode_data.get('description', ''))
            try:
                actions_arr = json.loads(self.mode_data.get('actions_json', '[]'))
                for act in actions_arr:
                    self.actions.append(act)
                    self.steps_list.addItem(f"⚙️ {act}")
            except Exception:
                pass

        # Save & Cancel Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 MODU KAYDET")
        save_btn.clicked.connect(self._save_mode)
        cancel_btn = QPushButton("❌ İptal")
        cancel_btn.setStyleSheet("background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _add_step(self):
        text = self.step_input.text().strip()
        if text:
            self.actions.append(text)
            self.steps_list.addItem(f"⚙️ {text}")
            self.step_input.clear()

    def _save_mode(self):
        name = self.name_input.text().strip()
        trigger = self.trigger_input.text().strip()
        desc = self.desc_input.text().strip()

        if not name or not trigger or not self.actions:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen Mod Adı, Tetikleyici Kelime ve en az 1 Aksiyon Adımı ekleyiniz.")
            return

        actions_json = json.dumps(self.actions, ensure_ascii=False)

        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            if self.mode_data and self.mode_data.get('id'):
                cursor.execute(
                    "UPDATE custom_routines SET name=?, trigger_keyword=?, description=?, actions_json=? WHERE id=?",
                    (name, trigger, desc, actions_json, self.mode_data['id'])
                )
            else:
                cursor.execute(
                    "INSERT INTO custom_routines (name, trigger_keyword, description, actions_json) VALUES (?, ?, ?, ?)",
                    (name, trigger, desc, actions_json)
                )

            conn.commit()
            self.accept()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Çakışan Kelime", f"'{trigger}' tetikleyici kelimesi zaten başka bir modda kullanılıyor!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Mod kaydedilirken hata oluştu: {e}")


class ModesViewWidget(QWidget):
    """Ultron Mod & Rutin Yöneticisi Ekranı"""
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.init_ui()
        self.load_modes()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Top Action Bar (Use '&&' so Qt does not render underline mnemonic!)
        top_bar = QHBoxLayout()
        
        title_lbl = QLabel("🎛️ ULTRON MOD && RUTİN YÖNETİCİSİ")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 900; color: #ff1a26; letter-spacing: 1.5px;")
        top_bar.addWidget(title_lbl)
        top_bar.addStretch()

        add_mode_btn = QPushButton("➕ YENİ MOD EKLE")
        add_mode_btn.setCursor(Qt.PointingHandCursor)
        add_mode_btn.setStyleSheet("""
            QPushButton {
                background: #ff1a26;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #ff4d58;
            }
        """)
        add_mode_btn.clicked.connect(self._open_add_dialog)
        top_bar.addWidget(add_mode_btn)

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
            }
        """)
        refresh_btn.clicked.connect(self.load_modes)
        top_bar.addWidget(refresh_btn)

        layout.addLayout(top_bar)

        # Scroll Area for Mode Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea, QScrollArea > QWidget, QScrollArea #qt_scrollarea_viewport {
                background: transparent;
                border: none;
            }
        """)
        self.scroll_area.viewport().setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(14)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)

    def load_modes(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Built-in Default Modes
        default_modes = [
            {
                'id': None,
                'name': 'Çalışma Modu',
                'trigger_keyword': 'çalışma modunu başlat',
                'description': 'Sesi %40 yapar, Chrome açar, sistem durumunu raporlar.',
                'actions_json': '["sesi %40 yap", "chrome aç", "sistem durumunu göster"]'
            },
            {
                'id': None,
                'name': 'Oyun Modu',
                'trigger_keyword': 'oyun modu',
                'description': 'Sesi %70 yapar, donanım telemetrisini raporlar.',
                'actions_json': '["sesi %70 yap", "sistem durumu"]'
            },
            {
                'id': None,
                'name': 'Dinlenme Modu',
                'trigger_keyword': 'dinlenme modu',
                'description': 'Sesi %35 yapar, YouTube Music chill beats başlatır.',
                'actions_json': '["sesi %35 yap", "youtube music chill beats çal"]'
            }
        ]

        for m in default_modes:
            self._render_mode_card(m, is_builtin=True)

        # Load Custom Modes from Database
        if self.db:
            try:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, trigger_keyword, description, actions_json FROM custom_routines ORDER BY id DESC")
                rows = cursor.fetchall()
                for row in rows:
                    m = dict(row)
                    self._render_mode_card(m, is_builtin=False)
            except Exception as e:
                print(f"[ModesView Load Error]: {e}")

    def _render_mode_card(self, mode_data: dict, is_builtin: bool = False):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(22, 6, 10, 0.92);
                border: 1px solid rgba(255, 26, 38, 0.4);
                border-radius: 12px;
                padding: 14px;
            }
            QFrame:hover {
                border-color: #ff1a26;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # Card Title & Trigger Keyword Badge
        header_layout = QHBoxLayout()
        
        name_lbl = QLabel(f"⚡ {mode_data['name']}")
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        header_layout.addWidget(name_lbl)

        trigger_badge = QLabel(f"🔑 Tetikleyici: \"{mode_data['trigger_keyword']}\"")
        trigger_badge.setStyleSheet("""
            background: rgba(255, 26, 38, 0.2);
            color: #ff4d58;
            border: 1px solid rgba(255, 26, 38, 0.5);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_layout.addWidget(trigger_badge)
        header_layout.addStretch()

        if not is_builtin:
            del_btn = QPushButton("🗑️ Sil")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 0, 0, 0.2);
                    color: #ff4d58;
                    border: 1px solid #ff4d58;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #ff1a26;
                    color: #ffffff;
                }
            """)
            del_btn.clicked.connect(lambda _, mid=mode_data['id']: self._delete_mode(mid))
            header_layout.addWidget(del_btn)

        layout.addLayout(header_layout)

        # Description
        if mode_data.get('description'):
            desc_lbl = QLabel(mode_data['description'])
            desc_lbl.setStyleSheet("color: #a68c90; font-size: 12px;")
            layout.addWidget(desc_lbl)

        # Steps Badges
        try:
            steps = json.loads(mode_data.get('actions_json', '[]'))
            steps_layout = QHBoxLayout()
            steps_layout.setSpacing(6)

            for idx, stp in enumerate(steps, 1):
                step_lbl = QLabel(f"{idx}. {stp}")
                step_lbl.setStyleSheet("""
                    background: rgba(255, 255, 255, 0.08);
                    color: #e0d0d2;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-family: Consolas, sans-serif;
                """)
                steps_layout.addWidget(step_lbl)

            steps_layout.addStretch()
            layout.addLayout(steps_layout)
        except Exception:
            pass

        count = self.cards_layout.count()
        self.cards_layout.insertWidget(count - 1, card)

    def _open_add_dialog(self):
        dlg = ModeEditorDialog(self.db, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_modes()

    def _delete_mode(self, mode_id: int):
        reply = QMessageBox.question(
            self, "Modu Sil",
            "Bu modu silmek istediğinizden emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes and self.db:
            try:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM custom_routines WHERE id=?", (mode_id,))
                conn.commit()
                self.load_modes()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Mod silinirken hata oluştu: {e}")
