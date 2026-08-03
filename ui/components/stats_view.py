"""
ULTRON Sistem İstatistikleri Sayfası

Tamamı mevcut veriden beslenir (yeni bağımlılık yok):
  • Kullanım kartları     → SQLite (sohbet_gecmisi, hatirlatmalar, memory) + rehberler
  • 7 günlük aktivite     → QPainter bar chart
  • Ruh hali dağılımı     → ruh_hali_gecmisi yüzdeleri
  • Canlı telemetri       → psutil (5 saniyede bir yenilenir)
"""

import psutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QPen, QFont

ULTRON_RED = QColor('#ff1a26')
ULTRON_RED_SOFT = QColor('#ff4d58')
ULTRON_BG = QColor(22, 6, 10)
TEXT_DIM = QColor('#a68c90')

CARD_STYLE = """
QFrame {
    background: rgba(22, 6, 10, 0.92);
    border: 1px solid rgba(255, 26, 38, 0.4);
    border-radius: 12px;
}
QFrame:hover { border-color: #ff1a26; }
"""


class StatCard(QFrame):
    """Tek metrik kartı: büyük değer + başlık."""
    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet(
            "color: #ffffff; font-size: 26px; font-weight: 900; border: none; background: transparent;")
        title_lbl = QLabel(f"{icon} {title}")
        title_lbl.setStyleSheet(
            "color: #a68c90; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; "
            "border: none; background: transparent;")

        layout.addWidget(self.value_lbl)
        layout.addWidget(title_lbl)

    def set_value(self, value):
        self.value_lbl.setText(str(value))


class MiniBarChart(QWidget):
    """QPainter ile çizilen dikey bar chart (son 7 gün aktivitesi)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []  # [(etiket, değer)]
        self.setMinimumHeight(170)

    def set_data(self, data):
        self._data = list(data)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if not self._data:
            p.setPen(QPen(TEXT_DIM))
            p.drawText(self.rect(), Qt.AlignCenter, "Henüz veri yok")
            return

        w, h = self.width(), self.height()
        margin_bottom = 26   # gün etiketleri
        margin_top = 20      # değer etiketleri
        chart_h = h - margin_bottom - margin_top
        n = len(self._data)
        slot_w = w / n
        bar_w = min(slot_w * 0.55, 46)
        max_val = max((v for _, v in self._data), default=1) or 1

        small_font = QFont("Consolas", 8)
        p.setFont(small_font)

        for i, (label, val) in enumerate(self._data):
            cx = slot_w * i + slot_w / 2
            bar_h = (val / max_val) * chart_h if max_val else 0
            x = cx - bar_w / 2
            y = margin_top + (chart_h - bar_h)

            # Bar (kırmızı degrade)
            grad = QLinearGradient(x, y, x, y + bar_h)
            grad.setColorAt(0.0, ULTRON_RED_SOFT)
            grad.setColorAt(1.0, QColor(128, 0, 10))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, y, bar_w, max(bar_h, 2)), 4, 4)

            # Değer (bar üstü)
            p.setPen(QPen(QColor('#ffffff')))
            p.drawText(QRectF(cx - slot_w / 2, y - 18, slot_w, 16),
                       Qt.AlignCenter, str(val))
            # Gün etiketi (alt)
            p.setPen(QPen(TEXT_DIM))
            p.drawText(QRectF(cx - slot_w / 2, h - margin_bottom + 6, slot_w, 16),
                       Qt.AlignCenter, label)


class PercentBar(QWidget):
    """Yatay yüzde çubuğu (ruh hali & telemetri için)."""
    def __init__(self, label: str, color: str = '#ff1a26', parent=None):
        super().__init__(parent)
        self._label = label
        self._color = QColor(color)
        self._value = 0.0
        self.setFixedHeight(30)

    def set_value(self, pct: float):
        self._value = max(0.0, min(100.0, float(pct)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        label_w = 120
        pct_w = 56
        bar_x = label_w
        bar_w = w - label_w - pct_w
        bar_h = 10
        bar_y = (h - bar_h) / 2

        p.setFont(QFont("Consolas", 9))
        p.setPen(QPen(QColor('#e0d0d2')))
        p.drawText(QRectF(0, 0, label_w - 8, h), Qt.AlignVCenter | Qt.AlignLeft, self._label)

        # Zemin
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5, 5)
        # Dolgu
        fill_w = bar_w * self._value / 100.0
        p.setBrush(self._color)
        p.drawRoundedRect(QRectF(bar_x, bar_y, max(fill_w, 2 if self._value > 0 else 0), bar_h), 5, 5)

        p.setPen(QPen(QColor('#ffffff')))
        p.drawText(QRectF(bar_x + bar_w + 8, 0, pct_w - 8, h),
                   Qt.AlignVCenter | Qt.AlignLeft, f"%{self._value:.0f}")


class _SectionCard(QFrame):
    """Başlıklı bölüm çerçevesi."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 12, 16, 14)
        self.body.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet("color: #ff4d58; font-size: 12px; font-weight: 900; "
                        "letter-spacing: 1.2px; border: none; background: transparent;")
        self.body.addWidget(t)


class StatsViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

        # Canlı telemetri — 5 saniyede bir
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self._tick_telemetry)
        self._telemetry_timer.start(5000)
        self._tick_telemetry()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        title = QLabel("📊 ULTRON SİSTEM İSTATİSTİKLERİ")
        title.setStyleSheet("font-size: 20px; font-weight: 900; color: #ff1a26; letter-spacing: 1.5px;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget, QScrollArea #qt_scrollarea_viewport { border: none; background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 8, 0)

        # 1. Kullanım kartları
        grid = QGridLayout()
        grid.setSpacing(12)
        self.card_toplam = StatCard("💬", "TOPLAM KONUŞMA")
        self.card_bugun = StatCard("📅", "BUGÜNKÜ MESAJ")
        self.card_hatirlatma = StatCard("⏰", "BEKLEYEN HATIRLATMA")
        self.card_hafiza = StatCard("🧠", "HAFIZA KAYDI")
        self.card_rehber = StatCard("📇", "REHBER KİŞİSİ")
        self.card_rutin = StatCard("🎛️", "ÖZEL RUTİN")
        # 🧠 Öğrenme katmanı kartları (features/chat_learning + suggestions)
        self.card_arsiv = StatCard("🗄️", "ARŞİVLENMİŞ KONUŞMA")
        self.card_kalip = StatCard("🔁", "ÖĞRENİLEN KALIP")
        self.card_oneri = StatCard("💡", "BEKLEYEN ÖNERİ")
        for i, card in enumerate([self.card_toplam, self.card_bugun, self.card_hatirlatma,
                                  self.card_hafiza, self.card_rehber, self.card_rutin,
                                  self.card_arsiv, self.card_kalip, self.card_oneri]):
            grid.addWidget(card, i // 3, i % 3)
        layout.addLayout(grid)

        # 2. 7 günlük aktivite
        sec_activity = _SectionCard("📈 SON 7 GÜN AKTİVİTE (mesaj sayısı)")
        self.chart = MiniBarChart()
        sec_activity.body.addWidget(self.chart)
        layout.addWidget(sec_activity)

        # 3. Ruh hali dağılımı
        sec_mood = _SectionCard("🎭 RUH HALİ DAĞILIMI (son 7 gün)")
        self.mood_pos = PercentBar("😊 Pozitif", '#ff4d58')
        self.mood_neu = PercentBar("😐 Nötr", '#a68c90')
        self.mood_neg = PercentBar("😔 Negatif", '#80000a')
        for b in (self.mood_pos, self.mood_neu, self.mood_neg):
            sec_mood.body.addWidget(b)
        layout.addWidget(sec_mood)

        # 4. Canlı telemetri
        sec_tel = _SectionCard("🖥️ CANLI SİSTEM TELEMETRİSİ")
        self.tel_cpu = PercentBar("CPU", '#ff1a26')
        self.tel_ram = PercentBar("RAM", '#ff1a26')
        self.tel_disk = PercentBar("Disk (C:)", '#ff1a26')
        for b in (self.tel_cpu, self.tel_ram, self.tel_disk):
            sec_tel.body.addWidget(b)
        layout.addWidget(sec_tel)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    def update_stats(self, stats: dict):
        """TauMainWindow.refresh_all_data() tarafından beslenir."""
        self.card_toplam.set_value(stats.get('toplam_konusma', 0))
        self.card_bugun.set_value(stats.get('bugun_mesaj', 0))
        self.card_hatirlatma.set_value(stats.get('bekleyen_hatirlatma', 0))
        self.card_hafiza.set_value(stats.get('hafiza_kaydi', 0))
        self.card_rehber.set_value(stats.get('rehber_kisi', 0))
        self.card_rutin.set_value(stats.get('ozel_rutin', 0))

        # Öğrenme metrikleri gelmeyebilir (ogrenme.db açılamadıysa) — 0 göster,
        # kartı gizleme: kaybolan kart "bozuldu mu?" sorusu doğurur.
        ogrenme = stats.get('ogrenme') or {}
        self.card_arsiv.set_value(ogrenme.get('konusma', 0))
        self.card_kalip.set_value(ogrenme.get('kalip', 0))
        self.card_oneri.set_value((ogrenme.get('oneri') or {}).get('bekleyen', 0))

        self.chart.set_data(stats.get('gunluk_aktivite', []))

        mood = stats.get('mood', {})
        self.mood_pos.set_value(mood.get('pozitif', 0))
        self.mood_neu.set_value(mood.get('nötr', 0))
        self.mood_neg.set_value(mood.get('negatif', 0))

    def _tick_telemetry(self):
        try:
            self.tel_cpu.set_value(psutil.cpu_percent(interval=None))
            self.tel_ram.set_value(psutil.virtual_memory().percent)
            import sys
            self.tel_disk.set_value(psutil.disk_usage('C:' if sys.platform == 'win32' else '/').percent)
        except Exception:
            pass
