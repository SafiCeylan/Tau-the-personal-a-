"""
ULTRON AI CORE DESIGN SYSTEM — Avengers: Age of Ultron Theme
Dominant Crimson Red (#ff1a26), Molten Scarlet (#ff3b47), Pitch Obsidian (#060305),
and Aggressive Cybernetic Sci-Fi HUD Styling.
"""

DARK_BG = "#060305"
SIDEBAR_BG = "rgba(12, 4, 7, 0.96)"
CARD_BG = "rgba(22, 7, 11, 0.88)"
HOVER_BG = "rgba(255, 26, 38, 0.18)"
ACCENT_RED = "#ff1a26"
ACCENT_RED_BRIGHT = "#ff4d58"
ACCENT_RED_DARK = "#99000f"
TEXT_PRIMARY = "#f5e6e8"
TEXT_SECONDARY = "#a88e93"
BORDER_RED = "rgba(255, 26, 38, 0.35)"
BORDER_RED_GLOW = "rgba(255, 26, 38, 0.7)"

MAIN_STYLESHEET = """
QMainWindow, #centralWidget {
    background-color: #060305;
}

QWidget {
    color: #f5e6e8;
    font-family: 'Consolas', 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}

/* ScrollBar Styling */
QScrollBar:vertical {
    border: none;
    background: rgba(10, 3, 5, 0.8);
    width: 7px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 26, 38, 0.4);
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 26, 38, 0.8);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Ultron Card Panel */
QFrame.card {
    background-color: rgba(22, 7, 11, 0.88);
    border: 1px solid rgba(255, 26, 38, 0.3);
    border-radius: 10px;
}

QFrame.card:hover {
    border: 1px solid rgba(255, 26, 38, 0.65);
    background-color: rgba(28, 8, 14, 0.95);
}

/* Sidebar */
#sidebarFrame {
    background-color: rgba(12, 4, 7, 0.96);
    border-right: 1px solid rgba(255, 26, 38, 0.25);
}

QPushButton.navBtn {
    background-color: transparent;
    color: #a88e93;
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

QPushButton.navBtn:hover {
    background-color: rgba(255, 26, 38, 0.15);
    color: #ff4d58;
}

QPushButton.navBtn:checked {
    background-color: rgba(255, 26, 38, 0.25);
    color: #ff1a26;
    font-weight: 700;
    border-left: 3px solid #ff1a26;
}

/* Text Inputs */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: rgba(14, 4, 7, 0.95);
    border: 1px solid rgba(255, 26, 38, 0.35);
    border-radius: 8px;
    padding: 8px 12px;
    color: #f5e6e8;
    selection-background-color: #ff1a26;
    selection-color: #060305;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #ff1a26;
    background-color: rgba(22, 7, 11, 0.98);
}

/* Buttons */
QPushButton.primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #99000f, stop:1 #ff1a26);
    color: #ffffff;
    border: 1px solid #ff4d58;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 1px;
}

QPushButton.primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b80012, stop:1 #ff4d58);
    border-color: #ff1a26;
}

QPushButton.primaryBtn:pressed {
    background: #73000b;
}

QPushButton.secondaryBtn {
    background-color: rgba(255, 26, 38, 0.08);
    color: #ff4d58;
    border: 1px solid rgba(255, 26, 38, 0.35);
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.secondaryBtn:hover {
    background-color: rgba(255, 26, 38, 0.22);
    border-color: #ff1a26;
    color: #ffffff;
}

/* Labels */
QLabel.heading1 {
    font-size: 20px;
    font-weight: 800;
    color: #ff1a26;
    letter-spacing: 1.5px;
}

QLabel.heading2 {
    font-size: 15px;
    font-weight: 700;
    color: #f5e6e8;
}

QLabel.subtext {
    font-size: 12px;
    color: #a88e93;
}

/* Badges & Tags */
QLabel.badge {
    background-color: rgba(255, 26, 38, 0.2);
    color: #ff4d58;
    border: 1px solid rgba(255, 26, 38, 0.4);
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 700;
}

/* ComboBox */
QComboBox {
    background-color: rgba(14, 4, 7, 0.95);
    border: 1px solid rgba(255, 26, 38, 0.35);
    border-radius: 8px;
    padding: 6px 12px;
    color: #f5e6e8;
}
QComboBox:hover {
    border-color: #ff1a26;
}
QComboBox QAbstractItemView {
    background-color: #0c0407;
    border: 1px solid rgba(255, 26, 38, 0.4);
    selection-background-color: rgba(255, 26, 38, 0.3);
    selection-color: #ffffff;
}
"""
