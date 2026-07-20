"""
TAU — tek ve resmi masaüstü arayüzü.

Tamamen native PyQt5 widget'ları ile inşa edilmiştir (QWebEngine / tarayıcı
bileşeni YOK). Görsel çekirdek ui/ai_core_widget.py içindeki QPainter tabanlı
AICoreWidget ile çizilir. Bu dosya; koyu/altın temalı pencereyi, sayfaları
(sohbet, hatırlatmalar, ruh hali, hafıza, istatistikler) ve gerçek backend'e
(database, features/*) bağlanan AssistantController'ı içerir.

Ağ gerektiren AI çağrıları (Kobold/Ollama/TAU Backend) ve mikrofon dinleme,
arayüz donmasın diye ayrı QThread'lerde çalıştırılır.
"""

import os
import sys
import json
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QStackedWidget, QTextBrowser,
    QSizePolicy, QButtonGroup, QSpacerItem,
)

from database.db_manager import DatabaseManager
from features.reminders import hatirlatma_algila, hatirlatma_kaydet
from features.mood import ruh_hali_analiz, ruh_hali_kaydet
from features.reporting import analiz_raporu_olustur
from features.qa import cevapla_guven_skoru_ile
from features.actions.system_control import sistem_komutu_algila
from features.kobold import kobold_generate
from features.ollama import ollama_generate
from features.tau_backend import tau_backend_soru_sor

from ui.ai_core_widget import AICoreWidget

try:
    from features.speech import dinle_ve_yaziya_cevir
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

UI_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(os.path.dirname(UI_DIR), 'config.json')

PROVIDER_LABELS = {
    'kobold': 'KoboldCPP (Yerel)',
    'ollama': 'Ollama (Yerel)',
    'tau_backend': 'TAU Backend',
}

AI_ERROR_PREFIXES = ("Hata", "Bağlantı Hatası", "Ollama hatası", "KoboldCPP", "❌", "🔌", "⏱️", "⚠️")

MOOD_EMOJI = {"pozitif": "😊", "negatif": "😔", "nötr": "😐"}


def load_config():
    """config.json'u okur; eksik/bozuksa güvenli varsayılanlarla devam eder."""
    defaults = {
        'ai_provider': 'kobold',
        'kobold_url': 'http://localhost:5001',
        'ollama_url': 'http://127.0.0.1:11434',
        'ollama_model': 'gemma3:4b',
        'tau_backend_url': None,
        'tau_api_key': None,
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


# =========================================================
# Tema (koyu + altın/amber)
# =========================================================

STYLE_SHEET = """
QMainWindow, #centralWidget { background-color: #06070a; }

#sidebar {
    background-color: rgba(10, 11, 16, 235);
    border-right: 1px solid rgba(242, 181, 68, 35);
}
#brandTitle { color: #ffd873; font-size: 17px; font-weight: 700; letter-spacing: 2px; }
#brandSub { color: #6b6558; font-size: 11px; }
#brandMark {
    background-color: rgba(242, 181, 68, 40);
    border: 2px solid #f2b544;
    border-radius: 17px;
}

QPushButton#navButton {
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 9px;
    color: #a79f8e;
    background: transparent;
    font-size: 13px;
}
QPushButton#navButton:hover { background-color: rgba(242, 181, 68, 18); color: #f3ecdd; }
QPushButton#navButton:checked { background-color: rgba(242, 181, 68, 32); color: #ffd873; font-weight: 600; }

#providerBadge {
    background-color: rgba(28, 30, 40, 140);
    border: 1px solid rgba(242, 181, 68, 35);
    border-radius: 9px;
}
#providerLabel, #connLabel { color: #a79f8e; font-size: 11px; }

#topbar { border-bottom: 1px solid rgba(242, 181, 68, 35); }
#viewTitle { color: #a79f8e; font-size: 14px; font-weight: 600; letter-spacing: 2px; }

QFrame[card="true"] {
    background-color: rgba(18, 20, 28, 160);
    border: 1px solid rgba(242, 181, 68, 35);
    border-radius: 14px;
}
QFrame[card="true"] QLabel { background: transparent; border: none; }

QFrame[bubble="assistant"] {
    background-color: rgba(18, 20, 28, 170);
    border: 1px solid rgba(242, 181, 68, 30);
    border-radius: 14px;
}
QFrame[bubble="user"] {
    background-color: rgba(201, 130, 31, 55);
    border: 1px solid rgba(242, 181, 68, 70);
    border-radius: 14px;
}
QFrame[bubble] QLabel { background: transparent; border: none; color: #f3ecdd; font-size: 13.5px; }
QLabel[metaChip="true"] { color: #6b6558; font-size: 10.5px; }

QPushButton[teach="true"] {
    color: #f2b544; background: transparent;
    border: 1px solid rgba(242, 181, 68, 40); border-radius: 10px;
    padding: 1px 9px; font-size: 10.5px;
}
QPushButton[teach="true"]:hover { background-color: rgba(242, 181, 68, 20); }
QPushButton[teach="done"] { color: #6ee7a8; border-color: rgba(110,231,168,80); }

#inputBar {
    background-color: rgba(18, 20, 28, 170);
    border: 1px solid rgba(242, 181, 68, 35);
    border-radius: 22px;
}
QLineEdit#chatInput {
    background: transparent; border: none; color: #f3ecdd; font-size: 14px; padding: 6px;
}
QLineEdit {
    background-color: rgba(18, 20, 28, 160);
    border: 1px solid rgba(242, 181, 68, 35);
    border-radius: 9px; color: #f3ecdd; padding: 10px 12px; font-size: 13px;
}
QLineEdit:focus { border: 1px solid rgba(242, 181, 68, 110); }

QPushButton#roundBtn {
    background-color: rgba(28, 30, 40, 180);
    border: 1px solid rgba(242, 181, 68, 35);
    border-radius: 19px; color: #f2b544; font-size: 15px;
}
QPushButton#roundBtn:hover { background-color: rgba(242, 181, 68, 25); }
QPushButton#sendBtn { background-color: #f2b544; color: #17110a; border: none; font-weight: 700; }
QPushButton#sendBtn:hover { background-color: #ffd873; }
QPushButton#micBtn[listening="true"] { background-color: #e2685f; color: white; }

QPushButton#pillBtn {
    background-color: #f2b544; color: #17110a; font-weight: 600;
    border: none; border-radius: 9px; padding: 0 18px; font-size: 13px;
}
QPushButton#pillBtn:hover { background-color: #ffd873; }

QLabel#statValue { color: #ffd873; font-size: 25px; font-weight: 700; }
QLabel#statLabel { color: #6b6558; font-size: 11px; }

QLabel#emptyState { color: #6b6558; font-size: 12.5px; padding: 30px; }

QFrame[track="true"] { background-color: rgba(255,255,255,10); border-radius: 5px; }
QFrame[fill="pozitif"] { background-color: #d9b25a; border-radius: 5px; }
QFrame[fill="negatif"] { background-color: #e2685f; border-radius: 5px; }
QFrame[fill="nötr"] { background-color: #7c8aa0; border-radius: 5px; }

QLabel[pill="bekliyor"] { color: #f2b544; border: 1px solid rgba(242,181,68,70); border-radius: 9px; padding: 2px 9px; font-size: 10.5px; }
QLabel[pill="tamamlandi"] { color: #6b6558; border: 1px solid rgba(242,181,68,25); border-radius: 9px; padding: 2px 9px; font-size: 10.5px; }

QLabel[catTag="true"] {
    color: #f2b544; background-color: rgba(242, 181, 68, 20);
    border: 1px solid rgba(242,181,68,35); border-radius: 9px; padding: 1px 8px; font-size: 10px;
}

QPushButton[deleteBtn="true"] { background: transparent; border: none; color: #6b6558; font-size: 16px; }
QPushButton[deleteBtn="true"]:hover { color: #e2685f; }

QLabel[dot="neutral"] { color: #7c8aa0; }
QLabel[dot="on"] { color: #6ee7a8; }
QLabel[dot="off"] { color: #e2685f; }
QLabel[dot="busy"] { color: #f2b544; }

QTextBrowser#reportView {
    background-color: rgba(18, 20, 28, 160);
    border: 1px solid rgba(242, 181, 68, 35);
    border-radius: 14px; color: #f3ecdd; padding: 6px; font-size: 13px;
}

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background-color: rgba(242,181,68,60); border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QLabel { color: #f3ecdd; }
"""


# =========================================================
# Backend mantığı (web köprüsü yok — doğrudan Python nesneleri)
# =========================================================

class AssistantController:
    def __init__(self, cursor, conn, db_manager, config):
        self.cursor = cursor
        self.conn = conn
        self.db = db_manager
        self.config = config
        self.provider = config.get('ai_provider', 'kobold')
        self.ai_context = {}

    def provider_label(self):
        return PROVIDER_LABELS.get(self.provider, self.provider)

    def fast_path(self, soru):
        """Ağ gerektirmeyen, anında cevaplanabilecek yolları dener.
        Bulursa (cevap, guven, kaynak, html_mi) döner, yoksa None (AI gerekiyor demek)."""
        is_action, action_response = sistem_komutu_algila(soru)
        if is_action:
            return f"⚙️ {action_response}", 100, "system", False

        hatirlatma = hatirlatma_algila(soru)
        if hatirlatma:
            if hatirlatma['tip'] == 'hatirlatma':
                if hatirlatma_kaydet(self.cursor, self.conn, hatirlatma):
                    detay = hatirlatma.get('detay', '')
                    return (
                        f"✅ Hatırlatma kaydedildi! '{hatirlatma['metin']}' konusunda {detay} hatırlatacağım.",
                        100, "system", False,
                    )
                return "❌ Hatırlatma kaydedilirken bir hata oluştu.", 0, "system", False

            if hatirlatma['tip'] == 'gecmis_takip':
                self.cursor.execute("""
                    SELECT metin, durum FROM hatirlatmalar
                    ORDER BY olusturma_tarihi DESC LIMIT 5
                """)
                rows = self.cursor.fetchall()
                if rows:
                    lines = [f"{i}. {metin} ({durum})" for i, (metin, durum) in enumerate(rows, 1)]
                    return "📅 Geçmiş hatırlatmaların:\n" + "\n".join(lines), 100, "system", False
                return "📅 Henüz hatırlatman yok.", 100, "system", False

            if hatirlatma['tip'] == 'analiz_raporu':
                return analiz_raporu_olustur(self.cursor), 100, "system", True

        ruh_hali, _skor = ruh_hali_analiz(soru)
        if ruh_hali != 'belirsiz':
            ruh_hali_kaydet(self.cursor, self.conn, ruh_hali, soru)

        cevap, skor = cevapla_guven_skoru_ile(self.cursor, soru)
        if skor >= 70:
            return cevap, skor, "db", False

        return None

    def log(self, soru, cevap):
        try:
            self.db.log_conversation(soru, cevap)
        except Exception as e:
            print(f"[TAU] Sohbet loglanamadı: {e}")

    def teach(self, soru, cevap, kategori="Genel"):
        try:
            self.db.add_question_answer(soru, cevap, kategori or "Genel")
            return True
        except Exception as e:
            print(f"[TAU] teach hata: {e}")
            return False

    def get_reminders(self):
        self.cursor.execute("""
            SELECT metin, hedef_tarih, olusturma_tarihi, durum FROM hatirlatmalar
            ORDER BY olusturma_tarihi DESC LIMIT 50
        """)
        return [
            {"metin": m, "hedef_tarih": h, "olusturma_tarihi": o, "durum": d}
            for m, h, o, d in self.cursor.fetchall()
        ]

    def add_reminder(self, text):
        text = (text or "").strip()
        if not text:
            return False, "Boş hatırlatma eklenemez."
        parsed = hatirlatma_algila(text)
        if not parsed or parsed.get('tip') != 'hatirlatma':
            return False, "Bir zaman ifadesi anlayamadım (ör. 'yarın', '10 dakika sonra')."
        ok = hatirlatma_kaydet(self.cursor, self.conn, parsed)
        return ok, ("Eklendi" if ok else "Kaydedilemedi")

    def get_mood_history(self):
        bir_hafta_once = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute("""
            SELECT ruh_hali, COUNT(*) FROM ruh_hali_gecmisi
            WHERE tarih >= ? GROUP BY ruh_hali
        """, (bir_hafta_once,))
        counts = {row[0]: row[1] for row in self.cursor.fetchall()}

        self.cursor.execute("""
            SELECT ruh_hali, tarih FROM ruh_hali_gecmisi
            ORDER BY tarih DESC LIMIT 1
        """)
        latest_row = self.cursor.fetchone()
        latest = {"ruh_hali": latest_row[0], "tarih": latest_row[1]} if latest_row else None
        return {"counts": counts, "latest": latest}

    def get_memory_list(self):
        rows = self.db.list_memory()
        return [{"key": k, "value": v, "category": c or "Genel"} for k, v, c in rows]

    def add_memory(self, key, value, category="Genel"):
        key, value = (key or "").strip(), (value or "").strip()
        if not key or not value:
            return False
        try:
            self.db.add_memory(key, value, category or "Genel")
            return True
        except Exception as e:
            print(f"[TAU] addMemory hata: {e}")
            return False

    def delete_memory(self, key):
        try:
            self.db.delete_memory(key)
            return True
        except Exception as e:
            print(f"[TAU] deleteMemory hata: {e}")
            return False

    def get_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM bilgiler")
        toplam_bilgi = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM sohbet_gecmisi")
        toplam_sohbet = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM hatirlatmalar WHERE durum='bekliyor'")
        aktif_hatirlatma = self.cursor.fetchone()[0]
        rapor = analiz_raporu_olustur(self.cursor)
        return {
            "toplamBilgi": toplam_bilgi, "toplamSohbet": toplam_sohbet,
            "aktifHatirlatma": aktif_hatirlatma, "reportText": rapor,
        }


# =========================================================
# Arka plan işçileri (ağ / mikrofon çağrıları UI'ı kilitlemesin)
# =========================================================

class AIWorker(QThread):
    finished_ok = pyqtSignal(str, str, str, object)  # soru, cevap, provider, yeni_context

    def __init__(self, provider, config, soru, context):
        super().__init__()
        self.provider = provider
        self.config = config
        self.soru = soru
        self.context = context

    def run(self):
        try:
            if self.provider == 'ollama':
                cevap, ctx = ollama_generate(
                    self.soru, ollama_url=self.config.get('ollama_url', 'http://127.0.0.1:11434'),
                    model=self.config.get('ollama_model') or 'gemma3:4b', context=self.context)
            elif self.provider == 'tau_backend':
                cevap, ctx = tau_backend_soru_sor(self.soru), None
            else:
                cevap, ctx = kobold_generate(
                    self.soru, kobold_url=self.config.get('kobold_url', 'http://localhost:5001'),
                    context=self.context)
        except Exception as e:
            cevap, ctx = f"❌ AI çağrısı sırasında beklenmeyen hata: {e}", None
        self.finished_ok.emit(self.soru, cevap or "", self.provider, ctx)


class VoiceWorker(QThread):
    result_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def run(self):
        try:
            text = dinle_ve_yaziya_cevir()
        except Exception as e:
            self.error.emit(f"Mikrofon hatası: {e}")
            return
        if text:
            self.result_ready.emit(text)
        else:
            self.error.emit("Ses algılanamadı, tekrar dener misin?")


# =========================================================
# Küçük yeniden kullanılabilir widget'lar
# =========================================================

def make_dot(state="neutral"):
    dot = QLabel("●")
    dot.setProperty("dot", state)
    return dot


class MessageBubble(QFrame):
    def __init__(self, text, role, source=None, confidence=None, is_html=False,
                 question=None, controller=None, parent=None):
        super().__init__(parent)
        self.setProperty("bubble", role)
        self.setMaximumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText if is_html else Qt.PlainText)
        label.setText(text)
        layout.addWidget(label)

        if role == "assistant":
            meta_row = QHBoxLayout()
            meta_row.setSpacing(8)
            chip_text = {"db": "💾 Hafıza", "ai": "🧠 Yapay Zeka", "system": "⚙️ Sistem"}.get(source, "🧠")
            if confidence is not None:
                chip_text += f" · %{confidence}"
            chip = QLabel(chip_text)
            chip.setProperty("metaChip", True)
            meta_row.addWidget(chip)

            if source != "system" and question and controller:
                teach_btn = QPushButton("Bunu öğret")
                teach_btn.setProperty("teach", "true")
                teach_btn.setCursor(Qt.PointingHandCursor)

                def on_teach():
                    ok = controller.teach(question, text)
                    if ok:
                        teach_btn.setText("✓ Öğrenildi")
                        teach_btn.setProperty("teach", "done")
                        teach_btn.setEnabled(False)
                        teach_btn.style().unpolish(teach_btn)
                        teach_btn.style().polish(teach_btn)

                teach_btn.clicked.connect(on_teach)
                meta_row.addWidget(teach_btn)

            meta_row.addStretch(1)
            layout.addLayout(meta_row)


def wrap_row(widget, align_right):
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    if align_right:
        row.addStretch(1)
        row.addWidget(widget)
    else:
        row.addWidget(widget)
        row.addStretch(1)
    container = QWidget()
    container.setLayout(row)
    return container


def make_card():
    card = QFrame()
    card.setProperty("card", "true")
    return card


class ScrollList(QScrollArea):
    """Dikey, kaydırılabilir kart listesi için ortak iskelet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._inner)

    def clear(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def add_widget(self, widget):
        self._layout.insertWidget(self._layout.count() - 1, widget)

    def set_empty(self, message):
        self.clear()
        empty = QLabel(message)
        empty.setObjectName("emptyState")
        empty.setAlignment(Qt.AlignCenter)
        empty.setWordWrap(True)
        self.add_widget(empty)


def format_date(value):
    if not value:
        return ""
    try:
        dt = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return value


# =========================================================
# Sayfalar
# =========================================================

class ChatPage(QWidget):
    def __init__(self, controller: AssistantController, core: AICoreWidget, status_cb, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.core = core
        self.status_cb = status_cb  # sağlayıcı durum noktasını günceller
        self._worker = None
        self._speaking_timer = QTimer(self)
        self._speaking_timer.setSingleShot(True)
        self._speaking_timer.timeout.connect(lambda: self.core.set_state("idle"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 6, 30, 20)
        layout.setSpacing(10)

        self.scroll = ScrollList()
        layout.addWidget(self.scroll, 1)

        input_bar = QFrame()
        input_bar.setObjectName("inputBar")
        bar_layout = QHBoxLayout(input_bar)
        bar_layout.setContentsMargins(6, 6, 6, 6)
        bar_layout.setSpacing(8)

        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.setProperty("listening", "false")
        self.mic_btn.setFixedSize(38, 38)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.clicked.connect(self._start_listening)
        bar_layout.addWidget(self.mic_btn)

        self.input = QLineEdit()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("TAU'ya bir şey sor...")
        self.input.returnPressed.connect(self._send)
        bar_layout.addWidget(self.input, 1)

        send_btn = QPushButton("➤")
        send_btn.setObjectName("sendBtn")
        send_btn.setFixedSize(38, 38)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.clicked.connect(self._send)
        bar_layout.addWidget(send_btn)

        layout.addWidget(input_bar)

        self._append_assistant("Merhaba! Ben TAU, kişisel asistanınız. Size nasıl yardımcı olabilirim? 😊",
                                source="system")

    # ---------------- gönderme akışı ----------------

    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._append_user(text)
        self.core.set_state("thinking")

        fast = self.controller.fast_path(text)
        if fast is not None:
            cevap, confidence, source, is_html = fast
            self.controller.log(text, cevap)
            self._show_answer(text, cevap, confidence, source, is_html)
            return

        self._worker = AIWorker(self.controller.provider, self.controller.config, text,
                                 self.controller.ai_context.get(self.controller.provider))
        self._worker.finished_ok.connect(self._on_ai_finished)
        self._worker.start()

    def _on_ai_finished(self, soru, cevap, provider, yeni_context):
        if yeni_context:
            self.controller.ai_context[provider] = yeni_context

        if any(cevap.startswith(p) for p in AI_ERROR_PREFIXES):
            db_cevap, skor = cevapla_guven_skoru_ile(self.controller.cursor, soru)
            self.status_cb(False)
            if skor > 30:
                self.controller.log(soru, db_cevap)
                self._show_answer(soru, db_cevap, skor, "db", False)
            else:
                self.controller.log(soru, cevap)
                self._show_answer(soru, cevap, 0, "ai", False)
            return

        self.status_cb(True)
        self.controller.log(soru, cevap)
        self._show_answer(soru, cevap, 85, "ai", False)

    def _show_answer(self, question, answer, confidence, source, is_html):
        self.core.set_state("speaking")
        self._append_assistant(answer, source=source, confidence=confidence,
                                is_html=is_html, question=question)
        self._speaking_timer.start(1500)

    # ---------------- sesli komut ----------------

    def _start_listening(self):
        if not SPEECH_AVAILABLE:
            self._append_assistant("Sesli komut için 'SpeechRecognition' ve 'pygame' paketleri kurulu değil.",
                                    source="system")
            return
        self.mic_btn.setProperty("listening", "true")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)
        self.core.set_state("listening")

        self._voice_worker = VoiceWorker()
        self._voice_worker.result_ready.connect(self._on_voice_result)
        self._voice_worker.error.connect(self._on_voice_error)
        self._voice_worker.start()

    def _reset_mic(self):
        self.mic_btn.setProperty("listening", "false")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)
        self.core.set_state("idle")

    def _on_voice_result(self, text):
        self._reset_mic()
        self.input.setText(text)
        self._send()

    def _on_voice_error(self, message):
        self._reset_mic()
        self._append_assistant(message, source="system")

    # ---------------- mesaj ekleme ----------------

    def _append_user(self, text):
        bubble = MessageBubble(text, "user")
        self.scroll.add_widget(wrap_row(bubble, align_right=True))
        self._scroll_to_bottom()

    def _append_assistant(self, text, source="ai", confidence=None, is_html=False, question=None):
        bubble = MessageBubble(text, "assistant", source=source, confidence=confidence,
                                is_html=is_html, question=question, controller=self.controller)
        self.scroll.add_widget(wrap_row(bubble, align_right=False))
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(10, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))


class RemindersPage(QWidget):
    def __init__(self, controller: AssistantController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 4, 30, 20)
        layout.setSpacing(12)

        header = QLabel("Hatırlatmalar")
        header.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(header)
        hint = QLabel("Doğal dille yaz: \"yarın toplantı\" veya \"10 dakika sonra su iç\"")
        hint.setStyleSheet("color: #6b6558; font-size: 12px;")
        layout.addWidget(hint)

        form = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Yeni hatırlatma...")
        self.input.returnPressed.connect(self._add)
        form.addWidget(self.input, 1)
        add_btn = QPushButton("Ekle")
        add_btn.setObjectName("pillBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add)
        form.addWidget(add_btn)
        layout.addLayout(form)

        self.list = ScrollList()
        layout.addWidget(self.list, 1)

    def _add(self):
        text = self.input.text().strip()
        if not text:
            return
        ok, message = self.controller.add_reminder(text)
        if ok:
            self.input.clear()
            self.refresh()
        else:
            self.input.setPlaceholderText(message)

    def refresh(self):
        items = self.controller.get_reminders()
        self.list.clear()
        if not items:
            self.list.set_empty("Henüz hatırlatman yok. Yukarıdan ekleyebilirsin.")
            return
        for r in items:
            card = make_card()
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)

            text_col = QVBoxLayout()
            text_lbl = QLabel(r["metin"])
            text_lbl.setStyleSheet("font-size: 13.5px;")
            date_lbl = QLabel(format_date(r["hedef_tarih"]))
            date_lbl.setStyleSheet("color: #6b6558; font-size: 11px;")
            text_col.addWidget(text_lbl)
            text_col.addWidget(date_lbl)
            row.addLayout(text_col, 1)

            pill = QLabel("Tamamlandı" if r["durum"] == "tamamlandi" else "Bekliyor")
            pill.setProperty("pill", r["durum"])
            row.addWidget(pill)

            self.list.add_widget(card)


class MoodPage(QWidget):
    def __init__(self, controller: AssistantController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 4, 30, 20)
        layout.setSpacing(14)

        header = QLabel("Ruh Hali")
        header.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(header)
        hint = QLabel("Son 7 günün duygu durum dağılımı")
        hint.setStyleSheet("color: #6b6558; font-size: 12px;")
        layout.addWidget(hint)

        self.current_holder = QVBoxLayout()
        layout.addLayout(self.current_holder)

        self.chart_holder = QVBoxLayout()
        self.chart_holder.setSpacing(12)
        layout.addLayout(self.chart_holder)
        layout.addStretch(1)

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def refresh(self):
        data = self.controller.get_mood_history()
        counts = data["counts"]
        latest = data["latest"]

        self._clear_layout(self.current_holder)
        card = make_card()
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        if latest:
            emoji = QLabel(MOOD_EMOJI.get(latest["ruh_hali"], "😐"))
            emoji.setStyleSheet("font-size: 26px;")
            row.addWidget(emoji)
            text_col = QVBoxLayout()
            text_col.addWidget(QLabel("Son algılanan ruh halin"))
            value = QLabel(latest["ruh_hali"].capitalize())
            value.setStyleSheet("color: #ffd873; font-size: 15px; font-weight: 600;")
            text_col.addWidget(value)
            row.addLayout(text_col)
            row.addStretch(1)
            self.current_holder.addWidget(card)
        else:
            empty = QLabel("Henüz ruh hali verisi yok.")
            empty.setObjectName("emptyState")
            self.current_holder.addWidget(empty)

        self._clear_layout(self.chart_holder)
        max_count = max([1] + list(counts.values()))
        for key in ["pozitif", "negatif", "nötr"]:
            count = counts.get(key, 0)
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)

            label = QLabel(f"{MOOD_EMOJI[key]} {key.capitalize()}")
            label.setFixedWidth(90)
            row_l.addWidget(label)

            track = QFrame()
            track.setProperty("track", "true")
            track.setFixedHeight(10)
            track.setMinimumWidth(160)
            fill = QFrame(track)
            fill.setProperty("fill", key)
            ratio = count / max_count if max_count else 0
            fill.setGeometry(0, 0, max(2, int(220 * ratio)), 10)
            track.setFixedWidth(220)
            row_l.addWidget(track)

            count_lbl = QLabel(str(count))
            count_lbl.setFixedWidth(24)
            count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_l.addWidget(count_lbl)
            row_l.addStretch(1)

            self.chart_holder.addWidget(row_w)


class MemoryPage(QWidget):
    def __init__(self, controller: AssistantController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 4, 30, 20)
        layout.setSpacing(12)

        header = QLabel("Hafıza")
        header.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(header)
        hint = QLabel("TAU'nun aklında tuttuğu bilgiler")
        hint.setStyleSheet("color: #6b6558; font-size: 12px;")
        layout.addWidget(hint)

        form = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Anahtar (ör. doğum günüm)")
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Değer (ör. 5 Mayıs)")
        self.value_input.returnPressed.connect(self._add)
        form.addWidget(self.key_input, 1)
        form.addWidget(self.value_input, 1)
        add_btn = QPushButton("Kaydet")
        add_btn.setObjectName("pillBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add)
        form.addWidget(add_btn)
        layout.addLayout(form)

        self.list = ScrollList()
        layout.addWidget(self.list, 1)

    def _add(self):
        key, value = self.key_input.text().strip(), self.value_input.text().strip()
        if not key or not value:
            return
        if self.controller.add_memory(key, value, "Genel"):
            self.key_input.clear()
            self.value_input.clear()
            self.refresh()

    def refresh(self):
        items = self.controller.get_memory_list()
        self.list.clear()
        if not items:
            self.list.set_empty("Henüz kayıtlı hafıza yok.")
            return
        for m in items:
            card = make_card()
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)

            text_col = QVBoxLayout()
            key_lbl = QLabel(m["key"])
            key_lbl.setStyleSheet("color: #ffd873; font-weight: 600; font-size: 13.5px;")
            value_lbl = QLabel(m["value"])
            value_lbl.setStyleSheet("color: #a79f8e; font-size: 12.5px;")
            value_lbl.setWordWrap(True)
            cat_lbl = QLabel(m["category"])
            cat_lbl.setProperty("catTag", "true")
            text_col.addWidget(key_lbl)
            text_col.addWidget(value_lbl)
            cat_row = QHBoxLayout()
            cat_row.addWidget(cat_lbl)
            cat_row.addStretch(1)
            text_col.addLayout(cat_row)
            row.addLayout(text_col, 1)

            del_btn = QPushButton("×")
            del_btn.setProperty("deleteBtn", "true")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(lambda _, k=m["key"]: self._delete(k))
            row.addWidget(del_btn, 0, Qt.AlignTop)

            self.list.add_widget(card)

    def _delete(self, key):
        if self.controller.delete_memory(key):
            self.refresh()


class StatsPage(QWidget):
    def __init__(self, controller: AssistantController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 4, 30, 20)
        layout.setSpacing(14)

        header = QLabel("İstatistikler")
        header.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(header)
        hint = QLabel("Genel kullanım özeti")
        hint.setStyleSheet("color: #6b6558; font-size: 12px;")
        layout.addWidget(hint)

        self.grid = QHBoxLayout()
        self.grid.setSpacing(14)
        layout.addLayout(self.grid)

        self.report = QTextBrowser()
        self.report.setObjectName("reportView")
        layout.addWidget(self.report, 1)

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def refresh(self):
        data = self.controller.get_stats()
        self._clear_layout(self.grid)
        cards = [
            ("Öğrenilen Bilgi", data["toplamBilgi"]),
            ("Toplam Sohbet", data["toplamSohbet"]),
            ("Aktif Hatırlatma", data["aktifHatirlatma"]),
        ]
        for label, value in cards:
            card = make_card()
            col = QVBoxLayout(card)
            col.setContentsMargins(16, 14, 16, 14)
            value_lbl = QLabel(str(value))
            value_lbl.setObjectName("statValue")
            label_lbl = QLabel(label)
            label_lbl.setObjectName("statLabel")
            col.addWidget(value_lbl)
            col.addWidget(label_lbl)
            self.grid.addWidget(card)

        self.report.setHtml(data["reportText"])


# =========================================================
# Ana pencere
# =========================================================

NAV_ITEMS = [
    ("chat", "💬", "Sohbet"),
    ("reminders", "⏰", "Hatırlatmalar"),
    ("mood", "🙂", "Ruh Hali"),
    ("memory", "🧠", "Hafıza"),
    ("stats", "📊", "İstatistikler"),
]


class TauMainWindow(QMainWindow):
    def __init__(self, cursor, conn, db_manager, config):
        super().__init__()
        self.setWindowTitle("TAU — Kişisel Asistan")
        self.resize(1400, 900)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(STYLE_SHEET)

        self.controller = AssistantController(cursor, conn, db_manager, config)

        central = QWidget()
        central.setObjectName("centralWidget")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        root.addWidget(self._build_sidebar())

        main_col = QVBoxLayout()
        main_col.setContentsMargins(0, 0, 0, 0)
        main_col.setSpacing(0)
        main_col.addWidget(self._build_topbar())

        self.core = AICoreWidget()
        main_col.addWidget(self.core)

        self.pages = QStackedWidget()
        self.chat_page = ChatPage(self.controller, self.core, self._set_provider_status)
        self.reminders_page = RemindersPage(self.controller)
        self.mood_page = MoodPage(self.controller)
        self.memory_page = MemoryPage(self.controller)
        self.stats_page = StatsPage(self.controller)
        for key, page in [("chat", self.chat_page), ("reminders", self.reminders_page),
                           ("mood", self.mood_page), ("memory", self.memory_page),
                           ("stats", self.stats_page)]:
            self.pages.addWidget(page)
        main_col.addWidget(self.pages, 1)

        main_wrap = QWidget()
        main_wrap.setLayout(main_col)
        root.addWidget(main_wrap, 1)

        self._select_nav("chat")
        self.provider_label.setText(self.controller.provider_label())
        self.conn_label.setText(f"Hazır · {self.controller.provider_label()}")
        self.provider_dot.setProperty("dot", "on")
        self._repolish(self.provider_dot)

    # ---------------- inşa yardımcıları ----------------

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QWidget()
        brand_l = QHBoxLayout(brand)
        brand_l.setContentsMargins(20, 20, 20, 18)
        mark = QLabel()
        mark.setObjectName("brandMark")
        mark.setFixedSize(34, 34)
        brand_l.addWidget(mark)
        text_col = QVBoxLayout()
        title = QLabel("TAU")
        title.setObjectName("brandTitle")
        sub = QLabel("Kişisel Asistan")
        sub.setObjectName("brandSub")
        text_col.addWidget(title)
        text_col.addWidget(sub)
        brand_l.addLayout(text_col)
        brand_l.addStretch(1)
        layout.addWidget(brand)

        nav_holder = QWidget()
        nav_l = QVBoxLayout(nav_holder)
        nav_l.setContentsMargins(12, 10, 12, 10)
        nav_l.setSpacing(3)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for key, icon, label in NAV_ITEMS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._select_nav(k))
            nav_l.addWidget(btn)
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
        nav_l.addStretch(1)
        layout.addWidget(nav_holder, 1)

        footer = QFrame()
        footer.setObjectName("providerBadge")
        footer_l = QHBoxLayout(footer)
        footer_l.setContentsMargins(12, 9, 12, 9)
        self.provider_dot = make_dot("neutral")
        self.provider_label = QLabel("Bağlanıyor...")
        self.provider_label.setObjectName("providerLabel")
        footer_l.addWidget(self.provider_dot)
        footer_l.addWidget(self.provider_label, 1)
        footer_wrap = QVBoxLayout()
        footer_wrap.setContentsMargins(16, 12, 16, 18)
        footer_wrap.addWidget(footer)
        layout.addLayout(footer_wrap)

        return sidebar

    def _build_topbar(self):
        topbar = QFrame()
        topbar.setObjectName("topbar")
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(30, 16, 30, 16)

        self.view_title = QLabel("SOHBET")
        self.view_title.setObjectName("viewTitle")
        layout.addWidget(self.view_title)
        layout.addStretch(1)

        self.conn_dot = make_dot("on")
        self.conn_label = QLabel("Hazır")
        self.conn_label.setObjectName("connLabel")
        layout.addWidget(self.conn_dot)
        layout.addWidget(self.conn_label)

        return topbar

    # ---------------- navigasyon ----------------

    def _select_nav(self, key):
        titles = {"chat": "Sohbet", "reminders": "Hatırlatmalar", "mood": "Ruh Hali",
                  "memory": "Hafıza", "stats": "İstatistikler"}
        index = {"chat": 0, "reminders": 1, "mood": 2, "memory": 3, "stats": 4}[key]
        self.pages.setCurrentIndex(index)
        self.view_title.setText(titles[key].upper())
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

        if key == "reminders":
            self.reminders_page.refresh()
        elif key == "mood":
            self.mood_page.refresh()
        elif key == "memory":
            self.memory_page.refresh()
        elif key == "stats":
            self.stats_page.refresh()

    def _set_provider_status(self, healthy):
        self.provider_dot.setProperty("dot", "on" if healthy else "off")
        self._repolish(self.provider_dot)

    @staticmethod
    def _repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def main():
    db_manager = DatabaseManager('bilgiler.db')
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    config = load_config()

    app = QApplication(sys.argv)
    window = TauMainWindow(cursor, conn, db_manager, config)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
