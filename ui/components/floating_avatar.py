# -*- coding: utf-8 -*-
"""
ULTRON — Living Floating Desktop Avatar Widget 👾
Masaüstünde süzülen, yaşayan, nefes alan, sürüklenebilir 3D WebGL Three.js Ultron çekirdeği.
"""

import os
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint, QUrl, QObject
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMenu

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

from ui.ai_core_widget import AICoreWidget
from ui.components.floating_chat_bubble import FloatingChatBubble


class AvatarBridge(QObject):
    """Python-JS Bridge for Desktop Avatar Window Movement and Controls"""

    def __init__(self, avatar_widget):
        super().__init__(avatar_widget)
        self.avatar = avatar_widget

    @pyqtSlot(int, int)
    def move_window_by(self, dx, dy):
        """Web sayfasından gelen göreceli sürükleme ile pencereyi masaüstünde taşır."""
        new_x = self.avatar.x() + dx
        new_y = self.avatar.y() + dy
        self.avatar.move(new_x, new_y)
        if self.avatar.chat_bubble.isVisible():
            self.avatar.chat_bubble.position_next_to(self.avatar.geometry())
        if hasattr(self.avatar, 'quick_bar') and self.avatar.quick_bar and self.avatar.quick_bar.isVisible():
            self.avatar.quick_bar.position_under(self.avatar.geometry())

    @pyqtSlot(str)
    def handle_dropped_file(self, file_path):
        """Web sayfasından gelen drag & drop dosya yolunu işler."""
        self.avatar.process_dropped_file(file_path)

    @pyqtSlot()
    def toggle_chat_bubble(self):
        self.avatar.toggle_chat_bubble()

    @pyqtSlot()
    def toggle_main_window(self):
        self.avatar.toggle_main_window.emit()


class AvatarQuickBar(QWidget):
    """Masaüstü avatarının hemen altında süzülen 1-tık hızlı eylem barı."""
    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(34)
        
        from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(13, 6, 9, 235);
                border: 1px solid rgba(255, 26, 38, 160);
                border-radius: 17px;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 12px;
                color: #ffffff;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 26, 38, 100);
            }
            QPushButton:pressed {
                background-color: rgba(255, 26, 38, 180);
            }
        """)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        buttons = [
            ("💬", "Hızlı Komut Balonu", "toggle_bubble"),
            ("🎙️", "Canlı Sesli Sohbet", "duplex_voice"),
            ("⏯️", "Müzik Oynat / Duraklat", "play_pause"),
            ("⏭️", "Sonraki Şarkı", "next_track"),
            ("👁️", "3D İmleç Takip Gözü", "cursor_eye"),
            ("🎯", "Odak Modu", "focus_mode"),
        ]

        for icon, tooltip, act_code in buttons:
            btn = QPushButton(icon, self.container)
            btn.setToolTip(tooltip)
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, code=act_code: self.action_requested.emit(code))
            layout.addWidget(btn)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.container)
        self.adjustSize()

    def position_under(self, avatar_rect):
        """Avatar penceresinin hemen altına ortalar."""
        x = avatar_rect.x() + (avatar_rect.width() - self.width()) // 2
        y = avatar_rect.y() + avatar_rect.height() + 4
        self.move(x, y)


class UltronFloatingAvatar(QWidget):
    """Masaüstünde süzülen, hareket eden ve sürüklenebilir 3D WebGL Ultron avatarı."""
    
    command_submitted = pyqtSignal(str)
    toggle_main_window = pyqtSignal()
    toggle_focus_mode = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(160, 160)
        self.setAcceptDrops(True)

        self._drag_pos = QPoint()
        self._is_dragging = False
        self._cursor_tracking = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 3D WebGL Three.js Hologram Render (1:1 screenshot match)
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView(self)
            self.web_view.setContextMenuPolicy(Qt.NoContextMenu)
            self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))

            # Bridge & WebChannel setup
            self.bridge = AvatarBridge(self)
            self.channel = QWebChannel(self)
            self.channel.registerObject("pybridge", self.bridge)
            self.web_view.page().setWebChannel(self.channel)
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            html_path = os.path.join(base_dir, "focus_web", "avatar.html")
            self.web_view.load(QUrl.fromLocalFile(html_path))
            self.layout.addWidget(self.web_view)
            self.core_widget = None
        else:
            self.web_view = None
            self.core_widget = AICoreWidget(self, draw_bg=False)
            self.layout.addWidget(self.core_widget)

        # Quick Floating Chat Bubble
        self.chat_bubble = FloatingChatBubble()
        self.chat_bubble.command_submitted.connect(self._on_bubble_command)

        # ⚡ 1-Click Quick Action Bar attached under Avatar
        self.quick_bar = AvatarQuickBar()
        self.quick_bar.action_requested.connect(self._handle_quick_bar_action)

        # 👁️ Global Desktop Screen Cursor Tracking (30 FPS)
        # ⚠️ Takip KAPALIYKEN başlatılmaz. Eskiden koşulsuz start() ediliyordu:
        # avatar gizliyken bile saniyede 30 kez boşa tick atıyordu.
        from PyQt5.QtCore import QTimer
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(33)
        self._cursor_timer.timeout.connect(self._track_global_cursor)

        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, state: str):
        """Idle, listening, thinking, speaking durumunu günceller.

        ⚠️ Birincil yol WebEngine'dir ve orada `core_widget` None'dır; yalnızca
        `core_widget` kontrol edildiğinde durum sessizce yutuluyor, 3D hologram
        hiç tepki vermiyordu. Web tarafında three_core.js `window.ultronCoreState`
        okuyor (ultron_focus_view ile aynı sözleşme)."""
        if self.core_widget:
            self.core_widget.set_state(state)
        elif self.web_view:
            import json as _json
            safe = _json.dumps(str(state).upper())
            self.web_view.page().runJavaScript(
                f"window.ultronCoreState = {safe};"
                f"if (typeof window.setCoreState === 'function') window.setCoreState({safe});"
            )

    def set_theme(self, theme_name: str):
        """Renk temasını günceller (chroma, gold, cyan, matrix, aurora)."""
        if self.core_widget:
            self.core_widget.set_theme(theme_name)
        elif self.web_view:
            js_code = (
                f"if (window.set3DHologramTheme) window.set3DHologramTheme('{theme_name}'); "
                f"document.body.className = 'theme-{theme_name}';"
            )
            self.web_view.page().runJavaScript(js_code)
        self.theme_changed.emit(theme_name)

    def _track_global_cursor(self):
        """Tüm Windows masaüstünde farenin nerede olduğunu 3D küreye iletir."""
        if not self._cursor_tracking or not self.isVisible():
            return

        from PyQt5.QtGui import QCursor
        cursor_pos = QCursor.pos()
        center_x = self.x() + self.width() // 2
        center_y = self.y() + self.height() // 2
        dx = cursor_pos.x() - center_x
        dy = cursor_pos.y() - center_y

        if self.web_view:
            self.web_view.page().runJavaScript(
                f"window.ultronMousePos = {{ x: {dx}, y: {dy} }}; "
                f"window.ultronCursorTracking = true;"
            )

    def toggle_cursor_tracking(self, enabled=None):
        """👁️ 3D İmleç Takibini Aç/Kapat."""
        if enabled is None:
            self._cursor_tracking = not self._cursor_tracking
        else:
            self._cursor_tracking = enabled
        
        if self._cursor_tracking:
            self._cursor_timer.start()
        else:
            self._cursor_timer.stop()
            if self.web_view:
                self.web_view.page().runJavaScript("window.ultronCursorTracking = false;")
        
        state_msg = "aktif ✅" if self._cursor_tracking else "kapalı ❌"
        self.set_response(f"👁️ **İmleç Takip Eden Yapay Zeka Gözü:** {state_msg}")

    def process_dropped_file(self, file_path: str):
        """📄 Avatara sürüklenip bırakılan dosyayı otomatik analiz eder."""
        if not file_path or not os.path.exists(file_path):
            return
        filename = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.gif'):
            self.set_response(f"🖼️ **Görsel Analizi ({filename}):** Ultron ekran okuyucu çalıştırılıyor...")
            self.command_submitted.emit(f"ekrandaki metni oku: {file_path}")
        else:
            self.set_response(f"📄 **Dosya Analizi ({filename}):** Dosya inceleniyor...")
            self.command_submitted.emit(f"{filename} dosyasını oku ve özetle")

    def _on_bubble_command(self, cmd: str):
        try:
            from core.interaction.level4_input import klavye_komutu_mu
            if klavye_komutu_mu(cmd):
                self.chat_bubble.hide()
        except Exception:
            pass
        self.command_submitted.emit(cmd)

    def set_response(self, text: str):
        """Yanıtı baloncukta gösterir."""
        if not self.chat_bubble.isVisible():
            self.toggle_chat_bubble()
        self.chat_bubble.set_response(text)

    def append_stream(self, chunk: str):
        if not self.chat_bubble.isVisible():
            self.toggle_chat_bubble()
        self.chat_bubble.append_stream(chunk)

    def toggle_chat_bubble(self):
        """Hızlı komut balonunu açar/kapatır."""
        if self.chat_bubble.isVisible():
            self.chat_bubble.hide()
        else:
            self.chat_bubble.position_next_to(self.geometry())
            self.chat_bubble.show()
            self.chat_bubble.raise_()
            self.chat_bubble.activateWindow()

    # -----------------------------------------------------------------------
    # Native Qt Drag & Drop Event Handlers
    # -----------------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.process_dropped_file(file_path)
                event.acceptProposedAction()

    # -----------------------------------------------------------------------
    # Fare Sürükleme ve Tıklama Yönetimi (Python Native Fallback)
    # -----------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._is_dragging = False
            event.accept()

    def _handle_quick_bar_action(self, code: str):
        if code == "toggle_bubble":
            self.toggle_chat_bubble()
        elif code == "duplex_voice":
            try:
                from features.speech import is_duplex_voice_active
                if is_duplex_voice_active():
                    self.command_submitted.emit("canlı sesli sohbeti kapat")
                else:
                    self.command_submitted.emit("canlı sesli sohbeti başlat")
            except Exception:
                self.command_submitted.emit("canlı sesli sohbeti başlat")
        elif code == "play_pause":
            self.command_submitted.emit("oynat/duraklat")
        elif code == "next_track":
            self.command_submitted.emit("sonraki şarkı")
        elif code == "cursor_eye":
            self.toggle_cursor_tracking()
        elif code == "focus_mode":
            self.toggle_focus_mode.emit()

    def showEvent(self, event):
        super().showEvent(event)
        if self._cursor_tracking and getattr(self, '_cursor_timer', None):
            self._cursor_timer.start()
        if hasattr(self, 'quick_bar') and self.quick_bar:
            self.quick_bar.position_under(self.geometry())
            self.quick_bar.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        # Avatar gizliyken imleç takibi de durur (görünmeyen küreye veri akmaz).
        if getattr(self, '_cursor_timer', None):
            self._cursor_timer.stop()
        if hasattr(self, 'quick_bar') and self.quick_bar:
            self.quick_bar.hide()
        if hasattr(self, 'chat_bubble') and self.chat_bubble:
            self.chat_bubble.hide()

    def closeEvent(self, event):
        super().closeEvent(event)
        if hasattr(self, 'quick_bar') and self.quick_bar:
            self.quick_bar.close()
        if hasattr(self, 'chat_bubble') and self.chat_bubble:
            self.chat_bubble.close()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.frameGeometry().topLeft() - self._drag_pos
            if delta.manhattanLength() > 4:
                self._is_dragging = True
            self.move(event.globalPos() - self._drag_pos)
            if self.chat_bubble.isVisible():
                self.chat_bubble.position_next_to(self.geometry())
            if hasattr(self, 'quick_bar') and self.quick_bar and self.quick_bar.isVisible():
                self.quick_bar.position_under(self.geometry())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._is_dragging:
            self.toggle_chat_bubble()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_main_window.emit()

    def contextMenuEvent(self, event):
        """Sağ tık menüsü."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d0609;
                border: 1px solid #ff1a26;
                color: #ffffff;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #ff1a26;
                color: #ffffff;
            }
        """)

        act_bubble = menu.addAction("💬 Hızlı Komut Ver")
        act_bubble.triggered.connect(self.toggle_chat_bubble)

        act_main = menu.addAction("🖥️ Ana Pencereyi Aç / Gizle")
        act_main.triggered.connect(self.toggle_main_window.emit)

        act_eye_str = "👁️ İmleç Takibi (" + ("Açık ✅" if self._cursor_tracking else "Kapalı ❌") + ")"
        act_eye = menu.addAction(act_eye_str)
        act_eye.triggered.connect(lambda: self.toggle_cursor_tracking())

        act_duplex = menu.addAction("🎙️ Canlı Sesli Sohbet (Aç / Kapat)")
        act_duplex.triggered.connect(lambda: self.command_submitted.emit("canlı sesli sohbeti başlat"))

        act_focus = menu.addAction("🎯 Odak Modunu Başlat")
        act_focus.triggered.connect(self.toggle_focus_mode.emit)

        media_menu = menu.addMenu("🎵 Medya Kontrolü")
        act_now = media_menu.addAction("🎶 Şu An Ne Çalıyor?")
        act_now.triggered.connect(lambda: self.command_submitted.emit("şu an ne çalıyor"))
        act_pp = media_menu.addAction("⏯️ Oynat / Duraklat")
        act_pp.triggered.connect(lambda: self.command_submitted.emit("müziği duraklat"))
        act_next = media_menu.addAction("⏭️ Sonraki Şarkı")
        act_next.triggered.connect(lambda: self.command_submitted.emit("sonraki şarkı"))
        act_prev = media_menu.addAction("⏮️ Önceki Şarkı")
        act_prev.triggered.connect(lambda: self.command_submitted.emit("önceki şarkı"))

        theme_menu = menu.addMenu("🎨 Tema Seç")
        theme_options = [
            ("🌈 Chroma Rainbow (Renkli Akış)", "chroma"),
            ("🟡 Ultron Gold", "gold"),
            ("🔵 Cyan Neon", "cyan"),
            ("🟢 Matrix Green", "matrix"),
            ("🟣 Aurora Purple", "aurora"),
        ]
        for label, t_name in theme_options:
            act_t = theme_menu.addAction(label)
            act_t.triggered.connect(lambda _, t=t_name: self.set_theme(t))

        menu.addSeparator()
        act_hide = menu.addAction("✖️ Avatarı Gizle")
        act_hide.triggered.connect(self.hide)

        menu.exec_(event.globalPos())
