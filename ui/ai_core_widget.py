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

# Ultron Palette
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._state = "idle"
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

        # Background pitch obsidian
        painter.fillRect(self.rect(), QColor("#050204"))

        scale = min(w, h) / BASE_SIZE
        painter.translate(cx, cy)
        painter.scale(scale, scale)

        cfg = STATE_CONFIG.get(self._state, STATE_CONFIG["idle"])
        pulse = 0.5 + 0.5 * math.sin(self._t * math.tau / cfg["pulse_period"])

        # -------------------------------------------------------------
        # 1. Fullscreen Holographic Grid & Scanlines
        # -------------------------------------------------------------
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
        # 6. Multi-Ring Gear & Radar HUD
        # -------------------------------------------------------------
        ring1_angle = self._t * cfg["ring_speed"]
        ring2_angle = -self._t * (cfg["ring_speed"] * 1.4)
        radar_angle = self._t * 130.0

        # Ring 1: Gear Ring
        painter.save()
        painter.rotate(ring1_angle)
        pen_gear = QPen(_alpha(RED_BRIGHT, 0.9), 1.5)
        painter.setPen(pen_gear)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0, 0), 105, 105)
        
        for i in range(24):
            a = i * (math.tau / 24)
            x1 = math.cos(a) * 100
            y1 = math.sin(a) * 100
            x2 = math.cos(a) * 110
            y2 = math.sin(a) * 110
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.restore()

        # Ring 2: Segment Arc Ring
        painter.save()
        painter.rotate(ring2_angle)
        pen_arc = QPen(_alpha(RED_CRIMSON, 0.8), 2.5)
        painter.setPen(pen_arc)
        for i in range(4):
            start_deg = i * 90 + (self._t * 18 % 360)
            painter.drawArc(QRectF(-90, -90, 180, 180), int(start_deg * 16), int(60 * 16))
        painter.restore()

        # Radar Sweep Line
        painter.save()
        painter.rotate(radar_angle)
        radar_grad = QLinearGradient(0, 0, 120, 0)
        radar_grad.setColorAt(0.0, _alpha(RED_HOT, 0.9))
        radar_grad.setColorAt(1.0, _alpha(RED_CRIMSON, 0.0))
        painter.setPen(QPen(QBrush(radar_grad), 2))
        painter.drawLine(QPointF(0, 0), QPointF(120, 0))
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

        # Telemetry Text Labels
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(_alpha(RED_BRIGHT, 0.9))
        
        painter.drawText(QPointF(-170, -143), f"[CORE: {int(98 + pulse*2)}%]")
        painter.drawText(QPointF(100, -143), f"[STATE: {self._state.upper()}]")
        painter.drawText(QPointF(-170, 150), "[FREQ: 432Hz]")
        painter.drawText(QPointF(105, 150), f"[TEMP: {int(310 + pulse*5)}K]")

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
