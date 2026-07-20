import sys
import html
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QLineEdit, QPushButton, QLabel, QTabWidget, 
                             QScrollArea, QFrame, QSplitter, QListWidget,
                             QListWidgetItem, QMessageBox, QInputDialog, QDialog,
                             QFormLayout, QDialogButtonBox, QComboBox, QSpinBox,
                             QCheckBox, QGroupBox, QGridLayout, QProgressBar)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDateTime, QSize
import os
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QLinearGradient
import sqlite3
from datetime import datetime, timedelta
import json
from features.speech import dinle_ve_yaziya_cevir, text_to_speech
# Online/gemini support removed — keep offline-only behavior


class ReminderChecker(QThread):
    reminder_found = pyqtSignal(str, str)
    
    def __init__(self, db_path='bilgiler.db'):
        super().__init__()
        self.db_path = db_path
        self.running = True
        
    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        while self.running:
            try:
                # Vadesi gelen hatırlatmaları kontrol et
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    SELECT metin, hedef_tarih 
                    FROM hatirlatmalar 
                    WHERE durum = 'bekliyor' AND hedef_tarih <= ?
                """, (now,))
                
                reminders = cursor.fetchall()
                for metin, hedef_tarih in reminders:
                    # Hatırlatmayı tamamlandı olarak işaretle
                    cursor.execute("""
                        UPDATE hatirlatmalar 
                        SET durum = 'tamamlandi' 
                        WHERE metin = ? AND hedef_tarih = ?
                    """, (metin, hedef_tarih))
                    conn.commit()
                    
                    # Sinyal gönder
                    self.reminder_found.emit(metin, hedef_tarih)
                    
            except Exception as e:
                print(f"Hatırlatma kontrolü hatası: {e}")
                
            self.msleep(10000)  # 10 saniye bekle
            
        conn.close()
            
    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    def __init__(self, cursor, conn, cevapla_func, cevap_ogren_func):
        super().__init__()
        self.cursor = cursor
        self.conn = conn
        self.cevapla_func = cevapla_func
        self.cevap_ogren_func = cevap_ogren_func
        
        
        self.reminder_checker = ReminderChecker()
        self.reminder_checker.reminder_found.connect(self.show_reminder_notification)
        self.reminder_checker.start()
        self.last_api_call = 0  # Rate limit için zaman sakla
        
        self.setup_ui()
        # Set application/window icon from local ui/icons if available
        try:
            icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
            app_icon_path = os.path.join(icons_dir, 'icon-app.svg')
            if os.path.exists(app_icon_path):
                self.setWindowIcon(QIcon(app_icon_path))
        except Exception:
            pass
        self.load_memories()
        self.load_reminders()
        
    def setup_ui(self):
        self.setWindowTitle("TAU - Kişisel Asistan")
        self.setGeometry(100, 100, 1400, 900)
        
        # Modern koyu arka plan
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #232526, stop:1 #414345);
            }
        """)
        
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Sol panel (Chat ve Giriş)
        left_panel = QWidget()
        left_panel.setStyleSheet("""
            QWidget {
                background: rgba(34, 40, 49, 0.98);
                border-radius: 15px;
                border: 1px solid #232931;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(20, 20, 20, 20)
        
        # Başlık (ikon + metin)
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)

        title_icon = QLabel()
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'icon-app.svg')
            pix = QPixmap(icon_path)
            title_icon.setPixmap(pix.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            title_icon.setText('V')
            title_icon.setStyleSheet('color: #f5f6fa; font-weight: bold; font-size: 20px;')

        title_text = QLabel('Tau Chat')
        title_text.setStyleSheet("""
            QLabel {
                color: #f5f6fa;
                font-size: 24px;
                font-weight: bold;
                padding: 10px 0;
                border-bottom: 2px solid #393e46;
            }
        """)

        title_layout.addWidget(title_icon)
        title_layout.addWidget(title_text)
        left_layout.addWidget(title_container)
        
        # Chat alanı
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(500)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: #232931;
                color: #f5f6fa;
                border: 2px solid #393e46;
                border-radius: 12px;
                padding: 15px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 2px solid #00adb5;
            }
            QScrollBar:vertical {
                background: #393e46;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #222831;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00adb5;
            }
        """)
        left_layout.addWidget(self.chat_display)
        
        # Giriş alanı + Gönder + Toggle (yeni yatay düzen)
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setSpacing(10)
        input_layout.setContentsMargins(15, 15, 15, 15)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Mesajınızı yazın...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #f5f6fa;
                border: none;
                font-size: 14px;
                padding: 8px 0;
            }
            QLineEdit:focus {
                outline: none;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)

        # Mikrofon (sesli komut) butonu
        self.mic_button = QPushButton()
        try:
            mic_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'mic.svg'))
            self.mic_button.setIcon(mic_icon)
            self.mic_button.setIconSize(QSize(20, 20))
        except Exception:
            self.mic_button.setText("Mic")
        self.mic_button.setFixedSize(40, 40)
        self.mic_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #393e46, stop:1 #00adb5);
                color: #f5f6fa;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00adb5, stop:1 #393e46);
            }
        """)
        self.mic_button.clicked.connect(self.handle_voice_command)
        
        self.send_button = QPushButton()
        try:
            send_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'send.svg'))
            self.send_button.setIcon(send_icon)
            self.send_button.setIconSize(QSize(20, 20))
        except Exception:
            self.send_button.setText("📤")
        self.send_button.setFixedSize(40, 40)
        self.send_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00adb5, stop:1 #393e46);
                color: #f5f6fa;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #393e46, stop:1 #00adb5);
            }
        """)
        self.send_button.clicked.connect(self.send_message)
        
        # iPhone tarzı toggle (Offline/Online)
        self.mode_toggle = QCheckBox()
        self.mode_toggle.setChecked(False)
        self.mode_toggle.setStyleSheet("""
            QCheckBox::indicator {
                width: 50px;
                height: 28px;
            }
            QCheckBox {
                font-size: 14px;
                font-weight: bold;
                color: #f5f6fa;
            }
        """)
        self.mode_toggle.stateChanged.connect(self.update_mode_label)
        offline_label = QLabel("Offline")
        offline_label.setStyleSheet("font-size: 13px; color: #888; margin-right: 4px;")
        online_label = QLabel("Online")
        online_label.setStyleSheet("font-size: 13px; color: #00adb5; margin-left: 4px;")
        
        input_layout.addWidget(self.input_field, 4)
        input_layout.addWidget(self.send_button, 0)
        input_layout.addWidget(self.mic_button, 0)
        input_layout.addWidget(offline_label, 0)
        input_layout.addWidget(self.mode_toggle, 0)
        input_layout.addWidget(online_label, 0)
        
        input_container.setStyleSheet("""
            QWidget {
                background: #232931;
                border-radius: 12px;
                border: 2px solid #393e46;
            }
        """)
        left_layout.addWidget(input_container)
        
        # Sağ panel (Sekmeler)
        right_panel = QWidget()
        right_panel.setStyleSheet("""
            QWidget {
                background: rgba(34, 40, 49, 0.98);
                border-radius: 15px;
                border: 1px solid #232931;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)
        right_layout.setContentsMargins(20, 20, 20, 20)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: #232931;
                color: #f5f6fa;
                padding: 12px 20px;
                margin-right: 5px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00adb5, stop:1 #393e46);
                color: #f5f6fa;
            }
            QTabBar::tab:hover:!selected {
                background: #393e46;
            }
        """)
        
        # Chat sekmesi
        self.setup_chat_tab()
        
        # Memory sekmesi
        self.setup_memory_tab()
        
        # Hatırlatmalar sekmesi
        self.setup_reminders_tab()
        
        # Ayarlar sekmesi
        self.setup_settings_tab()
        
        right_layout.addWidget(self.tab_widget)
        
        # Ana layout'a panelleri ekle
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 1)
        
        # Hoş geldin mesajı
        self.add_message("TAU", "Merhaba! Ben TAU, kişisel asistanınız. Size nasıl yardımcı olabilirim? 😊")
        
    def setup_chat_tab(self):
        chat_tab = QWidget()
        layout = QVBoxLayout(chat_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Chat istatistikleri
        stats_group = QGroupBox("Chat İstatistikleri")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background: rgba(255, 255, 255, 0.8);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                font-size: 14px;
            }
        """)
        
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(10)
        
        # Basit metin etiketleri (emoji yerine düz metin)
        self.total_messages_label = QLabel("Toplam Mesaj: 0")
        self.today_messages_label = QLabel("Bugünkü Mesaj: 0")
        self.avg_response_time_label = QLabel("Ortalama Yanıt Süresi: 0s")
        
        for label in [self.total_messages_label, self.today_messages_label, self.avg_response_time_label]:
            label.setStyleSheet("""
                color: #2c3e50; 
                padding: 8px; 
                background: rgba(236, 240, 241, 0.5);
                border-radius: 8px;
                font-size: 12px;
            """)
        
        stats_layout.addWidget(self.total_messages_label, 0, 0)
        stats_layout.addWidget(self.today_messages_label, 0, 1)
        stats_layout.addWidget(self.avg_response_time_label, 1, 0)
        
        layout.addWidget(stats_group)
        
        # Hızlı komutlar
        quick_commands_group = QGroupBox("Hızlı Komutlar")
        quick_commands_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background: rgba(255, 255, 255, 0.8);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                font-size: 14px;
            }
        """)
        
        quick_layout = QVBoxLayout(quick_commands_group)
        quick_layout.setSpacing(8)
        
        commands = [
            ("Analiz Raporu", "analiz raporu"),
            ("Geçmiş Hatırlatmalar", "dün ne yaptım"),
            ("Hatırlatma Ayarla", "yarın sabah hatırlat"),
            ("Öğrenme Modu", "tau öğren")
        ]
        
        for text, command in commands:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ecf0f1, stop:1 #bdc3c7);
                    color: #2c3e50;
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3498db, stop:1 #2980b9);
                    color: white;
                    border: 1px solid #2980b9;
                }
            """)
            btn.clicked.connect(lambda checked, cmd=command: self.quick_command(cmd))
            quick_layout.addWidget(btn)
        
        layout.addWidget(quick_commands_group)
        layout.addStretch()
        
        # Tab icon (chat)
        try:
            chat_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'send.svg'))
            self.tab_widget.addTab(chat_tab, chat_icon, "Chat")
        except Exception:
            self.tab_widget.addTab(chat_tab, "Chat")
        
    def setup_memory_tab(self):
        memory_tab = QWidget()
        layout = QVBoxLayout(memory_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Memory listesi
        self.memory_list = QListWidget()
        self.memory_list.setStyleSheet("""
            QListWidget {
                background: rgba(255, 255, 255, 0.8);
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 10px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px;
                margin: 2px;
                border-radius: 8px;
                background: rgba(236, 240, 241, 0.5);
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: 1px solid #2980b9;
            }
            QListWidget::item:hover:!selected {
                background: rgba(52, 152, 219, 0.2);
                border: 1px solid #3498db;
            }
        """)
        
        # Memory butonları
        memory_buttons = QHBoxLayout()
        memory_buttons.setSpacing(10)
        
        self.add_memory_btn = QPushButton("Yeni Memory")
        try:
            add_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'add.svg'))
            self.add_memory_btn.setIcon(add_icon)
            self.add_memory_btn.setIconSize(QSize(18, 18))
        except Exception:
            self.add_memory_btn.setText("Yeni Memory")

        self.edit_memory_btn = QPushButton("Düzenle")
        try:
            edit_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'edit.svg'))
            self.edit_memory_btn.setIcon(edit_icon)
            self.edit_memory_btn.setIconSize(QSize(18, 18))
        except Exception:
            self.edit_memory_btn.setText("Düzenle")

        self.delete_memory_btn = QPushButton("Sil")
        try:
            del_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'delete.svg'))
            self.delete_memory_btn.setIcon(del_icon)
            self.delete_memory_btn.setIconSize(QSize(18, 18))
        except Exception:
            self.delete_memory_btn.setText("Sil")
        
        for btn in [self.add_memory_btn, self.edit_memory_btn, self.delete_memory_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ecf0f1, stop:1 #bdc3c7);
                    color: #2c3e50;
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    padding: 10px 15px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3498db, stop:1 #2980b9);
                    color: white;
                    border: 1px solid #2980b9;
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
        
        try:
            mem_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'history.svg'))
            self.tab_widget.addTab(memory_tab, mem_icon, "Memory")
        except Exception:
            self.tab_widget.addTab(memory_tab, "Memory")
        
    def setup_reminders_tab(self):
        reminders_tab = QWidget()
        layout = QVBoxLayout(reminders_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Hatırlatma listesi
        self.reminder_list = QListWidget()
        self.reminder_list.setStyleSheet("""
            QListWidget {
                background: rgba(255, 255, 255, 0.8);
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 10px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px;
                margin: 2px;
                border-radius: 8px;
                background: rgba(236, 240, 241, 0.5);
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: 1px solid #2980b9;
            }
            QListWidget::item:hover:!selected {
                background: rgba(52, 152, 219, 0.2);
                border: 1px solid #3498db;
            }
        """)
        
        # Hatırlatma butonları
        reminder_buttons = QHBoxLayout()
        reminder_buttons.setSpacing(10)
        
        self.add_reminder_btn = QPushButton("Yeni Hatırlatma")
        try:
            add_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'add.svg'))
            self.add_reminder_btn.setIcon(add_icon)
            self.add_reminder_btn.setIconSize(QSize(18, 18))
        except Exception:
            self.add_reminder_btn.setText("Yeni Hatırlatma")

        self.complete_reminder_btn = QPushButton("Tamamla")
        try:
            save_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'save.svg'))
            self.complete_reminder_btn.setIcon(save_icon)
            self.complete_reminder_btn.setIconSize(QSize(18, 18))
        except Exception:
            self.complete_reminder_btn.setText("Tamamla")

        self.delete_reminder_btn = QPushButton("Sil")
        try:
            del_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'delete.svg'))
            self.delete_reminder_btn.setIcon(del_icon)
            self.delete_reminder_btn.setIconSize(QSize(18, 18))
        except Exception:
            self.delete_reminder_btn.setText("Sil")
        
        for btn in [self.add_reminder_btn, self.complete_reminder_btn, self.delete_reminder_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ecf0f1, stop:1 #bdc3c7);
                    color: #2c3e50;
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    padding: 10px 15px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3498db, stop:1 #2980b9);
                    color: white;
                    border: 1px solid #2980b9;
                }
            """)

        layout.addWidget(self.reminder_list)
        layout.addLayout(reminder_buttons)
        
        try:
            rem_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'history.svg'))
            self.tab_widget.addTab(reminders_tab, rem_icon, "Hatırlatmalar")
        except Exception:
            self.tab_widget.addTab(reminders_tab, "Hatırlatmalar")
        
    def setup_settings_tab(self):
        settings_tab = QWidget()
        layout = QVBoxLayout(settings_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Kullanıcı bilgileri
        user_group = QGroupBox("Kullanıcı Bilgileri")
        user_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background: rgba(255, 255, 255, 0.8);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                font-size: 14px;
            }
        """)
        
        user_layout = QFormLayout(user_group)
        user_layout.setSpacing(10)
        
        self.name_input = QLineEdit()
        self.mood_input = QLineEdit()
        self.habits_input = QLineEdit()
        
        for input_field in [self.name_input, self.mood_input, self.habits_input]:
            input_field.setStyleSheet("""
                QLineEdit {
                    background: rgba(255, 255, 255, 0.9);
                    color: #2c3e50;
                    border: 2px solid #ecf0f1;
                    border-radius: 8px;
                    padding: 10px;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 2px solid #3498db;
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
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background: rgba(255, 255, 255, 0.8);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                font-size: 14px;
            }
        """)
        
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(10)
        
        self.confidence_threshold = QSpinBox()
        self.confidence_threshold.setRange(0, 100)
        self.confidence_threshold.setValue(80)
        self.confidence_threshold.setStyleSheet("""
            QSpinBox {
                background: rgba(255, 255, 255, 0.9);
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 2px solid #3498db;
            }
        """)
        
        self.auto_save = QCheckBox("Otomatik Kaydet")
        self.auto_save.setChecked(True)
        self.auto_save.setStyleSheet("""
            QCheckBox {
                color: #2c3e50;
                font-size: 13px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border: 2px solid #3498db;
            }
        """)
        
        self.notifications = QCheckBox("Bildirimler")
        self.notifications.setChecked(True)
        self.notifications.setStyleSheet("""
            QCheckBox {
                color: #2c3e50;
                font-size: 13px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border: 2px solid #3498db;
            }
        """)
        
        settings_layout.addRow("Güven Eşiği (%):", self.confidence_threshold)
        settings_layout.addRow(self.auto_save)
        settings_layout.addRow(self.notifications)
        
        # Kaydet butonu
        save_btn = QPushButton("Ayarları Kaydet")
        try:
            save_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'save.svg'))
            save_btn.setIcon(save_icon)
            save_btn.setIconSize(QSize(16, 16))
        except Exception:
            save_btn.setText("Ayarları Kaydet")
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #27ae60, stop:1 #229954);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2ecc71, stop:1 #27ae60);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #229954, stop:1 #1e8449);
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        
        layout.addWidget(user_group)
        layout.addWidget(settings_group)
        layout.addWidget(save_btn)
        layout.addStretch()
        
        try:
            settings_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'settings.svg'))
            self.tab_widget.addTab(settings_tab, settings_icon, "Ayarlar")
        except Exception:
            self.tab_widget.addTab(settings_tab, "Ayarlar")
        
        # Kullanıcı verilerini yükle
        self.load_user_data()
        
    def update_mode_label(self):
        # Inform user that application runs in offline mode
        self.add_message("Mod", "Offline mod (TAU) aktif.")

    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return
        # Kullanıcı mesajını göster
        self.add_message("Sen", message)
        self.input_field.clear()
        # Offline mode only
        try:
            response, confidence = self.cevapla_func(self.cursor, message)
            self.add_message("TAU", response)
            # Sesli yanıt (Kısa tutmak için ilk cümleyi veya belli bir uzunluğu okuyabiliriz)
            # Ama şimdilik hepsini okusun
            # Arayüzü dondurmamak için bunu bir thread içinde yapmak daha iyi olurdu ama basit tutuyoruz
            from threading import Thread
            Thread(target=text_to_speech, args=(response,)).start()
            
        except Exception as e:
            self.add_message("TAU", f"Bir hata oluştu: {e}")
        
            
    def add_message(self, sender, message):
        timestamp = datetime.now().strftime("%H:%M")

        # Gelen mesajı HTML'e uygun hale getir.
        # Not: Rapor gibi bazı özellikler zaten HTML döndürür, bu yüzden her şeyi escape'lemiyoruz.
        # Bunun yerine, temel karakterleri güvenli hale getirip satır sonlarını <br> ile değiştiriyoruz.
        # Bu, basit metinleri ve önceden biçimlendirilmiş HTML'yi idare etmek için iyi bir denge.
        if sender == "Sen":
             message = html.escape(message).replace('\n', '<br>')
        
        # Modern mesaj formatı (kullanicida emoji yoksa yerine yerel SVG kullan)
        if sender == "TAU":
            icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'icon-app.svg')
            icon_url = f"file://{icon_path}"
            formatted_message = f"""
            <div style="margin: 10px 0; padding: 15px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3498db, stop:1 #2980b9); border-radius: 12px; color: white;">
                <div style="font-weight: bold; margin-bottom: 5px;"><img src='{icon_url}' style='width:16px;height:16px;vertical-align:middle;margin-right:6px;'/> {sender} <span style="font-size: 11px; opacity: 0.8;">[{timestamp}]</span></div>
                <div style="line-height: 1.4;">{message}</div>
            </div>
            """
        else:
            user_icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'icon-send.svg')
            user_icon_url = f"file://{user_icon_path}"
            formatted_message = f"""
            <div style="margin: 10px 0; padding: 15px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ecf0f1, stop:1 #bdc3c7); border-radius: 12px; color: #2c3e50;">
                <div style="font-weight: bold; margin-bottom: 5px;"><img src='{user_icon_url}' style='width:16px;height:16px;vertical-align:middle;margin-right:6px;'/> {sender} <span style="font-size: 11px; opacity: 0.8;">[{timestamp}]</span></div>
                <div style="line-height: 1.4;">{message}</div>
            </div>
            """
        
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(formatted_message)
        
        # Otomatik scroll - güvenli kontrol
        scrollbar = self.chat_display.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())
        
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
                item.setData(0, (key, value))  # UserRole = 0
                try:
                    key_icon = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'history.svg'))
                    item.setIcon(key_icon)
                except Exception:
                    pass
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
            key, value = current_item.data(0)  # UserRole = 0
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
            key, value = current_item.data(0)  # UserRole = 0
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
                item = QListWidgetItem(f"{metin} ({hedef_tarih})")
                item.setData(0, (metin, hedef_tarih, durum))  # UserRole = 0
                try:
                    if durum == 'tamamlandi':
                        iconp = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'save.svg'))
                    else:
                        iconp = QIcon(os.path.join(os.path.dirname(__file__), 'icons', 'history.svg'))
                    item.setIcon(iconp)
                except Exception:
                    pass
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
            metin, hedef_tarih, durum = current_item.data(0)  # UserRole = 0
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
            metin, hedef_tarih, durum = current_item.data(0)  # UserRole = 0
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
        self.add_message("TAU", f"HATIRLATMA: {metin}")
        
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

    def handle_voice_command(self):
        try:
            self.add_message("TAU", "Seni dinliyorum...")
            QApplication.processEvents() # Arayüzün güncellenmesini sağla
            
            komut = dinle_ve_yaziya_cevir()
            
            if komut:
                self.input_field.setText(komut)
                self.send_message()
            else:
                self.add_message("TAU", "Sesini duyamadım veya anlayamadım.")
        except Exception as e:
            self.add_message("TAU", f"Sesli komut hatası: {e}") 