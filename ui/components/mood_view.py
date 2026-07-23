from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar, QScrollArea
)
from PyQt5.QtCore import Qt

class MoodViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        
        head = QLabel("🎭 Duygu Durumu & Ruh Hali Analizi")
        head.setStyleSheet("color: #ffd873; font-size: 20px; font-weight: 800;")
        
        sub = QLabel("Son sohbetlerinize dayalı duygu durumu dağılımı ve analiz raporu")
        sub.setStyleSheet("color: #9aa0a6; font-size: 12px;")

        title_box.addWidget(head)
        title_box.addWidget(sub)
        layout.addLayout(title_box)

        # Mood Overview Cards (Positive, Neutral, Negative)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.pos_card = self._create_mood_card("Pozitif", "😊", "0%", "#4caf50")
        self.neu_card = self._create_mood_card("Nötr", "😐", "0%", "#ffb74d")
        self.neg_card = self._create_mood_card("Negatif", "😔", "0%", "#ef5350")

        cards_layout.addWidget(self.pos_card['frame'])
        cards_layout.addWidget(self.neu_card['frame'])
        cards_layout.addWidget(self.neg_card['frame'])

        layout.addLayout(cards_layout)

        # Progress / Distribution Section
        dist_box = QFrame()
        dist_box.setStyleSheet("""
            QFrame {
                background: rgba(20, 23, 33, 0.85);
                border: 1px solid rgba(242, 181, 68, 0.2);
                border-radius: 12px;
                padding: 12px;
            }
        """)
        dist_layout = QVBoxLayout(dist_box)
        dist_layout.setSpacing(10)

        dist_title = QLabel("Duygu Durum Dağılım Oranları")
        dist_title.setStyleSheet("color: #ffd873; font-size: 14px; font-weight: 700;")
        dist_layout.addWidget(dist_title)

        # Positive Progress
        self.pos_bar = self._create_progress_row("😊 Pozitif", "#4caf50", dist_layout)
        self.neu_bar = self._create_progress_row("😐 Nötr", "#ffb74d", dist_layout)
        self.neg_bar = self._create_progress_row("😔 Negatif", "#ef5350", dist_layout)

        layout.addWidget(dist_box)

        # Recent Logs Scroll
        log_title = QLabel("Son Duygu Analizi Kayıtları")
        log_title.setStyleSheet("color: #f0f2f5; font-size: 14px; font-weight: 700;")
        layout.addWidget(log_title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.log_container = QWidget()
        self.log_container.setStyleSheet("background: transparent;")
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(8)
        self.log_layout.addStretch()

        self.scroll.setWidget(self.log_container)
        layout.addWidget(self.scroll, 1)

    def _create_mood_card(self, title, emoji, percent, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(20, 23, 33, 0.85);
                border: 1px solid rgba(242, 181, 68, 0.2);
                border-radius: 12px;
                padding: 14px;
            }}
        """)
        l = QVBoxLayout(frame)
        l.setSpacing(4)
        
        e_lbl = QLabel(emoji)
        e_lbl.setStyleSheet("font-size: 28px;")
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #9aa0a6; font-size: 12px; font-weight: 600;")
        
        v_lbl = QLabel(percent)
        v_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 800;")
        
        l.addWidget(e_lbl)
        l.addWidget(t_lbl)
        l.addWidget(v_lbl)
        return {'frame': frame, 'val': v_lbl}

    def _create_progress_row(self, label_text, color_hex, parent_layout):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(90)
        lbl.setStyleSheet("color: #f0f2f5; font-size: 12px;")

        pbar = QProgressBar()
        pbar.setFixedHeight(12)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {color_hex};
                border-radius: 6px;
            }}
        """)

        pct_lbl = QLabel("%0")
        pct_lbl.setFixedWidth(40)
        pct_lbl.setStyleSheet("color: #9aa0a6; font-size: 11px; font-weight: 600;")

        row.addWidget(lbl)
        row.addWidget(pbar, 1)
        row.addWidget(pct_lbl)
        parent_layout.addLayout(row)
        return {'bar': pbar, 'pct': pct_lbl}

    def update_stats(self, stats: dict, logs: list = None):
        """
        stats: {'pozitif': 60, 'nötr': 30, 'negatif': 10}
        """
        pos = stats.get('pozitif', 0)
        neu = stats.get('nötr', 0)
        neg = stats.get('negatif', 0)

        self.pos_card['val'].setText(f"%{pos}")
        self.neu_card['val'].setText(f"%{neu}")
        self.neg_card['val'].setText(f"%{neg}")

        self.pos_bar['bar'].setValue(int(pos))
        self.pos_bar['pct'].setText(f"%{int(pos)}")

        self.neu_bar['bar'].setValue(int(neu))
        self.neu_bar['pct'].setText(f"%{int(neu)}")

        self.neg_bar['bar'].setValue(int(neg))
        self.neg_bar['pct'].setText(f"%{int(neg)}")

        if logs:
            while self.log_layout.count() > 1:
                c = self.log_layout.takeAt(0)
                if c.widget():
                    c.widget().deleteLater()

            for item in logs:
                lbl = QLabel(f"• {item}")
                lbl.setStyleSheet("color: #9aa0a6; font-size: 12px;")
                self.log_layout.insertWidget(self.log_layout.count()-1, lbl)
