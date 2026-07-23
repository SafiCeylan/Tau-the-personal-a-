from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QComboBox, QMessageBox, QFormLayout, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal

class SettingsViewWidget(QWidget):
    config_saved = pyqtSignal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        
        head = QLabel("⚙️ Sistem & AI Yapılandırması")
        head.setStyleSheet("color: #ffd873; font-size: 20px; font-weight: 800;")
        
        sub = QLabel("Model sağlayıcısını, yerel sunucu adreslerini ve sistem tercihlerini yönetin")
        sub.setStyleSheet("color: #9aa0a6; font-size: 12px;")

        title_box.addWidget(head)
        title_box.addWidget(sub)
        layout.addLayout(title_box)

        # Form Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(20, 23, 33, 0.85);
                border: 1px solid rgba(242, 181, 68, 0.2);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        form = QFormLayout(card)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        # Provider Combo
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Ollama (Yerel LLM)", "ollama")
        self.provider_combo.addItem("Google Gemini (Bulut / API Key)", "gemini")
        self.provider_combo.addItem("KoboldCPP (Yerel LLM)", "kobold")
        self.provider_combo.addItem("TAU Backend (Bulut/Sunucu)", "tau_backend")

        # Preselect current provider
        cur_prov = self.config.get("ai_provider", "ollama")
        idx = self.provider_combo.findData(cur_prov)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        # Inputs
        self.ollama_url_in = QLineEdit(self.config.get("ollama_url", "http://127.0.0.1:11434"))
        self.ollama_model_in = QLineEdit(self.config.get("ollama_model", "gemma3:4b"))

        self.gemini_key_in = QLineEdit(self.config.get("gemini_api_key", "") or "")
        self.gemini_key_in.setEchoMode(QLineEdit.Password)
        self.gemini_key_in.setPlaceholderText("AIzaSy...")

        self.gemini_model_in = QLineEdit(self.config.get("gemini_model", "gemini-1.5-flash"))

        self.kobold_url_in = QLineEdit(self.config.get("kobold_url", "http://localhost:5001"))

        self.tau_url_in = QLineEdit(self.config.get("tau_backend_url", "https://your-tau-backend-url.com/api") or "")
        self.tau_key_in = QLineEdit(self.config.get("tau_api_key", "") or "")
        self.tau_key_in.setEchoMode(QLineEdit.Password)

        # E-posta (Gmail SMTP) — "X'e mail gönder" özelliği için
        self.smtp_user_in = QLineEdit(self.config.get("smtp_user", "") or "")
        self.smtp_user_in.setPlaceholderText("ornek@gmail.com")
        self.smtp_pass_in = QLineEdit(self.config.get("smtp_pass", "") or "")
        self.smtp_pass_in.setEchoMode(QLineEdit.Password)
        self.smtp_pass_in.setPlaceholderText("Gmail UYGULAMA şifresi (normal şifre değil)")

        # Telegram köprüsü — telefondan komut vermek için
        self.tg_token_in = QLineEdit(self.config.get("telegram_token", "") or "")
        self.tg_token_in.setEchoMode(QLineEdit.Password)
        self.tg_token_in.setPlaceholderText("@BotFather'dan alınan bot token'ı")
        self.tg_chat_in = QLineEdit(str(self.config.get("telegram_chat_id", "") or ""))
        self.tg_chat_in.setPlaceholderText("Bota mesaj atınca söylediği Chat ID")

        form.addRow("Aktif AI Sağlayıcı:", self.provider_combo)
        form.addRow("Ollama Sunucu URL:", self.ollama_url_in)
        form.addRow("Ollama Model Adı:", self.ollama_model_in)
        form.addRow("Google Gemini API Key:", self.gemini_key_in)
        form.addRow("Gemini Model:", self.gemini_model_in)
        form.addRow("KoboldCPP URL:", self.kobold_url_in)
        form.addRow("TAU Backend URL:", self.tau_url_in)
        form.addRow("TAU API Anahtarı:", self.tau_key_in)
        form.addRow("Gmail Adresi (SMTP):", self.smtp_user_in)
        form.addRow("Gmail Uygulama Şifresi:", self.smtp_pass_in)
        form.addRow("Telegram Bot Token:", self.tg_token_in)
        form.addRow("Telegram Chat ID:", self.tg_chat_in)

        # 🔊 Ses Ayarları
        self.tts_check = QCheckBox("Cevapları sesli oku")
        self.tts_check.setChecked(bool(self.config.get("tts_enabled")))

        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItem("Edge Neural — Ahmet (kalın erkek, doğal) 🔴", "edge")
        self.tts_engine_combo.addItem("Google TTS (İnternet — kadın ses)", "gtts")
        self.tts_engine_combo.addItem("Windows SAPI (Offline — TR ses paketi gerekir)", "sapi")
        idx = self.tts_engine_combo.findData(self.config.get("tts_engine", "edge"))
        if idx >= 0:
            self.tts_engine_combo.setCurrentIndex(idx)

        self.wake_check = QCheckBox("\"Hey Ultron\" ile sesli uyandırma (lokal, Vosk)")
        self.wake_check.setChecked(bool(self.config.get("wake_enabled")))

        # Mikrofon seçici (wake word ve sesli komut bunu kullanır)
        self.mic_combo = QComboBox()
        self.mic_combo.addItem("Sistem varsayılanı", -1)
        for idx, name in self._list_microphones():
            self.mic_combo.addItem(f"[{idx}] {name}", idx)
        cur_mic = self.config.get("mic_device_index", -1)
        mic_idx = self.mic_combo.findData(cur_mic)
        if mic_idx >= 0:
            self.mic_combo.setCurrentIndex(mic_idx)

        mic_row = QHBoxLayout()
        mic_row.addWidget(self.mic_combo, 1)
        mic_test_btn = QPushButton("🎙️ Test Et")
        mic_test_btn.setCursor(Qt.PointingHandCursor)
        mic_test_btn.clicked.connect(self.test_microphone)
        mic_row.addWidget(mic_test_btn)
        mic_widget = QWidget()
        mic_widget.setLayout(mic_row)

        form.addRow("🔊 Sesli Yanıt (TTS):", self.tts_check)
        form.addRow("TTS Motoru:", self.tts_engine_combo)
        form.addRow("🎙️ Wake Word:", self.wake_check)
        form.addRow("Mikrofon:", mic_widget)

        layout.addWidget(card)

        # Buttons Bar
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        test_btn = QPushButton("🔌 Bağlantıyı Test Et")
        test_btn.setProperty("class", "secondaryBtn")
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.clicked.connect(self.test_connection)

        save_btn = QPushButton("💾 Ayarları Kaydet")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings)

        btn_box.addStretch()
        btn_box.addWidget(test_btn)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        layout.addStretch()

    @staticmethod
    def _list_microphones():
        """Kullanılabilir mikrofon girişlerini (indeks, ad) listeler.
        Sadece MME host API'si listelenir — fiziksel aygıt başına tek, kısa kayıt."""
        mics = []
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if d.get('max_input_channels', 0) > 0:
                    try:
                        host = sd.query_hostapis(d['hostapi'])['name']
                    except Exception:
                        host = ''
                    if host == 'MME':
                        mics.append((i, d['name']))
        except Exception as e:
            print(f"[Ayarlar] Mikrofon listesi alınamadı: {e}")
        return mics

    def test_microphone(self):
        """Seçili mikrofondan 2 saniye kayıt alıp ses seviyesini ölçer."""
        try:
            import array
            import sounddevice as sd
        except ImportError:
            QMessageBox.warning(self, "Eksik Paket", "sounddevice kurulu değil.")
            return

        device = self.mic_combo.currentData()
        device = None if device in (None, -1) else device

        QMessageBox.information(
            self, "Mikrofon Testi",
            "Tamam'a bastıktan sonra 2 saniye boyunca KONUŞUN — ses seviyenizi ölçeceğim.")
        try:
            kayit = sd.rec(int(2 * 16000), samplerate=16000, channels=1,
                           dtype='int16', device=device)
            sd.wait()
            samples = array.array('h', kayit.tobytes())
            tepe = max(abs(s) for s in samples) if samples else 0
            yuzde = round(tepe / 32767 * 100)
            if yuzde >= 10:
                QMessageBox.information(
                    self, "Mikrofon Testi",
                    f"✅ Ses algılandı! Tepe seviye: %{yuzde}\nBu mikrofon kullanıma hazır.")
            elif yuzde >= 2:
                QMessageBox.warning(
                    self, "Mikrofon Testi",
                    f"⚠️ Çok zayıf ses algılandı (%{yuzde}). Mikrofona daha yakın konuşun "
                    "veya Windows ses ayarlarından mikrofon seviyesini yükseltin.")
            else:
                QMessageBox.warning(
                    self, "Mikrofon Testi",
                    f"❌ Ses algılanamadı (%{yuzde}). Yanlış mikrofon seçilmiş olabilir — "
                    "listeden başka bir aygıt deneyin.")
        except Exception as e:
            QMessageBox.critical(self, "Mikrofon Testi", f"Kayıt hatası:\n{e}")

    def test_connection(self):
        prov = self.provider_combo.currentData()
        import requests
        try:
            if prov == "ollama":
                url = self.ollama_url_in.text().strip() + "/api/tags"
                res = requests.get(url, timeout=4)
                if res.status_code == 200:
                    QMessageBox.information(self, "Bağlantı Başarılı", "Ollama sunucusuna başarıyla bağlandı! 🚀")
                else:
                    QMessageBox.warning(self, "Uyarı", f"Ollama yanıt verdi ancak durum kodu: {res.status_code}")
            elif prov == "gemini":
                key = self.gemini_key_in.text().strip()
                if not key:
                    QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir Google Gemini API anahtarı girin.")
                    return
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    QMessageBox.information(self, "Bağlantı Başarılı", "Google Gemini API bağlantısı doğrulandı! 🚀")
                else:
                    QMessageBox.warning(self, "Hata", f"Gemini API yanıt hatası: {res.status_code} - {res.text}")
            elif prov == "kobold":
                url = self.kobold_url_in.text().strip() + "/v1/models"
                res = requests.get(url, timeout=4)
                if res.status_code == 200:
                    QMessageBox.information(self, "Bağlantı Başarılı", "KoboldCPP sunucusuna başarıyla bağlandı! 🚀")
                else:
                    QMessageBox.warning(self, "Uyarı", f"KoboldCPP yanıt verdi ancak durum kodu: {res.status_code}")
            else:
                QMessageBox.information(self, "Test", "TAU Backend konfigürasyonu kontrol ediliyor...")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya bağlanılamadı:\n{e}")

    def save_settings(self):
        # Mevcut config'i temel al: formda olmayan anahtarlar (tau_timeout,
        # tau_endpoint, kullanıcının elle eklediği ayarlar) kaybolmasın
        new_config = dict(self.config)
        new_config.update({
            "ai_provider": self.provider_combo.currentData(),
            "ollama_url": self.ollama_url_in.text().strip(),
            "ollama_model": self.ollama_model_in.text().strip(),
            "gemini_api_key": self.gemini_key_in.text().strip(),
            "gemini_model": self.gemini_model_in.text().strip(),
            "kobold_url": self.kobold_url_in.text().strip(),
            "tau_backend_url": self.tau_url_in.text().strip(),
            "tau_api_key": self.tau_key_in.text().strip(),
            "smtp_user": self.smtp_user_in.text().strip(),
            "smtp_pass": self.smtp_pass_in.text().strip(),
            "telegram_token": self.tg_token_in.text().strip(),
            "telegram_chat_id": self.tg_chat_in.text().strip(),
            "tts_enabled": self.tts_check.isChecked(),
            "tts_engine": self.tts_engine_combo.currentData(),
            "wake_enabled": self.wake_check.isChecked(),
            "mic_device_index": self.mic_combo.currentData(),
        })
        new_config.setdefault("tau_timeout", 30)
        new_config.setdefault("tau_endpoint", "/chat")
        self.config = new_config
        self.config_saved.emit(new_config)
        QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi ve uygulandı!")
