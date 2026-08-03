"""
TAU — Masaüstü Arayüzü (Refactored & Modernized)

Bileşen tabanlı (component-based) mimarı:
- ui/styles/theme.py (Glassmorphic dark/amber styling)
- ui/components/sidebar.py (Yan navigasyon)
- ui/components/chat_view.py (Sohbet & AI Core visualizer)
- ui/components/memory_view.py (Hafıza kartları & yönetimi)
- ui/components/reminders_view.py (Hatırlatıcı kartları)
- ui/components/mood_view.py (Duygu analizi paneli)
- ui/components/settings_view.py (Sistem & model yapılandırıcı)
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QMessageBox, QFrame, QLabel, QSystemTrayIcon, QMenu
)

from core.paths import veri_yolu
from database.db_manager import DatabaseManager
from features.reminders import hatirlatma_algila, hatirlatma_kaydet
from features.actions.system_control import sistem_komutu_algila, sistem_sesi_getir, sistem_sesi_kontrol
from features import scheduler as zamanlayici
from features.kobold import kobold_generate
from features.ollama import ollama_generate, ollama_chat_stream
from features.tau_backend import tau_backend_soru_sor
from features.gemini import gemini_generate

from core.engine import UltronCoreEngine

from ui.styles.theme import MAIN_STYLESHEET
from ui.components.sidebar import SidebarWidget
from ui.components.chat_view import ChatViewWidget
from ui.components.memory_view import MemoryViewWidget
from ui.components.reminders_view import RemindersViewWidget
from ui.components.mood_view import MoodViewWidget
from ui.components.settings_view import SettingsViewWidget
from ui.components.ultron_focus_view import UltronFocusViewWidget
from ui.components.modes_view import ModesViewWidget
from ui.components.stats_view import StatsViewWidget

try:
    from features.speech import dinle_ve_yaziya_cevir, seslendir, konusmayi_durdur
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

    def seslendir(*a, **k):
        pass

    def konusmayi_durdur():
        pass

# Vosk wake word modeli (yoksa wake word sessizce devre dışı kalır)
WAKE_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'vosk-tr'
)

# config.json artık %APPDATA%\ULTRON altında — exe ve python sürümü aynı ayarı
# okur, derleme de üstüne yazamaz. (Eski konumdan ilk açılışta göç eder.)
CONFIG_PATH = veri_yolu('config.json')

PROVIDER_LABELS = {
    'kobold': 'KoboldCPP (Yerel)',
    'ollama': 'Ollama (Yerel)',
    'gemini': 'Google Gemini (API)',
    'tau_backend': 'TAU Backend',
}

# Bekleyen güvenlik onayı SADECE bu mesajlarla (tam eşleşme) onaylanabilir.
# Substring eşleşmesi ("tamam kanka başka şey soracağım" gibi) kabul edilmez.
CONFIRM_PHRASES = {"onaylıyorum", "onayla", "evet", "evet onaylıyorum", "çalıştır", "tamam"}

# Onay kartı bu süre içinde yanıtlanmazsa bekleyen komut otomatik iptal edilir (ms)
CONFIRMATION_TIMEOUT_MS = 60_000


def build_ultron_icon() -> QIcon:
    """Ultron kırmızı çekirdek simgesini QPainter ile çizer (dosya bağımlılığı yok)."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    # Dış halka
    p.setPen(QPen(QColor('#ff1a26'), 5))
    p.setBrush(QBrush(QColor(18, 4, 6)))
    p.drawEllipse(5, 5, 54, 54)
    # İç çekirdek
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor('#ff1a26')))
    p.drawEllipse(22, 22, 20, 20)
    # Parlak merkez
    p.setBrush(QBrush(QColor('#ffffff')))
    p.drawEllipse(29, 29, 6, 6)
    p.end()
    return QIcon(pm)

def load_config():
    """config.json'u okur; eksik/bozuksa güvenli varsayılanlarla devam eder."""
    defaults = {
        'ai_provider': 'ollama',
        'kobold_url': 'http://localhost:5001',
        'ollama_url': 'http://127.0.0.1:11434',
        'ollama_model': 'qwen2.5:3b',
        'tau_backend_url': None,
        'tau_api_key': None,
        'gemini_api_key': None,
        'gemini_model': 'gemini-1.5-flash',
    }
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        for key, value in cfg.items():
            if value is not None:
                defaults[key] = value
    except Exception as e:
        print(f"[TAU] config.json okunamadı, varsayılanlar kullanılıyor: {e}")
    return defaults


def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[TAU] config.json yazılamadı: {e}")
        return False


# LLM sağlayıcı seçimi artık UI'dan bağımsız (engine + Telegram de kullanır).
from features.llm_gateway import llm_uret


class AIWorkerThread(QThread):
    finished_signal = pyqtSignal(str, object)
    error_signal = pyqtSignal(str)

    def __init__(self, provider, prompt, config, context=None):
        super().__init__()
        self.provider = provider
        self.prompt = prompt
        self.config = config
        self.context = context

    def run(self):
        try:
            ans, ctx = llm_uret(self.provider, self.prompt, self.config, self.context)
            self.finished_signal.emit(ans or "Yanıt alınamadı.", ctx)
        except Exception as e:
            self.error_signal.emit(f"AI Hatası: {str(e)}")


class StreamWorkerThread(QThread):
    """Ollama /api/chat streaming: her token geldiğinde sinyal atar."""
    token_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, prompt, config):
        super().__init__()
        self.prompt = prompt
        self.config = config

    def run(self):
        try:
            full = ollama_chat_stream(
                self.prompt,
                ollama_url=self.config.get('ollama_url', 'http://127.0.0.1:11434'),
                model=self.config.get('ollama_model', 'gemma3:4b'),
                on_token=lambda t: self.token_signal.emit(t),
            )
            self.finished_signal.emit(full or "Yanıt alınamadı.")
        except Exception as e:
            self.error_signal.emit(f"AI Hatası: {str(e)}")


class EngineWorkerThread(QThread):
    """Ultron Core Engine'i UI thread'ini dondurmadan arka planda çalıştırır.

    Web araması, uygulama tarama (os.walk) ve YouTube isteği gibi yavaş işlemler
    engine içinde olduğundan bu thread olmadan pencere saniyelerce donuyordu.
    """
    finished_signal = pyqtSignal(str, object)  # (orijinal metin, UltronContext)
    error_signal = pyqtSignal(str)

    def __init__(self, engine, text, recent_context=None):
        super().__init__()
        self.engine = engine
        self.text = text
        self.recent_context = recent_context

    def run(self):
        try:
            ctx = self.engine.process(self.text, recent_context=self.recent_context)
            self.finished_signal.emit(self.text, ctx)
        except Exception as e:
            self.error_signal.emit(f"Engine Hatası: {str(e)}")


class WakeWordThread(QThread):
    """
    🎙️ "Hey Ultron" — Vosk ile TAMAMEN LOKAL wake word dinleyicisi.
    Ses hiçbir sunucuya gitmez; tanıma gramerle sadece 'ultron' kelimesine
    kilitlenir (az CPU, az yanlış tetikleme). Uyanınca sinyal atar; asıl komut
    mevcut Google STT akışıyla alınır.
    """
    wake_detected = pyqtSignal()
    status_signal = pyqtSignal(str)

    def __init__(self, model_path: str, device_index=None):
        super().__init__()
        self.model_path = model_path
        self.device_index = device_index if device_index not in (None, -1) else None
        self._stop = False
        self.paused = False   # TTS konuşurken / komut dinlenirken kendini duymasın

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self._run_loop()
        except Exception as e:
            print(f"[WakeWord] Dinleyici durdu: {e}")
            self.status_signal.emit(f"⚠️ Wake word dinleyicisi durdu: {e}")

    def _run_loop(self):
        import queue
        try:
            import vosk
            import sounddevice as sd
        except ImportError as e:
            self.status_signal.emit(f"⚠️ Wake word için eksik paket: {e}")
            return

        if not os.path.isdir(self.model_path):
            self.status_signal.emit(
                "ℹ️ Wake word modeli bulunamadı (models/vosk-tr) — özellik devre dışı.")
            return

        vosk.SetLogLevel(-1)
        model = vosk.Model(self.model_path)
        # Gramer kilidi: tanıyıcı SADECE bu kelimeleri arar → hızlı + isabetli.
        # NOT: 'ultron' TR sözlüğünde yok; fonetik komşusu 'ultra' kullanılır —
        # kullanıcı "hey ultron" dediğinde model "hey ultra" duyar, biz onu yakalarız.
        rec = vosk.KaldiRecognizer(model, 16000, json.dumps(
            ["hey ultra", "ultra", "[unk]"], ensure_ascii=False))

        q = queue.Queue()

        def _cb(indata, frames, t, status):
            q.put(bytes(indata))

        # Mikrofonu aç — seçili aygıt nazlanırsa (BT kulaklık modu vb.)
        # sistem varsayılanına düş; ikisi de olmazsa düzgün mesajla çık
        stream = None
        kullanilan_dev = None
        for dev in dict.fromkeys([self.device_index, None]):
            try:
                stream = sd.RawInputStream(samplerate=16000, blocksize=8000,
                                           dtype='int16', channels=1,
                                           callback=_cb, device=dev)
                kullanilan_dev = dev
                break
            except Exception as e:
                print(f"[WakeWord] Mikrofon {dev} açılamadı: {e}")

        if stream is None:
            self.status_signal.emit(
                "⚠️ Wake word: hiçbir mikrofon açılamadı — Ayarlar'dan farklı bir mikrofon "
                "seçip 'Test Et' ile doğrulayın.")
            return

        mik_adi = "sistem varsayılanı"
        if kullanilan_dev is not None:
            try:
                mik_adi = sd.query_devices(kullanilan_dev)['name']
            except Exception:
                pass
        if kullanilan_dev is None and self.device_index is not None:
            self.status_signal.emit(
                "⚠️ Seçili mikrofon açılamadı (bluetooth modu olabilir) — "
                "sistem varsayılanına geçildi.")
        self.status_signal.emit(f"🎙️ 'Hey Ultron' dinleyicisi aktif (lokal) — mikrofon: {mik_adi}")

        with stream:
            mikrofon_acik = True
            while not self._stop:
                # DURAKLAT: STT (komut dinleme) veya TTS sırasında mikrofonu GERÇEKTEN
                # bırak. Sadece veriyi atmak yetmez — stream açık kalırsa Windows
                # mikrofonu ikinci akışa (sr.Microphone) vermez ve sesli komut çalışmaz.
                if self.paused:
                    if mikrofon_acik:
                        try:
                            stream.stop()      # mikrofonu serbest bırak
                        except Exception:
                            pass
                        mikrofon_acik = False
                    time.sleep(0.15)
                    continue
                if not mikrofon_acik:
                    try:
                        stream.start()         # mikrofonu geri al
                    except Exception as e:
                        print(f"[WakeWord] Mikrofon geri alınamadı: {e}")
                    mikrofon_acik = True
                    rec.Reset()
                    while not q.empty():       # duraklama sırasındaki bayat sesi at
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            break
                try:
                    data = q.get(timeout=1)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get('text', '')
                    if 'ultra' in text:
                        self.wake_detected.emit()
                        rec.Reset()


class TelegramWorkerThread(QThread):
    """
    📱 Telegram köprüsü: long-polling ile botu dinler, mesajları ULTRON
    engine'inden geçirir, cevabı Telegram'a döner.

    Güvenlik: sadece config'teki telegram_chat_id komut verebilir; riskli
    komutlar masaüstündeki gibi onay ister (inline ✅/❌ butonları, 60 sn).
    """
    activity_signal = pyqtSignal(str, str)   # (gelen_mesaj, verilen_cevap)
    status_signal = pyqtSignal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._stop = False
        self.ai_context = {}
        self.pending = {}  # chat_id -> (komut, son_gecerlilik_zamani)
        self.history = {}  # chat_id -> [{"role": "user"/"assistant", "text": ...}] (çok-turlu bağlam)

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------------
    def run(self):
        # PyQt5'te thread içindeki yakalanmamış hata TÜM uygulamayı kapatır —
        # köprüde ne olursa olsun uygulama ayakta kalmalı.
        try:
            self._run_loop()
        except Exception as e:
            print(f"[Telegram] Köprü çöktü (uygulama etkilenmedi): {e}")
            self.status_signal.emit(f"⚠️ Telegram köprüsü durdu: {e}")

    def _run_loop(self):
        from features import telegram_bridge as tg
        token = (self.controller.config.get('telegram_token') or '').strip()
        if not token:
            return

        bot_adi = tg.bot_bilgisi(token)
        if bot_adi:
            tg.set_bot_commands(token)
            self.status_signal.emit(f"📱 Telegram köprüsü aktif: @{bot_adi} (Hızlı Komut Menüsü Kaydedildi)")
        else:
            self.status_signal.emit("⚠️ Telegram token doğrulanamadı — köprü kapalı.")
            return

        offset = None
        while not self._stop:
            updates = tg.get_updates(token, offset, timeout=20)
            if updates is None:
                # Ağ hatası — kısa bekleyip tekrar dene
                for _ in range(10):
                    if self._stop:
                        return
                    time.sleep(0.5)
                continue
            for up in updates:
                offset = up.get('update_id', 0) + 1
                try:
                    self._handle_update(tg, token, up)
                except Exception as e:
                    print(f"[Telegram] Güncelleme işlenemedi: {e}")

    # ------------------------------------------------------------------
    def _allowed_chat(self):
        return str(self.controller.config.get('telegram_chat_id') or '').strip()

    def _handle_update(self, tg, token, up):
        if 'callback_query' in up:
            self._handle_callback(tg, token, up['callback_query'])
            return

        msg = up.get('message') or {}
        chat_id = (msg.get('chat') or {}).get('id')
        if chat_id is None:
            return

        allowed = self._allowed_chat()
        if not allowed or str(chat_id) != allowed:
            tg.send_message(
                token, chat_id,
                "⛔ **Yetkisiz erişim.** Bu bot ULTRON'un sahibine kilitlidir.\n\n"
                f"Bot sizinse: ULTRON masaüstü → Çekirdek Ayarları → 'Telegram Chat ID' "
                f"alanına şunu girin: `{chat_id}`"
            )
            return

        # 🎙️ Sesli mesaj → STT → komut
        if msg.get('voice'):
            self._handle_voice_message(tg, token, chat_id, msg['voice'])
            return

        # 📥 Dosya / fotoğraf → İndirilenler'e kaydet
        if msg.get('document') or msg.get('photo'):
            self._handle_incoming_file(tg, token, chat_id, msg)
            return

        text = (msg.get('text') or '').strip()
        if not text:
            return
        self._handle_text_command(tg, token, chat_id, text)

    def _handle_text_command(self, tg, token, chat_id, text):
        cmd_lower = text.lower().strip()

        # 🏠 Ana Menü
        if cmd_lower in ('/start', '/help', '/yardim', '/menu', '/klavye', '🏠 ana menü', '🎛️ hızlı menü'):
            tg.send_message(
                token, chat_id,
                "🔴 **ULTRON NEURAL CORE — Telegram Kategorili Komut Menüsü**\n\n"
                "Aşağıdaki menü kategorilerinden birini seçerek veya kısayol butonlarını kullanarak bilgisayarınızı uzaktan yönetebilirsiniz:\n\n"
                "• 🖥️ **Pencere & Gezinme** (`/pencere` — Alt+Tab, Win+D, Win+E)\n"
                "• ✍️ **Yazı & Düzenleme** (`/duzenleme` — Ctrl+C, Ctrl+V, Ctrl+Z)\n"
                "• 🌐 **Tarayıcı & Sekme** (`/tarayici` — Ctrl+T, Ctrl+W, F5)\n"
                "• 🎵 **Medya & Ses** (`/medya` — Oynat, Duraklat, Ses)\n"
                "• 💻 **Sistem & Güç** (`/sistem_menu` — CPU/RAM, Chrome, CMD)\n"
                "• 📊 **Bilgi & Brifing** (`/brifing_menu`)",
                reply_markup=tg.ana_menu_klavyesi()
            )
            return

        # 🖥️ Pencere & Gezinme Menüsü
        if cmd_lower in ('/pencere', '🖥️ pencere & gezinme'):
            tg.send_message(
                token, chat_id,
                "🖥️ **PENCERE VE MASAÜSTÜ GEZİNME MENÜSÜ**\n\n"
                "Aktif pencereler arası geçiş yapın, masaüstünü gösterin veya pencereleri hizalayın:",
                reply_markup=tg.pencere_gezinme_klavyesi()
            )
            return

        # ✍️ Yazı & Düzenleme Menüsü
        if cmd_lower in ('/duzenleme', '✍️ yazı & düzenleme'):
            tg.send_message(
                token, chat_id,
                "✍️ **YAZI VE DÜZENLEME KISAYOLLARI MENÜSÜ**\n\n"
                "Kopyala, yapıştır, geri al, kaydet ve tuş darbeleri:",
                reply_markup=tg.yazi_duzenleme_klavyesi()
            )
            return

        # 🌐 Tarayıcı & Sekme Menüsü
        if cmd_lower in ('/tarayici', '🌐 tarayıcı & sekme'):
            tg.send_message(
                token, chat_id,
                "🌐 **TARAYICI VE SEKME KISAYOLLARI MENÜSÜ**\n\n"
                "Sekme açma, kapatma, yenileme ve tam ekran kontrolleri:",
                reply_markup=tg.tarayici_klavyesi()
            )
            return

        # 🎵 Medya & Ses Menüsü
        if cmd_lower in ('/medya', '📸 ekran & medya menüsü', '🎵 medya & ses'):
            tg.send_message(
                token, chat_id,
                "🎵 **EKRAN VE MEDYA YÖNETİM MENÜSÜ**\n\n"
                "Ekran görüntüsü alma ve medya kontrolleri:",
                reply_markup=tg.medya_klavyesi()
            )
            return

        # 💻 Sistem & Güç Menüsü
        if cmd_lower in ('/sistem_menu', '💻 sistem & güç', '💻 sistem & guc'):
            tg.send_message(
                token, chat_id,
                "💻 **SİSTEM VE UYGULAMA YÖNETİM MENÜSÜ**\n\n"
                "CPU/RAM durumu, hızlı uygulama açma ve güç kontrolleri:",
                reply_markup=tg.sistem_klavyesi()
            )
            return

        # 📊 Bilgi & Brifing Menüsü
        if cmd_lower in ('/brifing_menu', '📊 bilgi & brifing'):
            tg.send_message(
                token, chat_id,
                "📊 **BİLGİ VE BRİFİNG MENÜSÜ**\n\n"
                "Hava, döviz, haberler, hatırlatmalar ve notlar:",
                reply_markup=tg.brifing_klavyesi()
            )
            return

        # 🎛️ Menüyü Kapat — hızlı buton takımını gizler
        if cmd_lower in ('/menu_kapat', '🎛️ menüyü kapat', 'menüyü kapat'):
            tg.send_message(
                token, chat_id,
                "🎛️ Hızlı buton takımı gizlendi. Geri açmak için `/menu` yazman yeterli.",
                reply_markup={"remove_keyboard": True}
            )
            return

        # ⭐ Özel Kısayollarım Menüsü
        if cmd_lower in ('/ozel', '⭐ özel kısayollarım', 'özel kısayollarım'):
            tg.send_message(
                token, chat_id,
                "⭐ **ÖZEL KISAYOLLARIM MENÜSÜ**\n\n"
                "Kendi eklediğiniz özel tuş kombinasyonları ve komutlar aşağıdadır.\n\n"
                "• **Yeni Ekleme:** `kısayol ekle: VS Code = code` veya `kısayol ekle: Photoshop = ctrl+alt+shift+p`\n"
                "• **Silme:** `kısayol sil: VS Code`",
                reply_markup=tg.ozel_klavye()
            )
            return

        if cmd_lower in ('➕ kısayol ekle', '/kisayol_ekle'):
            tg.send_message(
                token, chat_id,
                "➕ **YENİ ÖZEL KİSAYOL EKLEME**\n\n"
                "Lütfen eklemek istediğiniz kısayolu şu formatta yazıp gönderin:\n\n"
                "`kısayol ekle: Buton Adı = tuş veya komut`\n\n"
                "**Örnekler:**\n"
                "• `kısayol ekle: Photoshop = ctrl+alt+shift+p`\n"
                "• `kısayol ekle: Terminal = ctrl+alt+t`\n"
                "• `kısayol ekle: Spotify = spotify`",
                reply_markup=tg.ozel_klavye()
            )
            return

        if cmd_lower in ('🗑️ kısayol sil', '/kisayol_sil'):
            tg.send_message(
                token, chat_id,
                "🗑️ **ÖZEL KISAYOL SİLME**\n\n"
                "Silmek istediğiniz kısayolun adını şu formatta gönderin:\n\n"
                "`kısayol sil: Buton Adı`\n\n"
                "**Örnek:** `kısayol sil: Photoshop`",
                reply_markup=tg.ozel_klavye()
            )
            return

        # Kısayol ekleme kalıbı ("kısayol ekle: X = Y")
        import re
        m_ekle = re.search(r'kısayol\s*ekle\s*:\s*([^=]+)=\s*(.+)', text, re.IGNORECASE)
        if m_ekle:
            from features import custom_shortcuts
            ad_str = m_ekle.group(1).strip()
            komut_str = m_ekle.group(2).strip()
            ok, msg_res = custom_shortcuts.ekle(ad_str, komut_str)
            tg.send_message(token, chat_id, msg_res, reply_markup=tg.ozel_klavye())
            return

        # Kısayol silme kalıbı ("kısayol sil: X")
        m_sil = re.search(r'kısayol\s*sil\s*:\s*(.+)', text, re.IGNORECASE)
        if m_sil:
            from features import custom_shortcuts
            ad_str = m_sil.group(1).strip()
            ok, msg_res = custom_shortcuts.sil(ad_str)
            tg.send_message(token, chat_id, msg_res, reply_markup=tg.ozel_klavye())
            return

        # Gelişmiş Hızlı Buton ve Slash Komut Eşlemeleri (40+ Kısayol)
        quick_map = {
            # Pencere & Gezinme Kısayolları
            "/alt_tab": "alt+tab bas",
            "🔄 alt+tab": "alt+tab bas",
            "🔙 alt+shift+tab": "alt+shift+tab bas",
            "/win_d": "win+d bas",
            "🖥️ win+d": "win+d bas",
            "/win_e": "win+e bas",
            "📁 win+e": "win+e bas",
            "📋 win+v": "win+v bas",
            "📸 win+shift+s": "win+shift+s bas",
            "⚙️ ctrl+shift+esc": "ctrl+shift+esc bas",
            "/alt_f4": "alt+f4 bas",
            "❌ alt+f4": "alt+f4 bas",
            "🔒 win+l": "win+l bas",
            "⬆️ win+up": "win+up bas",
            "⬇️ win+down": "win+down bas",
            "⬅️ win+left": "win+left bas",
            "➡️ win+right": "win+right bas",

            # Yazı & Düzenleme Kısayolları
            "/ctrl_c": "ctrl+c bas",
            "📋 ctrl+c": "ctrl+c bas",
            "/ctrl_v": "ctrl+v bas",
            "📋 ctrl+v": "ctrl+v bas",
            "/ctrl_x": "ctrl+x bas",
            "✂️ ctrl+x": "ctrl+x bas",
            "↩️ ctrl+z": "ctrl+z bas",
            "↪️ ctrl+y": "ctrl+y bas",
            "/ctrl_a": "ctrl+a bas",
            "🅰️ ctrl+a": "ctrl+a bas",
            "/ctrl_s": "ctrl+s bas",
            "💾 ctrl+s": "ctrl+s bas",
            "🔍 ctrl+f": "ctrl+f bas",
            "🖨️ ctrl+p": "ctrl+p bas",
            "/enter": "enter bas",
            "↵ enter": "enter bas",
            "/alt_enter": "alt+enter bas",
            "⌨️ alt+enter": "alt+enter bas",
            "/tab": "tab bas",
            "↹ tab": "tab bas",
            "/esc": "escape bas",
            "⎋ escape": "escape bas",
            "/backspace": "backspace bas",
            "🔙 backspace": "backspace bas",
            "🗑️ delete": "delete bas",

            # Tarayıcı & Sekme Kısayolları
            "➕ ctrl+t": "ctrl+t bas",
            "❌ ctrl+w": "ctrl+w bas",
            "↩️ ctrl+shift+t": "ctrl+shift+t bas",
            "➡️ ctrl+tab": "ctrl+tab bas",
            "⬅️ ctrl+shift+tab": "ctrl+shift+tab bas",
            "🔄 f5": "f5 bas",
            "🌐 ctrl+n": "ctrl+n bas",
            "🕵️ ctrl+shift+n": "ctrl+shift+n bas",
            "🖥️ f11": "f11 bas",

            # Ekran & Medya Kontrolleri
            "/ekran": "ekran görüntüsü al",
            "📸 ekran görüntüsü al": "ekran görüntüsü al",
            "📸 ekran görüntüsü": "ekran görüntüsü al",
            "⏯️ oynat/duraklat": "müziği duraklat",
            "/ses_yukselt": "sesini artır",
            "🔊 ses yükselt (%10)": "sesini artır",
            "/ses_dusur": "sesini kıs",
            "🔉 ses düşür (%10)": "sesini kıs",
            "/ses_sessiz": "sesi kapat",
            "🔇 sesi sustur": "sesi kapat",
            "sonraki şarkı": "sonraki şarkı",
            "⏭️ sonraki şarkı": "sonraki şarkı",
            "önceki şarkı": "önceki şarkı",
            "⏮️ önceki şarkı": "önceki şarkı",

            # Sistem & Uygulamalar
            "/sistem": "sistem durumu nedir",
            "📊 sistem durumu": "sistem durumu nedir",
            "📊 sistem istatistikleri": "sistem durumu nedir",
            "/internet": "internet var mı",
            "🌐 i̇nternet kontrolü": "internet var mı",
            "🌐 internet kontrolü": "internet var mı",
            "/chrome": "chrome aç",
            "🌐 chrome'u aç": "chrome aç",
            "/cmd": "cmd aç",
            "💻 terminal / cmd aç": "cmd aç",
            "/indirilenler": "indirilenler klasörünü aç",
            "📂 i̇ndirilenler klasörü": "indirilenler klasörünü aç",
            "📂 indirilenler klasörü": "indirilenler klasörünü aç",
            "🧮 hesap makinesi aç": "hesap makinesi aç",
            "/kilitle": "bilgisayarı kilitle",
            "🔒 pc kilitle": "bilgisayarı kilitle",
            "/uyku": "bilgisayarı uykuya al",
            "🌙 uyku modu": "bilgisayarı uykuya al",

            # Brifing & Bilgi
            "/brifing": "sabah brifingi",
            "☀️ sabah brifingi": "sabah brifingi",
            "/hava": "hava durumu nedir",
            "🌦️ hava durumu": "hava durumu nedir",
            "/doviz": "dolar kaç TL",
            "💱 dolar & euro kuru": "dolar kaç TL",
            "/haberler": "son haberler neler",
            "📰 son haberler": "son haberler neler",
            "/hatirlatmalar": "hatırlatmalarımı göster",
            "⏰ hatırlatmalarım": "hatırlatmalarımı göster",
            "/notlar": "notlarımı göster",
            "📋 notlarım": "notlarımı göster",
        }

        if cmd_lower in quick_map:
            text = quick_map[cmd_lower]
        else:
            from features import custom_shortcuts
            ozel_komut = custom_shortcuts.komut_bul(text)
            if ozel_komut:
                text = ozel_komut

        # Bekleyen onay varken başka mesaj gelirse güvenlik gereği iptal et
        if chat_id in self.pending:
            self.pending.pop(chat_id, None)
            tg.send_message(token, chat_id,
                            "🛡️ Bekleyen onay, yeni bir komut girildiği için iptal edildi.")

        reply = self._process_command(tg, token, chat_id, text)
        if reply:
            tg.send_message(token, chat_id, reply)
            self.activity_signal.emit(text, reply)
            # Çok-turlu bağlam için turu kaydet (bir sonraki mesaj bunu görsün)
            self._gecmise_ekle(chat_id, "user", text)
            self._gecmise_ekle(chat_id, "assistant", reply)

    def _gecmise_ekle(self, chat_id, role, text):
        """Telegram sohbet geçmişine bir tur ekler (son 20 tur tutulur)."""
        gecmis = self.history.setdefault(chat_id, [])
        gecmis.append({"role": role, "text": text})
        if len(gecmis) > 20:
            self.history[chat_id] = gecmis[-20:]

    def _process_command(self, tg, token, chat_id, text):
        """Engine → (onay | doğrudan sonuç | LLM) akışı. None dönerse onay bekleniyor.
        allow_llm=True: LLM cevabı artık engine İÇİNDE üretilir (elle çağrı yok)."""
        # Çok-turlu bağlam: önceki turları engine'e geçir (masaüstüyle aynı davranış).
        # kanal=chat_id → dosya arama sonuçları telefona özel tutulur ("2'yi gönder"
        # masaüstünde yapılmış aramanın dosyasını göndermesin).
        engine_ctx = self.controller.engine.process(
            text, recent_context=self.history.get(chat_id), allow_llm=True,
            kanal=str(chat_id))

        if engine_ctx.security_level == "FORBIDDEN":
            return engine_ctx.security_message

        if engine_ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM"):
            self.pending[chat_id] = (text, time.time() + 60)
            tg.send_message(token, chat_id, engine_ctx.security_message,
                            reply_markup=tg.onay_butonlari())
            self.activity_signal.emit(text, "(onay bekleniyor — Telegram)")
            return None

        # 📸 Ekran görüntüsü istendiyse fotoğrafı da gönder
        if engine_ctx.execution_result and engine_ctx.execution_success:
            ss_yol = (engine_ctx.entities or {}).get('screenshot_path')
            if ss_yol:
                if tg.send_photo(token, chat_id, ss_yol, caption="🖥️ ULTRON — PC ekranı"):
                    self.activity_signal.emit(text, "(ekran görüntüsü Telegram'a gönderildi)")
                    return None  # foto zaten gitti, ayrıca metin gerekmez

        # Engine artık hem deterministik sonucu hem LLM cevabını final_output'ta hazırlar
        return engine_ctx.final_output or "Yanıt alınamadı."

    def _handle_voice_message(self, tg, token, chat_id, voice):
        """🎙️ Telegram sesli mesajı: indir → OGG/Opus çöz → Google STT → komut olarak işle."""
        import tempfile
        from features.speech import ogg_sesi_yaziya_cevir

        fp = tg.get_file_path(token, voice.get('file_id', ''))
        if not fp:
            tg.send_message(token, chat_id, "⚠️ Sesli mesaj alınamadı.")
            return

        ogg = os.path.join(tempfile.gettempdir(), f"ultron_voice_{voice.get('file_unique_id', 'x')}.ogg")
        try:
            if not tg.download_file(token, fp, ogg):
                tg.send_message(token, chat_id, "⚠️ Sesli mesaj indirilemedi.")
                return
            text = ogg_sesi_yaziya_cevir(ogg)
        finally:
            try:
                os.remove(ogg)
            except Exception:
                pass

        if not text:
            tg.send_message(token, chat_id, "🎙️ Sesli mesajı anlayamadım — tekrar dener misin?")
            return

        tg.send_message(token, chat_id, f"🎙️ Algılanan: \"{text}\"")
        self._handle_text_command(tg, token, chat_id, text)

    def _handle_incoming_file(self, tg, token, chat_id, msg):
        """📥 Telefondan gelen dosya/fotoğrafı PC'nin İndirilenler klasörüne kaydeder."""
        from features.file_finder import _gercek_yol

        doc = msg.get('document')
        if doc:
            file_id = doc.get('file_id', '')
            ad = doc.get('file_name') or f"ultron_dosya_{int(time.time())}"
        else:
            fotolar = msg.get('photo') or []
            if not fotolar:
                return
            file_id = fotolar[-1].get('file_id', '')   # en yüksek çözünürlük
            ad = f"ultron_foto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

        fp = tg.get_file_path(token, file_id)
        if not fp:
            tg.send_message(token, chat_id,
                            "⚠️ Dosya alınamadı (bot API sınırı 20MB — daha büyük olabilir).")
            return

        klasor = _gercek_yol('Downloads') or os.path.expanduser('~')
        hedef = os.path.join(klasor, ad)
        sayac = 1
        govde, uzanti = os.path.splitext(hedef)
        while os.path.exists(hedef):   # aynı isim varsa üzerine yazma
            hedef = f"{govde}_{sayac}{uzanti}"
            sayac += 1

        if tg.download_file(token, fp, hedef):
            boyut_mb = os.path.getsize(hedef) / (1024 * 1024)
            son_ad = os.path.basename(hedef)
            tg.send_message(token, chat_id,
                            f"📥 **İndirilenler'e kaydedildi:** `{son_ad}` ({boyut_mb:.1f} MB)")
            self.activity_signal.emit(f"(Telefondan dosya: {son_ad})",
                                      f"📥 İndirilenler'e kaydedildi ({boyut_mb:.1f} MB)")
        else:
            tg.send_message(token, chat_id, "⚠️ Dosya indirilemedi.")

    def _handle_callback(self, tg, token, cq):
        chat_id = ((cq.get('message') or {}).get('chat') or {}).get('id')
        data = cq.get('data', '')
        tg.answer_callback(token, cq.get('id', ''))
        if chat_id is None:
            return

        allowed = self._allowed_chat()
        if not allowed or str(chat_id) != allowed:
            return

        pending = self.pending.pop(chat_id, None)
        if not pending or time.time() > pending[1]:
            tg.send_message(token, chat_id, "⏱️ Onay süresi dolmuş — komut iptal edildi.")
            return

        cmd = pending[0]
        if data != 'ultron_confirm':
            tg.send_message(token, chat_id, "🛡️ **GÜVENLİK İPTALİ:** İşlem iptal edildi.")
            self.activity_signal.emit(cmd, "(Telegram'dan iptal edildi)")
            return

        # WhatsApp/e-posta/dosya gönderimi sistem_komutu_algila'da değil — birleşik
        # yürütücü. kanal=chat_id: "2'yi anneme mail at" seçimini telefonun kendi
        # arama listesinden çözer.
        from features.confirmed_executor import onayli_komut_yurut
        is_action, resp = onayli_komut_yurut(cmd, kanal=str(chat_id))
        final_msg = resp if (is_action and resp) else f"'{cmd}' komutu onaylandı ve yürütüldü."
        tg.send_message(token, chat_id, f"✅ **ONAYLANDI:** {final_msg}")
        self.activity_signal.emit(cmd, final_msg)


class FuncWorkerThread(QThread):
    """Bloklayan bir fonksiyonu arka planda çalıştırıp sonucunu sinyalle döner.
    (Onaylanan komutların yürütülmesi için — WhatsApp UIA beklemesi 20+ sn sürebilir.)"""
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.finished_signal.emit(self._func(*self._args, **self._kwargs))
        except Exception as e:
            self.error_signal.emit(str(e))


class ListenWorkerThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, device_index=None, pre_delay=0.0):
        super().__init__()
        self.device_index = device_index
        # Wake word dinleyicisinin mikrofonu bırakması için kısa bekleme
        # (aynı mikrofon iki akışa aynı anda verilemez).
        self.pre_delay = pre_delay

    def run(self):
        if not SPEECH_AVAILABLE:
            self.error_signal.emit("Sesli komut için gerekli kütüphaneler eksik.")
            return
        if self.pre_delay > 0:
            time.sleep(self.pre_delay)
        try:
            text = dinle_ve_yaziya_cevir(device_index=self.device_index)
            self.finished_signal.emit(text or "")
        except Exception as e:
            self.error_signal.emit(str(e))


class AssistantController:
    def __init__(self, cursor, conn, db_manager, config):
        self.cursor = cursor
        self.conn = conn
        self.db = db_manager
        self.config = config
        self.provider = config.get('ai_provider', 'ollama')
        self.ai_context = {}
        self.engine = UltronCoreEngine(db_manager=db_manager, cursor=cursor, conn=conn, config=config)

    def log(self, soru, cevap):
        try:
            self.db.log_conversation(soru, cevap)
        except Exception as e:
            print(f"[TAU] Sohbet loglanamadı: {e}")
        # 🧠 Öğrenme arşivindeki kaydın cevabını tamamla. Engine turu kaydettiğinde
        # masaüstü cevabı HENÜZ ÜRETİLMEMİŞTİ (streaming) — cevapsız bir arşiv,
        # "geçen sefer ne demiştin" sorusunu cevaplayamaz.
        try:
            from features import chat_learning
            chat_learning.cevabi_tamamla("desktop", soru, cevap)
        except Exception as e:
            print(f"[ULTRON Ogrenme] Cevap arsive yazilamadi: {e}")

    def get_reminders(self):
        self.cursor.execute("""
            SELECT id, metin, hedef_tarih, durum FROM hatirlatmalar
            ORDER BY olusturma_tarihi DESC LIMIT 50
        """)
        return [
            {"id": row[0], "text": row[1], "time": row[2], "completed": row[3] == "tamamlandi"}
            for row in self.cursor.fetchall()
        ]

    def add_reminder(self, text):
        parsed = hatirlatma_algila(text)
        if not parsed or parsed.get('tip') != 'hatirlatma':
            # Hatırlatma ekranından "yarın 14:00 toplantı" gibi anahtar kelimesiz
            # girilirse "hatırlat" ekleyerek tekrar dene
            parsed = hatirlatma_algila(text + " hatırlat")
        if not parsed or parsed.get('tip') != 'hatirlatma':
            return False
        return hatirlatma_kaydet(self.cursor, self.conn, parsed)

    def toggle_reminder(self, rem_id, completed):
        yeni_durum = "tamamlandi" if completed else "bekliyor"
        self.cursor.execute("UPDATE hatirlatmalar SET durum = ? WHERE id = ?", (yeni_durum, rem_id))
        self.conn.commit()

    def delete_reminder(self, rem_id):
        self.cursor.execute("DELETE FROM hatirlatmalar WHERE id = ?", (rem_id,))
        self.conn.commit()

    def get_statistics(self):
        """İstatistik sayfası için tüm metrikleri toplar."""
        GUN_KISA = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
        c = self.cursor
        stats = {}

        c.execute("SELECT COUNT(*) FROM sohbet_gecmisi")
        stats['toplam_konusma'] = c.fetchone()[0]

        bugun = datetime.now().strftime('%Y-%m-%d')
        c.execute("SELECT COUNT(*) FROM sohbet_gecmisi WHERE tarih LIKE ?", (bugun + '%',))
        stats['bugun_mesaj'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM hatirlatmalar WHERE durum = 'bekliyor'")
        stats['bekleyen_hatirlatma'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM memory")
        stats['hafiza_kaydi'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM custom_routines")
        stats['ozel_rutin'] = c.fetchone()[0]

        try:
            from features.actions.whatsapp_control import kisiler_yukle
            from features.email_control import email_kisiler
            stats['rehber_kisi'] = len(kisiler_yukle()) + len(email_kisiler())
        except Exception:
            stats['rehber_kisi'] = 0

        # Son 7 gün aktivite (bugün dahil)
        aktivite = []
        for i in range(6, -1, -1):
            gun = datetime.now() - timedelta(days=i)
            c.execute("SELECT COUNT(*) FROM sohbet_gecmisi WHERE tarih LIKE ?",
                      (gun.strftime('%Y-%m-%d') + '%',))
            aktivite.append((GUN_KISA[gun.weekday()], c.fetchone()[0]))
        stats['gunluk_aktivite'] = aktivite

        # 🧠 Öğrenme katmanı — ayrı veritabanında (ogrenme.db) yaşar.
        # Örüntüler önbelleklidir; bu çağrı her yenilemede SQL taraması yapmaz.
        try:
            from features import chat_learning, suggestions
            ogrenme = chat_learning.istatistik()
            ogrenme['oneri'] = suggestions.durum(db_cursor=c)
            stats['ogrenme'] = ogrenme
        except Exception as e:
            print(f"[Ultron Stats] Ogrenme metrikleri alinamadi: {e}")
            stats['ogrenme'] = {}

        stats['mood'] = self.get_mood_stats()
        return stats

    def get_chat_history(self, limit=15):
        """Son konuşma çiftlerini (soru, cevap, tarih) kronolojik sırayla döner."""
        self.cursor.execute("""
            SELECT kullanici_girisi, sistem_cevabi, tarih FROM sohbet_gecmisi
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        return list(reversed(self.cursor.fetchall()))

    def get_due_reminders(self):
        """Zamanı gelmiş ve henüz bildirilmemiş hatırlatmaları döner."""
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute("""
            SELECT id, metin, hedef_tarih FROM hatirlatmalar
            WHERE durum = 'bekliyor' AND hedef_tarih IS NOT NULL AND hedef_tarih <= ?
        """, (now_str,))
        return self.cursor.fetchall()

    def mark_reminder_notified(self, rem_id):
        """Bildirimi yapılan hatırlatmayı tamamlandı olarak işaretler (tekrar tetiklenmesin)."""
        self.cursor.execute("UPDATE hatirlatmalar SET durum = 'tamamlandi' WHERE id = ?", (rem_id,))
        self.conn.commit()

    def get_upcoming_reminders(self, lead_minutes: int = 10):
        """Önümüzdeki `lead_minutes` dakika içinde zamanı gelecek (henüz gelmemiş)
        hatırlatmalar → proaktif 'yaklaşıyor' uyarısı için. (id, metin, hedef_tarih)."""
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        ufuk = (now + timedelta(minutes=lead_minutes)).strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute("""
            SELECT id, metin, hedef_tarih FROM hatirlatmalar
            WHERE durum = 'bekliyor' AND hedef_tarih IS NOT NULL
              AND hedef_tarih > ? AND hedef_tarih <= ?
        """, (now_str, ufuk))
        return self.cursor.fetchall()

    def get_mood_stats(self):
        bir_hafta_once = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute("""
            SELECT ruh_hali, COUNT(*) FROM ruh_hali_gecmisi
            WHERE tarih >= ? GROUP BY ruh_hali
        """, (bir_hafta_once,))
        counts = {row[0]: row[1] for row in self.cursor.fetchall()}
        total = sum(counts.values()) or 1
        
        pos = round((counts.get('pozitif', 0) / total) * 100, 1)
        neu = round((counts.get('nötr', 0) / total) * 100, 1)
        neg = round((counts.get('negatif', 0) / total) * 100, 1)
        
        return {'pozitif': pos, 'nötr': neu, 'negatif': neg}

    def get_mood_logs(self):
        self.cursor.execute("""
            SELECT ruh_hali, mesaj, tarih FROM ruh_hali_gecmisi
            ORDER BY tarih DESC LIMIT 15
        """)
        return [f"[{r[2][:16]}] ({r[0].upper()}) {r[1]}" for r in self.cursor.fetchall()]

    def get_memories(self):
        rows = self.db.list_memory()
        return [{"id": idx, "key": k, "value": v, "category": c or "Genel"} for idx, (k, v, c) in enumerate(rows)]

    def add_memory(self, key, value, category="Genel"):
        self.db.add_memory(key, value, category)

    def delete_memory(self, key):
        self.db.delete_memory(key)


class TauMainWindow(QMainWindow):
    def __init__(self, cursor, conn, db_manager, config):
        super().__init__()
        self.setWindowTitle("ULTRON NEURAL AI CORE")
        self.resize(1100, 750)
        self.setMinimumSize(850, 600)
        
        self.setStyleSheet(MAIN_STYLESHEET)
        
        self.db = db_manager
        self.db_manager = db_manager
        self.controller = AssistantController(cursor, conn, db_manager, config)
        self.ai_worker = None
        self.listen_worker = None
        self.engine_worker = None
        # Çalışan thread'lere referans tutulmazsa GC "Destroyed while running" crash'i üretir
        self._active_workers = []

        # Çok turlu sohbet geçmişi ve bekleyen güvenlik onayı — lazy hasattr yerine baştan tanımlı
        self.recent_chat_history = []
        self.pending_confirmation_cmd = None

        # Onay kartı zaman aşımı: süresi dolan bekleyen komut otomatik iptal edilir
        self.pending_confirmation_timer = QTimer(self)
        self.pending_confirmation_timer.setSingleShot(True)
        self.pending_confirmation_timer.timeout.connect(self._expire_pending_confirmation)

        # 🎯 Odak modu (pomodoro) durumu
        self._focus_qtimer = None
        self._focus_end_time = None
        self._focus_prev_volume = None
        self._focus_minutes = 0

        # Streaming durumu
        self._stream_bubble = None
        self._stream_parts = []
        self._stream_dirty = False
        self._stream_timer = None

        self.init_ui()
        self.refresh_all_data()

        # 🔴 System Tray: pencere kapansa da Ultron arka planda yaşar
        self._tray_notice_shown = False
        self._quitting = False
        self.app_icon = build_ultron_icon()
        self.setWindowIcon(self.app_icon)
        self._init_tray()

        # ⏰ Otonom döngü: 30 saniyede bir hatırlatmalar + zamanlanmış görevler
        try:
            if zamanlayici.varsayilanlari_kur(self.controller.cursor, self.controller.conn):
                print("[TAU] Varsayılan zamanlanmış görevler kuruldu (08:00 brifing, 22:00 rapor)")
        except Exception as e:
            print(f"[TAU] Zamanlanmış görev tablosu hazırlanamadı: {e}")

        # Proaktif ön-uyarı verilen hatırlatma id'leri (oturum içi, tekrar uyarmasın)
        self._prenotified_reminders = set()

        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._autonomous_tick)
        self.reminder_timer.start(30_000)
        QTimer.singleShot(3_000, self._autonomous_tick)

        # 📱 Telegram köprüsü (token yapılandırılmışsa)
        self.telegram_worker = None
        self._start_telegram_bridge()

        # 🎙️ "Hey Ultron" wake word (ayarlardan açıksa ve model kuruluysa)
        self.wake_worker = None
        self._start_wake_word()

    def init_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Component
        self.sidebar = SidebarWidget()
        self.sidebar.page_changed.connect(self.switch_page)
        self.sidebar.new_chat_requested.connect(self.start_new_chat)

        provider_name = PROVIDER_LABELS.get(self.controller.provider, self.controller.provider)
        model_name = self.controller.config.get('ollama_model', '') if self.controller.provider == 'ollama' else ''
        self.sidebar.update_provider_status(provider_name, model_name)

        main_layout.addWidget(self.sidebar)

        # 2. Main Pages Container (QStackedWidget)
        self.pages = QStackedWidget()

        # Page 0: Chat
        self.chat_view = ChatViewWidget()
        self.chat_view.message_sent.connect(self.on_user_send_message)
        self.chat_view.mic_clicked.connect(self.on_mic_clicked)
        self.pages.addWidget(self.chat_view)

        # Page 1: Reminders
        self.reminders_view = RemindersViewWidget()
        self.reminders_view.add_reminder_signal.connect(self.on_add_reminder)
        self.reminders_view.toggle_complete_signal.connect(self.on_toggle_reminder)
        self.reminders_view.delete_reminder_signal.connect(self.on_delete_reminder)
        self.pages.addWidget(self.reminders_view)

        # Page 2: Memory
        self.memory_view = MemoryViewWidget()
        self.memory_view.add_memory_signal.connect(self.on_add_memory)
        self.memory_view.delete_memory_signal.connect(self.on_delete_memory)
        self.pages.addWidget(self.memory_view)

        # Page 3: Mood
        self.mood_view = MoodViewWidget()
        self.pages.addWidget(self.mood_view)

        # Page 4: Analytics — gerçek istatistik paneli
        self.stats_view = StatsViewWidget()
        self.pages.addWidget(self.stats_view)

        # Page 5: Settings
        self.settings_view = SettingsViewWidget(self.controller.config)
        self.settings_view.config_saved.connect(self.on_save_config)
        self.pages.addWidget(self.settings_view)

        # Page 6: Ultron Focus Mode (Full Screen Holographic Mode)
        self.ultron_focus_view = UltronFocusViewWidget()
        self.ultron_focus_view.message_sent.connect(self.on_user_send_message)
        self.ultron_focus_view.switch_mode_requested.connect(lambda: self.switch_page(0))
        self.pages.addWidget(self.ultron_focus_view)

        # Page 7: Dynamic Mode & Routine Manager
        self.modes_view = ModesViewWidget(self.db)
        self.pages.addWidget(self.modes_view)

        main_layout.addWidget(self.pages, 1)

        # 💾 Önceki oturumların sohbet geçmişini yükle (kalıcılık)
        now_str = datetime.now().strftime("%H:%M")
        try:
            history = self.controller.get_chat_history(limit=15)
        except Exception as e:
            print(f"[TAU] Sohbet geçmişi yüklenemedi: {e}")
            history = []
        for soru, cevap, tarih in history:
            ts = (tarih or "")[11:16]  # 'YYYY-MM-DD HH:MM:SS' → 'HH:MM'
            self.chat_view.add_message("user", soru, ts)
            self.chat_view.add_message("assistant", cevap, ts)
        if history:
            self.chat_view.add_message(
                "assistant",
                "— ⚡ **YENİ OTURUM** — (yukarısı önceki oturumların geçmişidir)",
                now_str
            )

        # Initial Welcome Message in Chat & Focus View
        welcome = "Ben **ULTRON Nöral Çekirdeği**. Sistem protokolleri aktif. Nasıl bir komut vermek istersiniz?"
        self.chat_view.add_message("assistant", welcome, now_str)
        self.ultron_focus_view.add_message("assistant", welcome)

    def switch_page(self, index: int):
        if index == 6:
            self.sidebar.hide()
        else:
            self.sidebar.show()
        self.pages.setCurrentIndex(index)
        self.refresh_all_data()

    def start_new_chat(self):
        self.pages.setCurrentIndex(0)
        self.controller.ai_context = {}
        self.recent_chat_history = []
        self.pending_confirmation_cmd = None
        self.pending_confirmation_timer.stop()
        now_str = datetime.now().strftime("%H:%M")
        self.chat_view.add_message("assistant", "⚡ Yeni Ultron sohbet oturumu başlatıldı.", now_str)

    def refresh_all_data(self):
        # Reminders
        rems = self.controller.get_reminders()
        self.reminders_view.set_reminders(rems)

        # Memories
        mems = self.controller.get_memories()
        self.memory_view.set_memories(mems)

        # Mood
        m_stats = self.controller.get_mood_stats()
        m_logs = self.controller.get_mood_logs()
        self.mood_view.update_stats(m_stats, m_logs)

        # İstatistikler
        try:
            self.stats_view.update_stats(self.controller.get_statistics())
        except Exception as e:
            print(f"[TAU] İstatistikler güncellenemedi: {e}")

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    def _post_assistant(self, text: str, user_prompt: str = None, speak: bool = True):
        """Asistan mesajını her iki görünüme basar ve geçmişe ekler.
        user_prompt verilirse alışveriş kalıcı sohbet geçmişine (SQLite) de yazılır.
        speak=True ve TTS açıksa cevap sesli okunur."""
        now_str = datetime.now().strftime("%H:%M")
        self.chat_view.add_message("assistant", text, now_str)
        self.ultron_focus_view.add_message("assistant", text)
        self.recent_chat_history.append({"role": "assistant", "text": text})
        self._trim_history()
        if user_prompt is not None:
            self.controller.log(user_prompt, text)
        if speak:
            self._speak(text)

    def _speak(self, text: str):
        """TTS açıksa cevabı arka planda seslendirir (UI bloklamaz).
        Konuşma sırasında wake word duraklatılır — Ultron kendi sesindeki
        'Ultron' kelimesiyle kendini uyandırmasın."""
        if not SPEECH_AVAILABLE or not self.controller.config.get('tts_enabled'):
            return
        engine = self.controller.config.get('tts_engine', 'gtts')

        def _do_speak():
            if self.wake_worker is not None:
                self.wake_worker.paused = True
            try:
                seslendir(text, engine=engine)
            finally:
                if self.wake_worker is not None:
                    self.wake_worker.paused = False

        worker = FuncWorkerThread(_do_speak)
        self._track_worker(worker)
        worker.start()

    def _trim_history(self):
        """Sohbet geçmişi tamponunun sınırsız büyümesini engeller."""
        if len(self.recent_chat_history) > 20:
            self.recent_chat_history = self.recent_chat_history[-20:]

    def _set_ai_state(self, state: str):
        self.chat_view.set_ai_state(state)
        self.ultron_focus_view.set_ai_state(state)

    def _track_worker(self, worker):
        """Thread nesnesine referans tutar; bitince listeden düşer (GC crash koruması)."""
        self._active_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._untrack_worker(w))

    def _untrack_worker(self, worker):
        try:
            self._active_workers.remove(worker)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Güvenlik Onayı
    # ------------------------------------------------------------------
    def _execute_pending_confirmation(self):
        cmd_to_run = self.pending_confirmation_cmd
        self.pending_confirmation_cmd = None
        self.pending_confirmation_timer.stop()
        if not cmd_to_run:
            return

        # Yürütme worker thread'de: WhatsApp gönderimi gibi işlemler UIA beklemesi
        # nedeniyle uzun sürebilir — UI donmamalı.
        self._set_ai_state("thinking")

        def _on_done(result):
            is_action, resp = result if isinstance(result, tuple) else (False, None)
            final_msg = resp if (is_action and resp) else f"'{cmd_to_run}' komutu onaylandı ve yürütüldü."
            self._post_assistant(f"✅ **ONAYLANDI:** {final_msg}", user_prompt=cmd_to_run)
            self._set_ai_state("idle")

        def _on_err(err):
            self._post_assistant(f"⚠️ Onaylanan komut yürütülürken hata: {err}")
            self._set_ai_state("idle")

        # Onaylı komutu DOĞRU executor'a yönlendir: WhatsApp/e-posta gönderimi
        # sistem_komutu_algila'da değil — birleşik yürütücü halleder.
        from features.confirmed_executor import onayli_komut_yurut
        worker = FuncWorkerThread(onayli_komut_yurut, cmd_to_run)
        worker.finished_signal.connect(_on_done)
        worker.error_signal.connect(_on_err)
        self._track_worker(worker)
        worker.start()

    def _cancel_pending_confirmation(self, reason_msg: str):
        self.pending_confirmation_cmd = None
        self.pending_confirmation_timer.stop()
        self._post_assistant(reason_msg)
        self._set_ai_state("idle")

    def _expire_pending_confirmation(self):
        if self.pending_confirmation_cmd:
            self._cancel_pending_confirmation(
                "⏱️ **GÜVENLİK ZAMAN AŞIMI:** Onay 60 saniye içinde verilmediği için bekleyen işlem iptal edildi."
            )

    # ------------------------------------------------------------------
    # Mesaj Akışı
    # ------------------------------------------------------------------
    def on_user_send_message(self, text: str):
        now_str = datetime.now().strftime("%H:%M")
        self.chat_view.add_message("user", text, now_str)
        self.ultron_focus_view.add_message("user", text)

        # Hızlı susturma: TTS'i anında keser, pipeline'a girmez
        if text.lower().strip().rstrip('.!') in ('sus', 'sustur', 'sus ultron', 'kes sesini', 'sessiz ol'):
            konusmayi_durdur()
            self._post_assistant("🤫 Sustum.", speak=False)
            return

        # 0. Bekleyen güvenlik onayı: SADECE tam eşleşme kabul edilir.
        #    Başka bir mesaj gelirse bekleyen komut güvenlik gereği iptal edilir.
        if self.pending_confirmation_cmd:
            text_exact = text.lower().strip().rstrip(".!")
            if text_exact in CONFIRM_PHRASES:
                self._execute_pending_confirmation()
                return
            self._cancel_pending_confirmation(
                "🛡️ **GÜVENLİK:** Bekleyen onay, yeni bir komut girildiği için iptal edildi."
            )
            # iptalden sonra yeni mesaj normal akışta işlenmeye devam eder

        # 1. Çok turlu sohbet geçmişine ekle
        self.recent_chat_history.append({"role": "user", "text": text})
        self._trim_history()

        self._set_ai_state("thinking")

        # 2. Engine'i worker thread'de çalıştır (web araması / uygulama tarama UI'ı dondurmasın)
        worker = EngineWorkerThread(self.controller.engine, text, list(self.recent_chat_history))
        worker.finished_signal.connect(self._on_engine_result)
        worker.error_signal.connect(self.on_ai_error)
        self._track_worker(worker)
        self.engine_worker = worker
        worker.start()

    def _on_engine_result(self, text: str, engine_ctx):
        # 3. Güvenlik onayı / yasak komut kontrolü
        if engine_ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
            if engine_ctx.security_level == "FORBIDDEN":
                self._post_assistant(engine_ctx.security_message)
                self._set_ai_state("idle")
                return

            self.pending_confirmation_cmd = text
            self.pending_confirmation_timer.start(CONFIRMATION_TIMEOUT_MS)

            def _on_confirm():
                if self.pending_confirmation_cmd:
                    self._execute_pending_confirmation()

            def _on_cancel():
                if self.pending_confirmation_cmd:
                    self._cancel_pending_confirmation(
                        "🛡️ **GÜVENLİK İPTALİ:** İşlem kullanıcı tarafından iptal edildi."
                    )

            self.chat_view.add_confirmation_card(engine_ctx.security_message, _on_confirm, _on_cancel)
            self.ultron_focus_view.add_confirmation_card(engine_ctx.security_message, _on_confirm, _on_cancel)
            self._set_ai_state("idle")
            return

        # 3.5 🎯 Odak modu istekleri (zamanlayıcı ana pencerede yaşar)
        focus_action = (engine_ctx.entities or {}).get('focus_action')
        if focus_action:
            self._handle_focus_action(focus_action,
                                      (engine_ctx.entities or {}).get('focus_minutes', 25),
                                      text)
            return

        # 4. Engine doğrudan sonuç ürettiyse (sistem komutu, web araması, hatırlatma vb.)
        if engine_ctx.execution_result and engine_ctx.execution_success:
            # 📸 "ekran görüntüsü al ve telegrama gönder" → foto telefona da gitsin
            ss_yol = (engine_ctx.entities or {}).get('screenshot_path')
            if ss_yol and 'telegram' in text.lower():
                self._telegram_foto_gonder(ss_yol)
            self._post_assistant(engine_ctx.execution_result, user_prompt=text)
            self._set_ai_state("idle")
            self.refresh_all_data()
            return

        # 5. LLM'e düş: zenginleştirilmiş prompt + çok turlu bağlam
        provider = self.controller.provider
        enriched_prompt = engine_ctx.enriched_prompt or text

        # Ollama → STREAMING: cevap kelime kelime akar
        if provider == 'ollama':
            self._start_streaming_reply(text, enriched_prompt)
            return

        ctx = self.controller.ai_context.get(provider)
        worker = AIWorkerThread(provider, enriched_prompt, self.controller.config, context=ctx)
        worker.finished_signal.connect(lambda ans, updated_ctx: self.on_ai_response(text, ans, updated_ctx))
        worker.error_signal.connect(self.on_ai_error)
        self._track_worker(worker)
        self.ai_worker = worker
        worker.start()

    # ------------------------------------------------------------------
    # Streaming (Ollama)
    # ------------------------------------------------------------------
    def _start_streaming_reply(self, user_text: str, prompt: str):
        self._set_ai_state("speaking")
        now_str = datetime.now().strftime("%H:%M")
        self._stream_bubble = self.chat_view.add_message("assistant", "▌", now_str)
        self._stream_parts = []
        self._stream_dirty = False

        # Her token'da HTML render pahalı — 150ms'de bir topluca güncelle
        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._flush_stream)
        self._stream_timer.start(150)

        worker = StreamWorkerThread(prompt, self.controller.config)
        worker.token_signal.connect(self._on_stream_token)
        worker.finished_signal.connect(lambda full: self._on_stream_done(user_text, full))
        worker.error_signal.connect(self._on_stream_error)
        self._track_worker(worker)
        self.ai_worker = worker
        worker.start()

    def _on_stream_token(self, token: str):
        self._stream_parts.append(token)
        self._stream_dirty = True

    def _flush_stream(self):
        if self._stream_dirty and self._stream_bubble is not None:
            self._stream_dirty = False
            self._stream_bubble.update_text(''.join(self._stream_parts) + " ▌")
            self.chat_view.scroll_to_bottom()

    def _on_stream_done(self, user_text: str, full: str):
        self._stream_timer.stop()
        if self._stream_bubble is not None:
            self._stream_bubble.update_text(full)
            self.chat_view.scroll_to_bottom()
        self._stream_bubble = None

        # Balonu zaten canlı bastık — _post_assistant'ın yeniden basmaması için
        # geçmiş/log/TTS işlemlerini burada elle yapıyoruz
        self.ultron_focus_view.add_message("assistant", full)
        self.recent_chat_history.append({"role": "assistant", "text": full})
        self._trim_history()
        self.controller.log(user_text, full)
        self._speak(full)

        QTimer.singleShot(800, lambda: self._set_ai_state("idle"))
        self.refresh_all_data()

    def _on_stream_error(self, err: str):
        self._stream_timer.stop()
        if self._stream_bubble is not None:
            self._stream_bubble.update_text(f"⚠️ {err}")
        self._stream_bubble = None
        self._set_ai_state("idle")

    def on_ai_response(self, user_prompt: str, ai_answer: str, updated_context):
        self._set_ai_state("speaking")

        self.controller.ai_context[self.controller.provider] = updated_context
        self._post_assistant(ai_answer, user_prompt=user_prompt)

        QTimer.singleShot(1500, lambda: self._set_ai_state("idle"))
        self.refresh_all_data()

    # ------------------------------------------------------------------
    # 🎯 Odak Modu (Pomodoro)
    # ------------------------------------------------------------------
    def _handle_focus_action(self, action: str, minutes: int, user_text: str):
        if action == 'cancel':
            if self._focus_qtimer is not None:
                self._focus_qtimer.stop()
                self._focus_qtimer = None
                self._focus_restore_volume()
                self._post_assistant("🎯 Odak modu iptal edildi — ses eski seviyesine döndü.",
                                     user_prompt=user_text)
            else:
                self._post_assistant("ℹ️ Aktif bir odak modu yok.", user_prompt=user_text)
            self._set_ai_state("idle")
            return

        if action == 'status':
            if self._focus_qtimer is not None and self._focus_end_time:
                kalan = max(0, int((self._focus_end_time - datetime.now()).total_seconds() // 60))
                self._post_assistant(f"🎯 Odak modu aktif — **{kalan} dakika** kaldı. Devam! 💪",
                                     user_prompt=user_text)
            else:
                self._post_assistant("ℹ️ Aktif bir odak modu yok. Başlatmak için: `25 dakika odaklan`",
                                     user_prompt=user_text)
            self._set_ai_state("idle")
            return

        # start
        minutes = max(1, min(180, int(minutes)))
        if self._focus_qtimer is not None:
            self._focus_qtimer.stop()

        try:
            self._focus_prev_volume = sistem_sesi_getir()
            sistem_sesi_kontrol("set", 20)
            ses_notu = f"🔉 Ses %{self._focus_prev_volume} → %20'ye alındı."
        except Exception:
            self._focus_prev_volume = None
            ses_notu = ""

        self._focus_minutes = minutes
        self._focus_end_time = datetime.now() + timedelta(minutes=minutes)
        self._focus_qtimer = QTimer(self)
        self._focus_qtimer.setSingleShot(True)
        self._focus_qtimer.timeout.connect(self._focus_finished)
        self._focus_qtimer.start(minutes * 60_000)

        self._post_assistant(
            f"🎯 **ODAK MODU BAŞLADI — {minutes} dakika**\n{ses_notu}\n"
            f"Süre dolunca haber vereceğim. (İptal: `odaklanmayı iptal et` · Durum: `odak durumu`)",
            user_prompt=user_text)
        self._set_ai_state("idle")

    def _focus_restore_volume(self):
        if self._focus_prev_volume is not None:
            try:
                sistem_sesi_kontrol("set", self._focus_prev_volume)
            except Exception:
                pass
            self._focus_prev_volume = None
        self._focus_end_time = None

    def _focus_finished(self):
        self._focus_qtimer = None
        dakika = self._focus_minutes
        self._focus_restore_volume()
        msg = (f"🎯 **ODAK SÜRESİ TAMAMLANDI!** {dakika} dakika kesintisiz odaklandın 💪\n"
               f"🔊 Ses eski seviyesine döndü. Kısa bir mola hak ettin.")
        self._post_assistant(msg)
        self._show_system_notification("ULTRON Odak Modu", f"{dakika} dakika tamamlandı! Mola zamanı.")
        self._telegram_bildir(msg)

    # ------------------------------------------------------------------
    # Otonom Döngü: Hatırlatmalar + Zamanlanmış Görevler
    # ------------------------------------------------------------------
    def _autonomous_tick(self):
        self.check_upcoming_reminders()   # önce "yaklaşıyor" uyarısı
        self.check_due_reminders()
        self.check_scheduled_tasks()
        self.check_file_index()

    def check_file_index(self):
        """
        📇 Dosya indeksini taze tutar: ilk açılışta kurar, sonra 6 saatte bir yeniler.
        Tarama arka planda çalışır (UI donmaz) ve aynı anda yalnızca bir kez döner.
        """
        if getattr(self, '_indeks_calisiyor', False):
            return
        try:
            from features import file_index
            sayi, son = file_index.indeks_durumu()
            if sayi:
                if not son:
                    return
                yas = (datetime.now() - datetime.fromisoformat(son)).total_seconds()
                if yas < 6 * 3600:
                    return
        except Exception as e:
            print(f"[Dosya İndeksi] Durum okunamadı: {e}")
            return

        self._indeks_calisiyor = True

        def _tara():
            from features import file_index
            return file_index.indeksi_yenile()

        self._indeks_worker = FuncWorkerThread(_tara)
        self._indeks_worker.finished_signal.connect(self._on_indeks_bitti)
        self._indeks_worker.error_signal.connect(lambda e: setattr(self, '_indeks_calisiyor', False))
        self._indeks_worker.start()

    def _on_indeks_bitti(self, sonuc):
        self._indeks_calisiyor = False
        try:
            sayi, sure, _gizli = sonuc
            print(f"[Dosya İndeksi] {sayi:,} dosya indekslendi ({sure} sn)")
        except Exception:
            pass

    def check_upcoming_reminders(self):
        """Yaklaşan hatırlatmalar için PROAKTİF ön-uyarı ("toplantıya 10 dk kaldı").
        Her hatırlatma için ön-uyarı yalnızca BİR kez verilir (bellekteki set)."""
        lead = int(self.controller.config.get('reminder_lead_minutes', 10) or 10)
        if lead <= 0:
            return
        try:
            yaklasan = self.controller.get_upcoming_reminders(lead)
        except Exception as e:
            print(f"[TAU] Yaklaşan hatırlatma kontrolü hatası: {e}")
            return

        for rem_id, metin, hedef in yaklasan:
            if rem_id in self._prenotified_reminders:
                continue
            self._prenotified_reminders.add(rem_id)
            try:
                kalan = datetime.strptime(hedef, '%Y-%m-%d %H:%M:%S') - datetime.now()
                dk = max(1, round(kalan.total_seconds() / 60))
            except Exception:
                dk = lead
            msg = f"🔔 **YAKLAŞIYOR ({dk} dk):** {metin}"
            self._post_assistant(msg)
            self._show_system_notification("ULTRON — Yaklaşan Hatırlatma", f"{dk} dk: {metin}")
            self._telegram_bildir(msg)

    def check_scheduled_tasks(self):
        """Saati gelen zamanlanmış görevleri (sabah brifingi, akşam raporu vb.) çalıştırır."""
        try:
            due = zamanlayici.zamani_gelenler(self.controller.cursor)
        except Exception as e:
            print(f"[TAU] Zamanlanmış görev kontrolü hatası: {e}")
            return

        for gorev_id, saat, komut in due:
            # ÖNCE işaretle — worker sürerken timer tekrar tetiklemesin
            try:
                zamanlayici.calisti_isaretle(self.controller.cursor, self.controller.conn, gorev_id)
            except Exception:
                continue
            self._run_scheduled_task(saat, komut)

    def _run_scheduled_task(self, saat: str, komut: str):
        """Görevi worker'da engine'den geçirir; sonucu masaüstüne + Telegram'a basar."""
        def _do():
            # allow_llm=True: "her sabah bana motivasyon sözü söyle" gibi LLM gerektiren
            # zamanlanmış görevler artık gerçek cevap üretir (önceden sessizce boş dönüyordu).
            ctx = self.controller.engine.process(komut, allow_llm=True)
            if ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
                return f"⏭️ Zamanlanmış görev \"{komut}\" onay gerektirdiği için atlandı (güvenlik)."
            if ctx.final_output:
                return ctx.final_output
            return f"ℹ️ Zamanlanmış görev \"{komut}\" sonuç üretmedi."

        def _on_done(result):
            msg = f"⏰ **ZAMANLANMIŞ GÖREV ({saat})**\n\n{result}"
            self._post_assistant(msg, user_prompt=f"[Zamanlanmış {saat}] {komut}")
            self._telegram_bildir(msg)
            self.refresh_all_data()

        worker = FuncWorkerThread(_do)
        worker.finished_signal.connect(_on_done)
        worker.error_signal.connect(lambda e: print(f"[TAU] Zamanlanmış görev hatası: {e}"))
        self._track_worker(worker)
        worker.start()

    def check_due_reminders(self):
        """Zamanı gelen hatırlatmaları bildirir ve tamamlandı işaretler."""
        try:
            due = self.controller.get_due_reminders()
        except Exception as e:
            print(f"[TAU] Hatırlatma kontrolü hatası: {e}")
            return

        if not due:
            return

        for rem_id, metin, _hedef in due:
            try:
                self.controller.mark_reminder_notified(rem_id)
            except Exception as e:
                print(f"[TAU] Hatırlatma güncellenemedi: {e}")
                continue
            self._post_assistant(f"⏰ **HATIRLATMA ZAMANI GELDİ:** {metin}")
            self._show_system_notification("ULTRON Hatırlatma", metin)
            self._telegram_bildir(f"⏰ **HATIRLATMA:** {metin}")

        self.refresh_all_data()

    def _show_system_notification(self, title: str, body: str):
        """Windows toast bildirimi dener; winotify yoksa tray balonuna, o da yoksa sese düşer."""
        try:
            from winotify import Notification
            toast = Notification(app_id="ULTRON Neural Core", title=title, msg=body)
            toast.show()
            return
        except Exception:
            pass
        if getattr(self, 'tray', None) and self.tray.isVisible():
            self.tray.showMessage(title, body, QSystemTrayIcon.Information, 6000)
        else:
            QApplication.beep()

    # ------------------------------------------------------------------
    # Wake Word ("Hey Ultron")
    # ------------------------------------------------------------------
    def _start_wake_word(self):
        """Ayarlarda açıksa ve model kuruluysa dinleyiciyi (yeniden) başlatır."""
        if self.wake_worker is not None:
            self.wake_worker.stop()
            self.wake_worker = None

        if not self.controller.config.get('wake_enabled'):
            return
        if not SPEECH_AVAILABLE:
            return

        worker = WakeWordThread(WAKE_MODEL_PATH,
                                device_index=self.controller.config.get('mic_device_index', -1))
        worker.wake_detected.connect(self._on_wake_detected)
        worker.status_signal.connect(lambda s: self._post_assistant(s, speak=False))
        self._track_worker(worker)
        self.wake_worker = worker
        worker.start()

    def _on_wake_detected(self):
        """'Hey Ultron' duyuldu → uyarı sesi + komut dinlemeye geç."""
        QApplication.beep()
        konusmayi_durdur()  # konuşuyorsa sussun, kullanıcı bir şey diyecek
        self.chat_view.set_ai_state("listening")
        self.ultron_focus_view.set_ai_state("listening")

        # Komut dinlenirken wake dinleyicisi duraksın (aynı anda iki niyet olmasın)
        # ve mikrofonu bıraksın → STT için 0.7s ön-gecikme.
        if self.wake_worker is not None:
            self.wake_worker.paused = True

        self.listen_worker = ListenWorkerThread(
            device_index=self.controller.config.get('mic_device_index', -1),
            pre_delay=0.7)
        self.listen_worker.finished_signal.connect(self._on_wake_command)
        self.listen_worker.error_signal.connect(self._on_wake_command_error)
        self._track_worker(self.listen_worker)
        self.listen_worker.start()

    def _on_wake_command(self, text: str):
        if self.wake_worker is not None:
            self.wake_worker.paused = False
        self._set_ai_state("idle")
        if text:
            self.on_user_send_message(text)

    def _on_wake_command_error(self, err: str):
        if self.wake_worker is not None:
            self.wake_worker.paused = False
        self._set_ai_state("idle")

    # ------------------------------------------------------------------
    # Telegram Köprüsü
    # ------------------------------------------------------------------
    def _start_telegram_bridge(self):
        """Token varsa köprüyü (yeniden) başlatır."""
        if self.telegram_worker is not None:
            self.telegram_worker.stop()
            self.telegram_worker = None

        token = (self.controller.config.get('telegram_token') or '').strip()
        if not token:
            return

        worker = TelegramWorkerThread(self.controller)
        worker.activity_signal.connect(self._on_telegram_activity)
        worker.status_signal.connect(lambda s: self._post_assistant(s, speak=False))
        self._track_worker(worker)
        self.telegram_worker = worker
        worker.start()

    def _on_telegram_activity(self, user_text: str, reply: str):
        """Telegram trafiğini masaüstü sohbetine yansıtır ve kalıcı loglar."""
        now_str = datetime.now().strftime("%H:%M")
        self.chat_view.add_message("user", f"📱 [Telegram] {user_text}", now_str)
        # Telefondan konuşulurken masaüstünün sesli okuması gereksiz
        self._post_assistant(reply, user_prompt=f"[Telegram] {user_text}", speak=False)
        self.refresh_all_data()

    def _telegram_foto_gonder(self, foto_yolu: str, caption: str = "🖥️ ULTRON — PC ekranı"):
        """Fotoğrafı telefona iter (yapılandırılmışsa, arka planda)."""
        token = (self.controller.config.get('telegram_token') or '').strip()
        chat_id = str(self.controller.config.get('telegram_chat_id') or '').strip()
        if not token or not chat_id:
            return
        from features import telegram_bridge as tg
        worker = FuncWorkerThread(tg.send_photo, token, chat_id, foto_yolu, caption)
        self._track_worker(worker)
        worker.start()

    def _telegram_bildir(self, mesaj: str):
        """Hatırlatma vb. bildirimleri telefona iter (yapılandırılmışsa, arka planda)."""
        token = (self.controller.config.get('telegram_token') or '').strip()
        chat_id = str(self.controller.config.get('telegram_chat_id') or '').strip()
        if not token or not chat_id:
            return
        from features import telegram_bridge as tg
        worker = FuncWorkerThread(tg.send_message, token, chat_id, mesaj)
        self._track_worker(worker)
        worker.start()

    # ------------------------------------------------------------------
    # System Tray
    # ------------------------------------------------------------------
    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return

        self.tray = QSystemTrayIcon(self.app_icon, self)
        self.tray.setToolTip("ULTRON Neural Core — arka planda aktif")

        menu = QMenu()
        act_show = menu.addAction("🔴 Ultron'u Göster")
        act_show.triggered.connect(self._restore_from_tray)
        act_new = menu.addAction("⚡ Yeni Oturum")
        act_new.triggered.connect(lambda: (self._restore_from_tray(), self.start_new_chat()))
        menu.addSeparator()
        act_quit = menu.addAction("⛔ Tamamen Kapat")
        act_quit.triggered.connect(self._quit_app)
        self.tray.setContextMenu(menu)

        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        # Tek tık veya çift tık → pencereyi geri getir
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        """Tepsi menüsünden gerçek çıkış."""
        self._quitting = True
        if self.telegram_worker is not None:
            self.telegram_worker.stop()
        if self.wake_worker is not None:
            self.wake_worker.stop()
        konusmayi_durdur()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """Pencere kapatılınca uygulamayı öldürme — tepsiye küçült (hatırlatmalar yaşasın)."""
        if self._quitting or not getattr(self, 'tray', None) or not self.tray.isVisible():
            event.accept()
            return

        event.ignore()
        self.hide()
        if not self._tray_notice_shown:
            self._tray_notice_shown = True
            self.tray.showMessage(
                "ULTRON arka planda çalışıyor",
                "Hatırlatmalar aktif kalacak. Pencereyi geri açmak için tepsi simgesine tıklayın, "
                "tamamen kapatmak için sağ tık → Tamamen Kapat.",
                QSystemTrayIcon.Information, 6000
            )

    def on_ai_error(self, err_msg: str):
        self.chat_view.set_ai_state("idle")
        self.ultron_focus_view.set_ai_state("idle")

        err_text = f"⚠️ {err_msg}"
        self.chat_view.add_message("assistant", err_text, datetime.now().strftime("%H:%M"))
        self.ultron_focus_view.add_message("assistant", err_text)

    def on_mic_clicked(self):
        if not SPEECH_AVAILABLE:
            QMessageBox.warning(self, "Sesli Komut", "Sesli komut için SpeechRecognition / PyAudio paketi yüklü değil.")
            return

        # Wake word dinleyicisi mikrofonu tutuyorsa STT süresince bıraksın
        # (aksi halde sr.Microphone aynı aygıtı açamaz → sesli komut sessizce çalışmaz).
        wake_var = self.wake_worker is not None
        if wake_var:
            self.wake_worker.paused = True

        self.chat_view.set_ai_state("listening")
        self.listen_worker = ListenWorkerThread(
            device_index=self.controller.config.get('mic_device_index', -1),
            pre_delay=0.7 if wake_var else 0.0)
        self.listen_worker.finished_signal.connect(self.on_voice_input)
        self.listen_worker.error_signal.connect(self._on_stt_error)
        self._track_worker(self.listen_worker)
        self.listen_worker.start()

    def on_voice_input(self, text: str):
        self.chat_view.set_ai_state("idle")
        # Wake dinleyicisini geri aç (mikrofonu tekrar dinlemeye başlasın)
        if self.wake_worker is not None:
            self.wake_worker.paused = False
        if text:
            self.on_user_send_message(text)

    def _on_stt_error(self, err: str):
        """Sesli komut hatası: wake'i geri aç ve kullanıcıyı bilgilendir."""
        if self.wake_worker is not None:
            self.wake_worker.paused = False
        self.chat_view.set_ai_state("idle")
        self._post_assistant(f"🎙️ Sesli komut alınamadı: {err}", speak=False)

    # Reminders Handlers
    def on_add_reminder(self, text: str):
        if self.controller.add_reminder(text):
            QMessageBox.information(self, "Başarılı", "Hatırlatma kaydedildi!")
            self.refresh_all_data()
        else:
            QMessageBox.warning(self, "Uyarı", "Hatırlatma kaydedilemedi. Geçerli bir zaman belirtin (ör. 'yarın 14:00').")

    def on_toggle_reminder(self, rem_id: int, completed: bool):
        self.controller.toggle_reminder(rem_id, completed)
        self.refresh_all_data()

    def on_delete_reminder(self, rem_id: int):
        self.controller.delete_reminder(rem_id)
        self.refresh_all_data()

    # Memory Handlers
    def on_add_memory(self, key: str, value: str, category: str):
        self.controller.add_memory(key, value, category)
        self.refresh_all_data()

    def on_delete_memory(self, item_id: int):
        mems = self.controller.get_memories()
        if 0 <= item_id < len(mems):
            key = mems[item_id]['key']
            self.controller.delete_memory(key)
            self.refresh_all_data()

    # Config Handler
    def on_save_config(self, new_cfg: dict):
        if save_config(new_cfg):
            self.controller.config = new_cfg
            self.controller.provider = new_cfg.get('ai_provider', 'ollama')
            # Engine'in niyet katmanı da yeni ayarı görsün (LLM intent aç/kapa vb.)
            self.controller.engine.update_config(new_cfg)
            
            provider_name = PROVIDER_LABELS.get(self.controller.provider, self.controller.provider)
            model_name = new_cfg.get('ollama_model', '') if self.controller.provider == 'ollama' else ''
            self.sidebar.update_provider_status(provider_name, model_name)

            # Telegram / wake word ayarları değişmiş olabilir — yeniden başlat
            self._start_telegram_bridge()
            self._start_wake_word()
