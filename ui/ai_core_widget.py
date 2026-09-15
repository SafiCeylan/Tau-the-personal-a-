"""
ULTRON Ultimate Holographic AI Core Canvas — V4.0 Next-Gen Visualizer
Features:
- Matrix Hex Stream Data Rain (0x7F, 0x4A, NEURAL_SYNC)
- Expanding Shockwave Pulse Rings
- 32-Bar Radiating Audio Spectrum Visualizer with White Hot Peaks
- Multi-Layer 3D-Tilted Gear Reticles & Radar Tars
- State-aware reactivity (idle, listening, thinking, speaking)
"""

import math
import random
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QRadialGradient, QLinearGradient, QPen, QPainterPath, QBrush, QFont
)
from PyQt5.QtWidgets import QWidget, QSizePolicy

# Ultron Theme Palettes
THEME_PALETTES = {
    "crimson": {
        "hot": QColor("#ffffff"),
        "bright": QColor("#ff4d58"),
        "crimson": QColor("#ff1a26"),
        "deep": QColor("#99000f"),
        "dark": QColor("#2b0004"),
        "bg": QColor("#050204"),
    },
    "gold": {
        "hot": QColor("#ffffff"),
        "bright": QColor("#ffd700"),
        "crimson": QColor("#ffaa00"),
        "deep": QColor("#b8860b"),
        "dark": QColor("#2b2004"),
        "bg": QColor("#050402"),
    },
    "cyan": {
        "hot": QColor("#ffffff"),
        "bright": QColor("#00f0ff"),
        "crimson": QColor("#0099ff"),
        "deep": QColor("#0055aa"),
        "dark": QColor("#001a33"),
        "bg": QColor("#020406"),
    },
    "obsidian": {
        "hot": QColor("#ffffff"),
        "bright": QColor("#e040ff"),
        "crimson": QColor("#d000ff"),
        "deep": QColor("#7000aa"),
        "dark": QColor("#200033"),
        "bg": QColor("#040205"),
    }
}

# Fallback default colors for backward compatibility
RED_HOT = QColor("#ffffff")
RED_BRIGHT = QColor("#ff4d58")
RED_CRIMSON = QColor("#ff1a26")
RED_DEEP = QColor("#99000f")
RED_DARK = QColor("#2b0004")

STATE_CONFIG = {
    "idle":      dict(pulse_period=3.0, ring_speed=24, particle_rate=0.7, particle_speed=0.8, shimmer=1.0, audio_wave=0.4),
    "listening": dict(pulse_period=1.3, ring_speed=50, particle_rate=2.2, particle_speed=1.3, shimmer=2.0, audio_wave=0.9),
    "thinking":  dict(pulse_period=0.65, ring_speed=120, particle_rate=4.5, particle_speed=2.0, shimmer=3.5, audio_wave=1.2),
    "speaking":  dict(pulse_period=0.35, ring_speed=70, particle_rate=3.0, particle_speed=1.5, shimmer=2.8, audio_wave=1.6),
}

BASE_SIZE = 360.0


def _alpha(color: QColor, a: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


class AICoreWidget(QWidget):
    def __init__(self, parent=None, draw_bg: bool = True):
        super().__init__(parent)
        self.draw_bg = draw_bg
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._state = "idle"
        self._theme = "crimson"
        self._t = 0.0
        self._rng = random.Random(2026)

        self._particles = []
        self._spawn_acc = 0.0
        self._spectrum_levels = [0.2] * 32
        
        # Expanding Shockwave Rings
        self._shockwaves = []
        self._shock_timer = 0.0

        # Matrix Hex Stream Glyphs
        self._matrix_stream = [
            {"x": self._rng.uniform(-160, 160), "y": self._rng.uniform(-160, 160), 
             "val": f"0x{self._rng.randint(10, 99):X}", "spd": self._rng.uniform(15, 40), "alpha": self._rng.uniform(0.3, 0.8)}
            for _ in range(25)
        ]

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # 60 fps
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def set_theme(self, theme_name: str):
        if theme_name in THEME_PALETTES:
            self._theme = theme_name
            self.update()

    def set_state(self, state: str):
        if state in STATE_CONFIG and state != self._state:
            self._state = state
            # Trigger immediate shockwave on state change
            self._shockwaves.append({"r": 30.0, "alpha": 1.0, "spd": 160.0})
            self.update()

    def state(self) -> str:
        return self._state

    def _on_tick(self):
        dt = 0.016
        self._t += dt
        cfg = STATE_CONFIG.get(self._state, STATE_CONFIG["idle"])

        # Update Audio Spectrum Waves
        wave_mult = cfg["audio_wave"]
        for i in range(32):
            target = (0.25 + 0.75 * math.sin(self._t * 7.0 + i * 0.35) ** 2) * wave_mult
            if self._state in ("thinking", "speaking"):
                target += self._rng.uniform(-0.2, 0.3)
            self._spectrum_levels[i] += (target - self._spectrum_levels[i]) * 0.18

        # Spawn Shockwave Rings periodically
        self._shock_timer += dt
        if self._shock_timer > (0.8 if self._state == "speaking" else 2.5):
            self._shock_timer = 0.0
            self._shockwaves.append({"r": 35.0, "alpha": 0.9, "spd": 140.0})

        # Update Shockwaves
        alive_shocks = []
        for sw in self._shockwaves:
            sw["r"] += sw["spd"] * dt
            sw["alpha"] -= 0.6 * dt
            if sw["alpha"] > 0 and sw["r"] < 240:
                alive_shocks.append(sw)
        self._shockwaves = alive_shocks

        # Update Matrix Stream Glyphs
        for g in self._matrix_stream:
            g["y"] += g["spd"] * dt
            if g["y"] > 170:
                g["y"] = -170
                g["x"] = self._rng.uniform(-170, 170)
                g["val"] = f"0x{self._rng.randint(10, 99):X}"

        # Update & Spawn Quantum Embers
        self._spawn_acc += cfg["particle_rate"]
        while self._spawn_acc >= 1.0:
            self._spawn_acc -= 1.0
            angle = self._rng.uniform(0.0, math.tau)
            dist = self._rng.uniform(20.0, 100.0)
            spd = self._rng.uniform(40.0, 110.0) * cfg["particle_speed"]
            life = self._rng.uniform(0.7, 1.8)
            sz = self._rng.uniform(1.5, 4.5)
            self._particles.append({
                "x": math.cos(angle) * dist,
                "y": math.sin(angle) * dist,
                "vx": math.cos(angle) * spd,
                "vy": math.sin(angle) * spd,
                "life": life,
                "max_life": life,
                "sz": sz,
            })

        alive_pts = []
        for p in self._particles:
            p["life"] -= dt
            if p["life"] > 0:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                alive_pts.append(p)
        self._particles = alive_pts

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        palette = THEME_PALETTES.get(self._theme, THEME_PALETTES["crimson"])
        RED_HOT = palette["hot"]
        RED_BRIGHT = palette["bright"]
        RED_CRIMSON = palette["crimson"]
        RED_DEEP = palette["deep"]
        RED_DARK = palette["dark"]

        # Background pitch obsidian / theme bg (if draw_bg is enabled)
        if self.draw_bg:
            painter.fillRect(self.rect(), palette["bg"])

        scale = min(w, h) / BASE_SIZE
        painter.translate(cx, cy)
        painter.scale(scale, scale)

        cfg = STATE_CONFIG.get(self._state, STATE_CONFIG["idle"])
        pulse = 0.5 + 0.5 * math.sin(self._t * math.tau / cfg["pulse_period"])

        # -------------------------------------------------------------
        # 1. Fullscreen Holographic Grid & Scanlines
        # -------------------------------------------------------------
        if self.draw_bg:
            painter.save()
            pen_scan = QPen(_alpha(RED_CRIMSON, 0.10 + 0.05 * pulse), 1)
            painter.setPen(pen_scan)
            for y_line in range(-250, 250, 6):
                painter.drawLine(QPointF(-320, y_line), QPointF(320, y_line))
            painter.restore()

        # -------------------------------------------------------------
        # 2. Matrix Hex Data Stream Rain
        # -------------------------------------------------------------
        painter.save()
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        for g in self._matrix_stream:
            painter.setPen(_alpha(RED_BRIGHT, g["alpha"] * 0.4))
            painter.drawText(QPointF(g["x"], g["y"]), g["val"])
        painter.restore()

        # -------------------------------------------------------------
        # 3. Radiating 32-Bar Audio Spectrum Visualizer
        # -------------------------------------------------------------
        painter.save()
        for i in range(32):
            angle = i * (math.tau / 32)
            lvl = max(0.1, min(1.4, self._spectrum_levels[i]))
            
            r_inner = 125.0
            r_outer = 125.0 + (40.0 * lvl)
            
            x1 = math.cos(angle) * r_inner
            y1 = math.sin(angle) * r_inner
            x2 = math.cos(angle) * r_outer
            y2 = math.sin(angle) * r_outer
            
            bar_col = RED_HOT if lvl > 0.85 else (RED_BRIGHT if lvl > 0.4 else RED_CRIMSON)
            painter.setPen(QPen(_alpha(bar_col, 0.8 + 0.2 * pulse), 2.5))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.restore()

        # -------------------------------------------------------------
        # 4. Expanding Shockwave Pulse Rings
        # -------------------------------------------------------------
        painter.save()
        for sw in self._shockwaves:
            pen_sw = QPen(_alpha(RED_BRIGHT, sw["alpha"] * 0.7), 2)
            painter.setPen(pen_sw)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), sw["r"], sw["r"])
        painter.restore()

        # -------------------------------------------------------------
        # 5. Atmosphere Radial Glow Shield
        # -------------------------------------------------------------
        outer_grad = QRadialGradient(0, 0, 180)
        outer_grad.setColorAt(0.0, _alpha(RED_CRIMSON, 0.38 + 0.15 * pulse))
        outer_grad.setColorAt(0.55, _alpha(RED_DEEP, 0.16 + 0.05 * pulse))
        outer_grad.setColorAt(1.0, _alpha(RED_DARK, 0.0))
        painter.setBrush(QBrush(outer_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), 180, 180)

        # -------------------------------------------------------------
        # 6. 3D Geodesic Wireframe Sphere Globe Mesh & Orbital Rings
        # -------------------------------------------------------------
        painter.save()
        rot_y = self._t * 0.45
        rot_x = self._t * 0.25
        cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
        cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)

        def project_3d(x, y, z):
            # Rotate Y
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            # Rotate X
            y1 = y * cos_x - z1 * sin_x
            z2 = y * sin_x + z1 * cos_x
            # Perspective
            scale_3d = 320.0 / (320.0 + z2)
            return QPointF(x1 * scale_3d, y1 * scale_3d), z2

        # 6a. Latitude 3D Wireframe Rings
        sphere_r = 115.0
        pen_wire = QPen(_alpha(RED_BRIGHT, 0.45 + 0.15 * pulse), 1.2)
        painter.setPen(pen_wire)

        for lat_deg in range(-75, 80, 20):
            lat_rad = math.radians(lat_deg)
            r_lat = sphere_r * math.cos(lat_rad)
            y_lat = sphere_r * math.sin(lat_rad)

            path = QPainterPath()
            first = True
            for lon_deg in range(0, 365, 10):
                lon_rad = math.radians(lon_deg)
                x_3d = r_lat * math.cos(lon_rad)
                z_3d = r_lat * math.sin(lon_rad)
                pt, _z = project_3d(x_3d, y_lat, z_3d)
                if first:
                    path.moveTo(pt)
                    first = False
                else:
                    path.lineTo(pt)
            painter.drawPath(path)

        # 6b. Longitude 3D Wireframe Rings
        for lon_deg in range(0, 180, 24):
            lon_rad = math.radians(lon_deg)
            path = QPainterPath()
            first = True
            for lat_deg in range(-90, 95, 10):
                lat_rad = math.radians(lat_deg)
                r_lat = sphere_r * math.cos(lat_rad)
                y_lat = sphere_r * math.sin(lat_rad)
                x_3d = r_lat * math.cos(lon_rad)
                z_3d = r_lat * math.sin(lon_rad)
                pt, _z = project_3d(x_3d, y_lat, z_3d)
                if first:
                    path.moveTo(pt)
                    first = False
                else:
                    path.lineTo(pt)
            painter.drawPath(path)

        # 6c. 3D Tilted Orbital Gyro Rings (Golden & Pink)
        for ring_idx, (tilt_angle, spd_mult, col_spec, thickness) in enumerate([
            (math.radians(55), 1.2, RED_BRIGHT, 2.2),
            (math.radians(-40), -1.5, RED_HOT, 1.8),
            (math.radians(75), 0.8, RED_CRIMSON, 2.5),
        ]):
            path_orb = QPainterPath()
            r_orb = 135.0 + ring_idx * 6
            rot_orb = self._t * spd_mult * cfg["ring_speed"] * 0.05
            first = True
            for deg in range(0, 365, 8):
                rad = math.radians(deg) + rot_orb
                # Circle in XZ plane tilted around X axis
                x_3d = r_orb * math.cos(rad)
                y_raw = r_orb * math.sin(rad)
                y_3d = y_raw * math.cos(tilt_angle)
                z_3d = y_raw * math.sin(tilt_angle)

                pt, _z = project_3d(x_3d, y_3d, z_3d)
                if first:
                    path_orb.moveTo(pt)
                    first = False
                else:
                    path_orb.lineTo(pt)

            painter.setPen(QPen(_alpha(col_spec, 0.85), thickness))
            painter.drawPath(path_orb)

        painter.restore()

        # -------------------------------------------------------------
        # 7. Ultron Molten Core Iris
        # -------------------------------------------------------------
        core_r = 48.0 + 7.0 * pulse
        core_grad = QRadialGradient(0, 0, core_r)
        core_grad.setColorAt(0.0, RED_HOT)
        core_grad.setColorAt(0.25, RED_BRIGHT)
        core_grad.setColorAt(0.65, RED_CRIMSON)
        core_grad.setColorAt(1.0, _alpha(RED_DEEP, 0.35))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(0, 0), core_r, core_r)

        # Pupil Ring
        painter.setPen(QPen(_alpha(RED_HOT, 0.95), 1.5))
        painter.drawEllipse(QPointF(0, 0), 20 + 2 * pulse, 20 + 2 * pulse)

        # -------------------------------------------------------------
        # 8. Crosshairs & Telemetry Overlay
        # -------------------------------------------------------------
        pen_hud = QPen(_alpha(RED_BRIGHT, 0.7), 1)
        painter.setPen(pen_hud)
        painter.drawLine(QPointF(-160, 0), QPointF(-70, 0))
        painter.drawLine(QPointF(70, 0), QPointF(160, 0))
        painter.drawLine(QPointF(0, -160), QPointF(0, -70))
        painter.drawLine(QPointF(0, 70), QPointF(0, 160))

        # Corner Brackets
        brk_sz = 14
        for bx, by in [(-160, -135), (146, -135), (-160, 125), (146, 125)]:
            painter.drawRect(QRectF(bx, by, brk_sz, brk_sz))

        # -------------------------------------------------------------
        # 9. Quantum Embers
        # -------------------------------------------------------------
        for p in self._particles:
            ratio = p["life"] / p["max_life"]
            alpha = math.sin(ratio * math.pi)
            pt_col = _alpha(RED_BRIGHT if self._rng.random() > 0.3 else RED_HOT, alpha)
            painter.setBrush(QBrush(pt_col))
            painter.setPen(Qt.NoPen)
            sz = p["sz"] * (0.6 + 0.4 * ratio)
            painter.drawEllipse(QPointF(p["x"], p["y"]), sz, sz)

        painter.end()
