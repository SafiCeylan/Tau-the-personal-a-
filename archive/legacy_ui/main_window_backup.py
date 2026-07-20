from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QTabWidget, QListWidget, QMessageBox, QInputDialog, QFrame, QScrollArea, QSplitter, QListWidgetItem, QDialog, QFormLayout, QDialogButtonBox, QComboBox, QSpinBox, QCheckBox, QGroupBox, QGridLayout, QProgressBar)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDateTime
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap
from datetime import datetime, timedelta
import sqlite3
import json

class ModernButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet('''
            QPushButton {
                background-color: #2d3748;
                border: 2px solid #4a5568;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a5568;
                border-color: #718096;
            }
            QPushButton:pressed {
                background-color: #1a202c;
                border-color: #2d3748;
            }
        ''')

class ModernLineEdit(QLineEdit):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet('''
            QLineEdit {
                background-color: #2d3748;
                border: 2px solid #4a5568;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 12px;
                font-size: 14px;
                selection-background-color: #4a5568;
            }
            QLineEdit:focus {
                border-color: #63b3ed;
            }
        ''')

class ModernTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet('''
            QTextEdit {
                background-color: #1a202c;
                border: 2px solid #4a5568;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 12px;
                font-size: 14px;
                selection-background-color: #4a5568;
            }
        ''')

class ReminderChecker(QThread):
    reminder_found = pyqtSignal(str, str)
    
    def __init__(self, cursor, conn):
        super().__init__()
        self.cursor = cursor
        self.conn = conn
        self.running = True
        
    def run(self):
        while self.running:
            try:
                # Vadesi gelen hatırlatmaları kontrol et
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute("""
                    SELECT metin, hedef_tarih 
                    FROM hatirlatmalar 
                    WHERE durum = 'bekliyor' AND hedef_tarih <= ?
                """, (now,))
                
                reminders = self.cursor.fetchall()
                for metin, hedef_tarih in reminders:
                    # Hatırlatmayı tamamlandı olarak işaretle
                    self.cursor.execute("""
                        UPDATE hatirlatmalar 
                        SET durum = 'tamamlandi' 
                        WHERE metin = ? AND hedef_tarih = ?
                    """, (metin, hedef_tarih))
                    self.conn.commit()
                    
                    # Sinyal gönder
                    self.reminder_found.emit(metin, hedef_tarih)
                    
            except Exception as e:
                print(f"Hatırlatma kontrolü hatası: {e}")
                
            self.msleep(10000)  # 10 saniye bekle
            
    def stop(self):
        self.running = False

class AnalysisDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analiz Ayarları")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Analiz türü seçimi
        self.analysis_type = QComboBox()
        self.analysis_type.addItems(["Haftalık Analiz", "Aylık Analiz", "Ruh Hali Trendi", "Hatırlatma İstatistikleri"])
        
        # Tarih aralığı
        self.date_range = QComboBox()
        self.date_range.addItems(["Son 7 gün", "Son 30 gün", "Son 3 ay", "Tüm zamanlar"])
        
        # Detay seviyesi
        self.detail_level = QComboBox()
        self.detail_level.addItems(["Özet", "Detaylı", "Çok Detaylı"])
        
        # Form düzeni
        form_layout = QFormLayout()
        form_layout.addRow("Analiz Türü:", self.analysis_type)
        form_layout.addRow("Tarih Aralığı:", self.date_range)
        form_layout.addRow("Detay Seviyesi:", self.detail_level)
        
        # Butonlar
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addLayout(form_layout)
        layout.addWidget(buttons)
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self, cursor, conn, cevapla_func, cevap_ogren_func):
        super().__init__()
        self.cursor = cursor
        self.conn = conn
        self.cevapla_func = cevapla_func
        self.cevap_ogren_func = cevap_ogren_func
        self.reminder_checker = ReminderChecker(cursor, conn)
        self.reminder_checker.reminder_found.connect(self.show_reminder_notification)
        self.reminder_checker.start()
        
        self.setup_ui()
        self.load_memories()
        self.load_reminders()
        
    def setup_ui(self):
        self.setWindowTitle("TAU - Kişisel Asistan")
        self.setGeometry(100, 100, 1200, 800)
        
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QHBoxLayout(central_widget)
        
        # Sol panel (Chat ve Giriş)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Chat alanı
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(400)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
        """)
        
        # Giriş alanı
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Mesajınızı yazın...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        
        # Gönder butonu
        self.send_button = QPushButton("Gönder")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.send_button.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        
        left_layout.addWidget(self.chat_display)
        left_layout.addLayout(input_layout)
        
        # Sağ panel (Sekmeler)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #3b3b3b;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
            }
            QTabBar::tab:hover {
                background-color: #555;
            }
        """)
        
        # Chat sekmesi
        self.setup_chat_tab()
        
        # Memory sekmesi
        self.setup_memory_tab()
        
        # Hatırlatmalar sekmesi
        self.setup_reminders_tab()
        
        # Analiz sekmesi
        self.setup_analysis_tab()
        
        # Ayarlar sekmesi
        self.setup_settings_tab()
        
        right_layout.addWidget(self.tab_widget)
        
        # Ana layout'a panelleri ekle
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 1)
        
        # Hoş geldin mesajı
        self.add_message("TAU", "Merhaba! Ben TAU, kişisel asistanınız. Size nasıl yardımcı olabilirim?")
        
    def setup_chat_tab(self):
        chat_tab = QWidget()
        layout = QVBoxLayout(chat_tab)
        
        # Chat istatistikleri
        stats_group = QGroupBox("Chat İstatistikleri")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        stats_layout = QGridLayout(stats_group)
        
        self.total_messages_label = QLabel("Toplam Mesaj: 0")
        self.today_messages_label = QLabel("Bugünkü Mesaj: 0")
        self.avg_response_time_label = QLabel("Ortalama Yanıt Süresi: 0s")
        
        for label in [self.total_messages_label, self.today_messages_label, self.avg_response_time_label]:
            label.setStyleSheet("color: #ffffff; padding: 5px;")
        
        stats_layout.addWidget(self.total_messages_label, 0, 0)
        stats_layout.addWidget(self.today_messages_label, 0, 1)
        stats_layout.addWidget(self.avg_response_time_label, 1, 0)
        
        layout.addWidget(stats_group)
        
        # Hızlı komutlar
        quick_commands_group = QGroupBox("Hızlı Komutlar")
        quick_commands_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        quick_layout = QVBoxLayout(quick_commands_group)
        
        commands = [
            ("📊 Analiz Raporu", "analiz raporu"),
            ("📅 Geçmiş Hatırlatmalar", "dün ne yaptım"),
            ("⏰ Hatırlatma Ayarla", "yarın sabah hatırlat"),
            ("🎓 Öğrenme Modu", "tau öğren")
        ]
        
        for text, command in commands:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #0078d4;
                }
            """)
            btn.clicked.connect(lambda checked, cmd=command: self.quick_command(cmd))
            quick_layout.addWidget(btn)
        
        layout.addWidget(quick_commands_group)
        layout.addStretch()
        
        self.tab_widget.addTab(chat_tab, "💬 Chat")
        
    def setup_memory_tab(self):
        memory_tab = QWidget()
        layout = QVBoxLayout(memory_tab)
        
        # Memory listesi
        self.memory_list = QListWidget()
        self.memory_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # Memory butonları
        memory_buttons = QHBoxLayout()
        
        self.add_memory_btn = QPushButton("➕ Yeni Memory")
        self.edit_memory_btn = QPushButton("✏️ Düzenle")
        self.delete_memory_btn = QPushButton("🗑️ Sil")
        
        for btn in [self.add_memory_btn, self.edit_memory_btn, self.delete_memory_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #0078d4;
                }
            """)
        
        self.add_memory_btn.clicked.connect(self.add_memory)
        self.edit_memory_btn.clicked.connect(self.edit_memory)
        self.delete_memory_btn.clicked.connect(self.delete_memory)
        
        memory_buttons.addWidget(self.add_memory_btn)
        memory_buttons.addWidget(self.edit_memory_btn)
        memory_buttons.addWidget(self.delete_memory_btn)
        
        layout.addWidget(self.memory_list)
        layout.addLayout(memory_buttons)
        
        self.tab_widget.addTab(memory_tab, "🧠 Memory")
        
    def setup_reminders_tab(self):
        reminders_tab = QWidget()
        layout = QVBoxLayout(reminders_tab)
        
        # Hatırlatma listesi
        self.reminder_list = QListWidget()
        self.reminder_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # Hatırlatma butonları
        reminder_buttons = QHBoxLayout()
        
        self.add_reminder_btn = QPushButton("➕ Yeni Hatırlatma")
        self.complete_reminder_btn = QPushButton("✅ Tamamla")
        self.delete_reminder_btn = QPushButton("🗑️ Sil")
        
        for btn in [self.add_reminder_btn, self.complete_reminder_btn, self.delete_reminder_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #0078d4;
                }
            """)
        
        self.add_reminder_btn.clicked.connect(self.add_reminder)
        self.complete_reminder_btn.clicked.connect(self.complete_reminder)
        self.delete_reminder_btn.clicked.connect(self.delete_reminder)
        
        reminder_buttons.addWidget(self.add_reminder_btn)
        reminder_buttons.addWidget(self.complete_reminder_btn)
        reminder_buttons.addWidget(self.delete_reminder_btn)
        
        layout.addWidget(self.reminder_list)
        layout.addLayout(reminder_buttons)
        
        self.tab_widget.addTab(reminders_tab, "⏰ Hatırlatmalar")
        
    def setup_analysis_tab(self):
        analysis_tab = QWidget()
        layout = QVBoxLayout(analysis_tab)
        
        # Analiz raporu alanı
        self.analysis_display = QTextEdit()
        self.analysis_display.setReadOnly(True)
        self.analysis_display.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
        """)
        
        # Analiz butonları
        analysis_buttons = QHBoxLayout()
        
        self.generate_analysis_btn = QPushButton("📊 Analiz Oluştur")
        self.custom_analysis_btn = QPushButton("⚙️ Özel Analiz")
        self.export_analysis_btn = QPushButton("📤 Dışa Aktar")
        
        for btn in [self.generate_analysis_btn, self.custom_analysis_btn, self.export_analysis_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #0078d4;
                }
            """)
        
        self.generate_analysis_btn.clicked.connect(self.generate_analysis)
        self.custom_analysis_btn.clicked.connect(self.custom_analysis)
        self.export_analysis_btn.clicked.connect(self.export_analysis)
        
        analysis_buttons.addWidget(self.generate_analysis_btn)
        analysis_buttons.addWidget(self.custom_analysis_btn)
        analysis_buttons.addWidget(self.export_analysis_btn)
        
        layout.addWidget(self.analysis_display)
        layout.addLayout(analysis_buttons)
        
        self.tab_widget.addTab(analysis_tab, "📊 Analiz")
        
    def setup_settings_tab(self):
        settings_tab = QWidget()
        layout = QVBoxLayout(settings_tab)
        
        # Kullanıcı bilgileri
        user_group = QGroupBox("Kullanıcı Bilgileri")
        user_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        user_layout = QFormLayout(user_group)
        
        self.name_input = QLineEdit()
        self.mood_input = QLineEdit()
        self.habits_input = QLineEdit()
        
        for input_field in [self.name_input, self.mood_input, self.habits_input]:
            input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 5px;
                }
            """)
        
        user_layout.addRow("İsim:", self.name_input)
        user_layout.addRow("Ruh Hali:", self.mood_input)
        user_layout.addRow("Alışkanlıklar:", self.habits_input)
        
        # Ayarlar
        settings_group = QGroupBox("Ayarlar")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        settings_layout = QFormLayout(settings_group)
        
        self.confidence_threshold = QSpinBox()
        self.confidence_threshold.setRange(0, 100)
        self.confidence_threshold.setValue(80)
        self.confidence_threshold.setStyleSheet("""
            QSpinBox {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        self.auto_save = QCheckBox("Otomatik Kaydet")
        self.auto_save.setChecked(True)
        self.auto_save.setStyleSheet("color: #ffffff;")
        
        self.notifications = QCheckBox("Bildirimler")
        self.notifications.setChecked(True)
        self.notifications.setStyleSheet("color: #ffffff;")
        
        settings_layout.addRow("Güven Eşiği (%):", self.confidence_threshold)
        settings_layout.addRow(self.auto_save)
        settings_layout.addRow(self.notifications)
        
        # Kaydet butonu
        save_btn = QPushButton("💾 Ayarları Kaydet")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        
        layout.addWidget(user_group)
        layout.addWidget(settings_group)
        layout.addWidget(save_btn)
        layout.addStretch()
        
        self.tab_widget.addTab(settings_tab, "⚙️ Ayarlar")
        
        # Kullanıcı verilerini yükle
        self.load_user_data()
        
    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return
            
        # Kullanıcı mesajını göster
        self.add_message("Sen", message)
        self.input_field.clear()
        
        # TAU'nun yanıtını al
        try:
            response, confidence = self.cevapla_func(self.cursor, message)
            self.add_message("TAU", response)
        except Exception as e:
            self.add_message("TAU", f"Bir hata oluştu: {e}")
            
    def add_message(self, sender, message):
        timestamp = datetime.now().strftime("%H:%M")
        formatted_message = f"[{timestamp}] <b>{sender}:</b> {message}<br><br>"
        
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(formatted_message)
        
        # Otomatik scroll
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )
        
    def quick_command(self, command):
        self.input_field.setText(command)
        self.send_message()
        
    def load_memories(self):
        try:
            self.cursor.execute("SELECT key, value FROM memory ORDER BY created_at DESC")
            memories = self.cursor.fetchall()
            
            self.memory_list.clear()
            for key, value in memories:
                item = QListWidgetItem(f"{key}: {value[:50]}...")
                item.setData(Qt.UserRole, (key, value))
                self.memory_list.addItem(item)
        except Exception as e:
            print(f"Memory yüklenirken hata: {e}")
            
    def add_memory(self):
        key, ok = QInputDialog.getText(self, "Yeni Memory", "Anahtar:")
        if ok and key:
            value, ok = QInputDialog.getText(self, "Yeni Memory", "Değer:")
            if ok and value:
                try:
                    self.cursor.execute("INSERT INTO memory (key, value) VALUES (?, ?)", (key, value))
                    self.conn.commit()
                    self.load_memories()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Memory eklenirken hata: {e}")
                    
    def edit_memory(self):
        current_item = self.memory_list.currentItem()
        if current_item:
            key, value = current_item.data(Qt.UserRole)
            new_value, ok = QInputDialog.getText(self, "Memory Düzenle", "Yeni değer:", text=value)
            if ok and new_value:
                try:
                    self.cursor.execute("UPDATE memory SET value = ? WHERE key = ?", (new_value, key))
                    self.conn.commit()
                    self.load_memories()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Memory düzenlenirken hata: {e}")
                    
    def delete_memory(self):
        current_item = self.memory_list.currentItem()
        if current_item:
            key, value = current_item.data(Qt.UserRole)
            reply = QMessageBox.question(self, "Onay", f"'{key}' memory'sini silmek istediğinizden emin misiniz?")
            if reply == QMessageBox.Yes:
                try:
                    self.cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
                    self.conn.commit()
                    self.load_memories()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Memory silinirken hata: {e}")
                    
    def load_reminders(self):
        try:
            self.cursor.execute("""
                SELECT metin, hedef_tarih, durum 
                FROM hatirlatmalar 
                ORDER BY hedef_tarih ASC
            """)
            reminders = self.cursor.fetchall()
            
            self.reminder_list.clear()
            for metin, hedef_tarih, durum in reminders:
                status_emoji = "✅" if durum == "tamamlandi" else "⏰"
                item = QListWidgetItem(f"{status_emoji} {metin} ({hedef_tarih})")
                item.setData(Qt.UserRole, (metin, hedef_tarih, durum))
                self.reminder_list.addItem(item)
        except Exception as e:
            print(f"Hatırlatmalar yüklenirken hata: {e}")
            
    def add_reminder(self):
        metin, ok = QInputDialog.getText(self, "Yeni Hatırlatma", "Hatırlatma metni:")
        if ok and metin:
            # Basit tarih seçimi (gerçek uygulamada daha gelişmiş olabilir)
            tarih_str, ok = QInputDialog.getText(self, "Yeni Hatırlatma", "Tarih (YYYY-MM-DD HH:MM):")
            if ok and tarih_str:
                try:
                    self.cursor.execute("""
                        INSERT INTO hatirlatmalar (metin, hedef_tarih, durum)
                        VALUES (?, ?, 'bekliyor')
                    """, (metin, tarih_str))
                    self.conn.commit()
                    self.load_reminders()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Hatırlatma eklenirken hata: {e}")
                    
    def complete_reminder(self):
        current_item = self.reminder_list.currentItem()
        if current_item:
            metin, hedef_tarih, durum = current_item.data(Qt.UserRole)
            if durum == "bekliyor":
                try:
                    self.cursor.execute("""
                        UPDATE hatirlatmalar 
                        SET durum = 'tamamlandi' 
                        WHERE metin = ? AND hedef_tarih = ?
                    """, (metin, hedef_tarih))
                    self.conn.commit()
                    self.load_reminders()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Hatırlatma güncellenirken hata: {e}")
                    
    def delete_reminder(self):
        current_item = self.reminder_list.currentItem()
        if current_item:
            metin, hedef_tarih, durum = current_item.data(Qt.UserRole)
            reply = QMessageBox.question(self, "Onay", f"Bu hatırlatmayı silmek istediğinizden emin misiniz?")
            if reply == QMessageBox.Yes:
                try:
                    self.cursor.execute("""
                        DELETE FROM hatirlatmalar 
                        WHERE metin = ? AND hedef_tarih = ?
                    """, (metin, hedef_tarih))
                    self.conn.commit()
                    self.load_reminders()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Hatırlatma silinirken hata: {e}")
                    
    def show_reminder_notification(self, metin, hedef_tarih):
        self.add_message("TAU", f"⏰ **HATIRLATMA:** {metin}")
        
    def generate_analysis(self):
        try:
            # Ruh hali analizi
            self.cursor.execute("""
                SELECT ruh_hali, COUNT(*) as sayi
                FROM ruh_hali_gecmisi
                WHERE tarih >= datetime('now', '-7 days')
                GROUP BY ruh_hali
            """)
            ruh_hali_istatistikleri = self.cursor.fetchall()
            
            # Memory analizi
            self.cursor.execute("SELECT COUNT(*) FROM memory")
            memory_count = self.cursor.fetchone()[0]
            
            # Hatırlatma analizi
            self.cursor.execute("SELECT COUNT(*) FROM hatirlatmalar WHERE durum = 'bekliyor'")
            active_reminders = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM hatirlatmalar WHERE durum = 'tamamlandi'")
            completed_reminders = self.cursor.fetchone()[0]
            
            # Son 7 günün hatırlatmalarını al
            self.cursor.execute("""
                SELECT COUNT(*) as toplam_hatirlatma
                FROM hatirlatmalar
                WHERE olusturma_tarihi >= datetime('now', '-7 days')
            """)
            haftalik_hatirlatma = self.cursor.fetchone()[0]
            
            analysis_text = f"""
📊 **Bu Haftanın Kişisel Analiz Raporu**

😊 **Ruh Hali Analizi:**
"""
            
            if ruh_hali_istatistikleri:
                for ruh_hali, sayi in ruh_hali_istatistikleri:
                    emoji = "😊" if ruh_hali == "pozitif" else "😔" if ruh_hali == "negatif" else "😐"
                    analysis_text += f"   {emoji} {ruh_hali.title()}: {sayi} kez\n"
                
                # En yaygın ruh hali
                en_yaygin = max(ruh_hali_istatistikleri, key=lambda x: x[1])
                if en_yaygin[1] > 2:
                    if en_yaygin[0] == "negatif":
                        analysis_text += f"\n⚠️ **Farkındalık:** Bu hafta {en_yaygin[1]} kez moralin düşük görünüyordu. Belki biraz dinlenmeye ihtiyacın var?\n"
                    elif en_yaygin[0] == "pozitif":
                        analysis_text += f"\n🎉 **Harika!** Bu hafta {en_yaygin[1]} kez çok pozitif görünüyordun. Bu enerjiyi koru!\n"
            else:
                analysis_text += "   Henüz yeterli veri yok.\n"
            
            analysis_text += f"""

⏰ **Hatırlatma İstatistikleri:**
   • Bu hafta oluşturulan: {haftalik_hatirlatma}
   • Aktif hatırlatmalar: {active_reminders}
   • Tamamlanan hatırlatmalar: {completed_reminders}
   • Tamamlanma oranı: %{(completed_reminders/(completed_reminders+active_reminders)*100) if (completed_reminders+active_reminders) > 0 else 0:.1f}

🧠 **Memory Durumu:**
   • Toplam Memory: {memory_count}

💡 **Öneriler:**
"""
            
            if haftalik_hatirlatma > 5:
                analysis_text += "   • Çok fazla hatırlatman var. Belki daha az ama önemli şeylere odaklanabilirsin.\n"
            elif haftalik_hatirlatma == 0:
                analysis_text += "   • Hiç hatırlatman yok. Belki önemli şeyleri not almayı deneyebilirsin.\n"
            
            if memory_count > 10:
                analysis_text += "   • Memory sayın yüksek. Düzenli temizlik yapmayı düşünebilirsin.\n"
            elif memory_count < 3:
                analysis_text += "   • Memory sayın düşük. Daha fazla bilgi kaydetmeyi deneyebilirsin.\n"
            
            analysis_text += f"""

🔄 **Son Güncelleme:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            self.analysis_display.setPlainText(analysis_text)
            
        except Exception as e:
            self.analysis_display.setPlainText(f"Analiz oluşturulurken hata: {e}")
            
    def custom_analysis(self):
        dialog = AnalysisDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Özel analiz mantığı burada olacak
            self.analysis_display.setPlainText("Özel analiz özelliği geliştiriliyor...")
            
    def export_analysis(self):
        try:
            analysis_text = self.analysis_display.toPlainText()
            if analysis_text:
                filename = f"analiz_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(analysis_text)
                QMessageBox.information(self, "Başarılı", f"Analiz raporu {filename} dosyasına kaydedildi.")
            else:
                QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak analiz bulunamadı.")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Dışa aktarma hatası: {e}")
            
    def load_user_data(self):
        try:
            with open('user_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.name_input.setText(data.get('name', ''))
                self.mood_input.setText(data.get('mood', ''))
                self.habits_input.setText(data.get('habits', ''))
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Kullanıcı verisi yüklenirken hata: {e}")
            
    def save_settings(self):
        try:
            # Kullanıcı verilerini kaydet
            user_data = {
                'name': self.name_input.text(),
                'mood': self.mood_input.text(),
                'habits': self.habits_input.text(),
                'confidence_threshold': self.confidence_threshold.value(),
                'auto_save': self.auto_save.isChecked(),
                'notifications': self.notifications.isChecked()
            }
            
            with open('user_data.json', 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
                
            QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi!")
            
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Ayarlar kaydedilirken hata: {e}")
            
    def closeEvent(self, event):
        self.reminder_checker.stop()
        self.reminder_checker.wait()
        event.accept() 