"""
AICoreWidget — TAU'nun altın/amber holografik "AI çekirdeği".

Tamamen native QPainter ile çizilir (web view / tarayıcı bileşeni YOK).
Merkezde içi boş parlak bir "göz/portal" halkası, etrafında dönen ince
enerji halkaları, pusula gibi yayılan ışın çizgileri, devre-kartı benzeri
ince hatlar ve dışa doğru süzülen kıvılcım parçacıkları içerir.

Durum (idle / listening / thinking / speaking) nabız hızını, halka dönüş
hızını ve parçacık yoğunluğunu değiştirir.
"""

import math
import random

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QRadialGradient, QPen, QPainterPath, QBrush
)
from PyQt5.QtWidgets import QWidget, QSizePolicy

GOLD_HOT = QColor("#fff3d6")
GOLD_BRIGHT = QColor("#ffd873")
GOLD = QColor("#f2b544")
GOLD_DEEP = QColor("#c9821f")

STATE_CONFIG = {
    "idle":      dict(pulse_period=4.0, ring_speed=14, particle_rate=0.35, particle_speed=0.55, shimmer=1.0),
    "listening": dict(pulse_period=1.7, ring_speed=32, particle_rate=1.1, particle_speed=0.85, shimmer=1.6),
    "thinking":  dict(pulse_period=1.0, ring_speed=85, particle_rate=2.6, particle_speed=1.35, shimmer=2.4),
    "speaking":  dict(pulse_period=0.55, ring_speed=40, particle_rate=1.8, particle_speed=1.05, shimmer=2.0),
}

BASE_SIZE = 300.0  # tasarımın temel referans boyutu (px), her şey buna oranlanır


def _alpha(color: QColor, a: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


class AICoreWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(200)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._state = "idle"
        self._t = 0.0
        self._rng = random.Random()

        self._rays = self._build_rays()
        self._traces = self._build_traces()
        self._particles = []
        self._spawn_acc = 0.0
        self._bokeh = self._build_bokeh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 fps

    # ---------------- public API ----------------

    def set_state(self, state: str):
        if state in STATE_CONFIG and state != self._state:
            self._state = state
            self.update()

    # ---------------- procedural generation ----------------

    def _build_rays(self):
        rays = []
        count = 36
        for i in range(count):
            angle = (i / count) * 2 * math.pi
            major = (i % 4 == 0)
            r_outer = (0.43 + self._rng.random() * 0.03) if major else (0.31 + self._rng.random() * 0.07)
            rays.append(dict(
                angle=angle, major=major, r_inner=0.21, r_outer=r_outer,
                phase=self._rng.random() * 2 * math.pi,
                width=1.7 if major else 0.8,
                o_min=0.16 if major else 0.06, o_max=0.62 if major else 0.30,
            ))
        return rays

    def _build_traces(self):
        traces = []
        for _ in range(7):
            angle = self._rng.random() * 2 * math.pi
            start_r = 0.32 + self._rng.random() * 0.03
            x0 = math.cos(angle) * start_r
            y0 = math.sin(angle) * start_r
            seg1 = 0.06 + self._rng.random() * 0.06
            x1 = x0 + math.cos(angle) * seg1
            y1 = y0 + math.sin(angle) * seg1
            seg2 = 0.05 + self._rng.random() * 0.05
            dir_x = 1 if math.cos(angle) >= 0 else -1
            dir_y = 1 if math.sin(angle) >= 0 else -1
            if self._rng.random() > 0.5:
                x2, y2 = x1 + dir_x * seg2, y1
            else:
                x2, y2 = x1, y1 + dir_y * seg2
            traces.append(dict(points=[(x0, y0), (x1, y1), (x2, y2)], phase=self._rng.random() * 2 * math.pi))
        return traces

    def _build_bokeh(self):
        dots = []
        for _ in range(10):
            dots.append(dict(
                x=self._rng.uniform(-0.9, 0.9), y=self._rng.uniform(-0.9, 0.9),
                r=self._rng.uniform(0.05, 0.16), phase=self._rng.random() * 2 * math.pi,
                speed=self._rng.uniform(0.15, 0.4),
                vx=self._rng.uniform(-0.01, 0.01), vy=self._rng.uniform(-0.01, 0.01),
            ))
        return dots

    # ---------------- animation loop ----------------

    def _tick(self):
        cfg = STATE_CONFIG[self._state]
        self._t += 0.033

        self._spawn_acc += cfg["particle_rate"]
        while self._spawn_acc >= 1:
            self._spawn_particle()
            self._spawn_acc -= 1

        alive = []
        for p in self._particles:
            p["age"] += 1
            p["dist"] += cfg["particle_speed"] * 0.012
            if p["age"] < p["life"]:
                alive.append(p)
        self._particles = alive

        for d in self._bokeh:
            d["x"] += d["vx"] * 0.05
            d["y"] += d["vy"] * 0.05
            if d["x"] < -1: d["x"] = 1
            if d["x"] > 1: d["x"] = -1
            if d["y"] < -1: d["y"] = 1
            if d["y"] > 1: d["y"] = -1

        self.update()

    def _spawn_particle(self):
        angle = self._rng.random() * 2 * math.pi
        self._particles.append(dict(angle=angle, dist=0.11, age=0, life=self._rng.randint(45, 75),
                                     size=self._rng.uniform(1.1, 2.4)))

    # ---------------- painting ----------------

    def paintEvent(self, event):
        cfg = STATE_CONFIG[self._state]
        side = min(self.width(), self.height() if self.height() > 0 else self.width())
        scale = side / BASE_SIZE * 0.86
        cx, cy = self.width() / 2.0, self.height() / 2.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(cx, cy)

        self._paint_bokeh(painter, scale)
        self._paint_ambient_glow(painter, scale, cfg)
        self._paint_rays(painter, scale, cfg)
        self._paint_traces(painter, scale)
        self._paint_rings(painter, scale, cfg)
        self._paint_sphere(painter, scale, cfg)
        self._paint_eye(painter, scale, cfg)
        self._paint_particles(painter, scale, cfg)

        painter.end()

    def _paint_bokeh(self, p: QPainter, scale):
        for d in self._bokeh:
            alpha = 0.05 + 0.08 * (0.5 + 0.5 * math.sin(self._t * d["speed"] + d["phase"]))
            r = d["r"] * BASE_SIZE * scale
            x, y = d["x"] * BASE_SIZE * scale, d["y"] * BASE_SIZE * scale
            grad = QRadialGradient(QPointF(x, y), r)
            grad.setColorAt(0, _alpha(GOLD_BRIGHT, alpha))
            grad.setColorAt(1, _alpha(GOLD_BRIGHT, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(x, y), r, r)

    def _paint_ambient_glow(self, p: QPainter, scale, cfg):
        pulse = 0.5 + 0.5 * math.sin(self._t * (2 * math.pi / cfg["pulse_period"]))
        r = (95 + 18 * pulse) * scale
        grad = QRadialGradient(QPointF(0, 0), r)
        grad.setColorAt(0, _alpha(GOLD, 0.30 + 0.18 * pulse))
        grad.setColorAt(0.6, _alpha(GOLD, 0.05))
        grad.setColorAt(1, _alpha(GOLD, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(0, 0), r, r)

    def _paint_rays(self, p: QPainter, scale, cfg):
        for ray in self._rays:
            shimmer = 0.5 + 0.5 * math.sin(self._t * cfg["shimmer"] * 1.1 + ray["phase"])
            alpha = ray["o_min"] + (ray["o_max"] - ray["o_min"]) * shimmer
            r_in = ray["r_inner"] * BASE_SIZE * scale
            r_out = ray["r_outer"] * BASE_SIZE * scale
            x1, y1 = math.cos(ray["angle"]) * r_in, math.sin(ray["angle"]) * r_in
            x2, y2 = math.cos(ray["angle"]) * r_out, math.sin(ray["angle"]) * r_out
            pen = QPen(_alpha(GOLD, alpha), ray["width"] * scale)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _paint_traces(self, p: QPainter, scale):
        pen = QPen(_alpha(GOLD_DEEP, 0.38), 1.0)
        p.setPen(pen)
        for trace in self._traces:
            path = QPainterPath()
            pts = [(x * BASE_SIZE * scale, y * BASE_SIZE * scale) for x, y in trace["points"]]
            path.moveTo(*pts[0])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            p.drawPath(path)

            blink = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(self._t * 2.6 + trace["phase"]))
            p.setPen(Qt.NoPen)
            p.setBrush(_alpha(GOLD_BRIGHT, blink))
            nx, ny = pts[-1]
            p.drawEllipse(QPointF(nx, ny), 2.4 * scale, 2.4 * scale)
            p.setPen(pen)

    def _paint_rings(self, p: QPainter, scale, cfg):
        angle_outer = (self._t * cfg["ring_speed"]) % 360
        angle_mid = (-self._t * cfg["ring_speed"] * 0.6) % 360
        self._draw_arc_ring(p, 0.35 * BASE_SIZE * scale, angle_outer, 2.4 * scale, GOLD, 0.55)
        self._draw_arc_ring(p, 0.35 * BASE_SIZE * scale, angle_outer + 180, 2.4 * scale, GOLD, 0.55)
        self._draw_arc_ring(p, 0.26 * BASE_SIZE * scale, angle_mid, 1.8 * scale, GOLD_BRIGHT, 0.5)
        self._draw_arc_ring(p, 0.26 * BASE_SIZE * scale, angle_mid + 150, 1.8 * scale, GOLD_BRIGHT, 0.5)

    def _draw_arc_ring(self, p: QPainter, radius, start_deg, width, color, alpha):
        rect = QRectF(-radius, -radius, radius * 2, radius * 2)
        pen = QPen(_alpha(color, alpha), width)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawArc(rect, int(start_deg * 16), int(38 * 16))

    def _paint_sphere(self, p: QPainter, scale, cfg):
        pulse = 0.5 + 0.5 * math.sin(self._t * (2 * math.pi / cfg["pulse_period"]))
        base_r = 0.20 * BASE_SIZE * scale
        r = base_r * (1.0 + 0.09 * pulse)

        # bloom (katmanlı, azalan opaklıkla)
        for i, (mult, a) in enumerate([(1.9, 0.05), (1.5, 0.08), (1.15, 0.14)]):
            p.setPen(Qt.NoPen)
            p.setBrush(_alpha(GOLD, a))
            p.drawEllipse(QPointF(0, 0), r * mult, r * mult)

        grad = QRadialGradient(QPointF(-r * 0.18, -r * 0.24), r * 1.05)
        grad.setColorAt(0.0, GOLD_HOT)
        grad.setColorAt(0.25, GOLD_BRIGHT)
        grad.setColorAt(0.55, GOLD)
        grad.setColorAt(0.85, GOLD_DEEP)
        grad.setColorAt(1.0, _alpha(GOLD_DEEP, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(0, 0), r, r)

    def _paint_eye(self, p: QPainter, scale, cfg):
        fast_pulse = 0.5 + 0.5 * math.sin(self._t * (2 * math.pi / (cfg["pulse_period"] * 0.5)))
        r = 0.095 * BASE_SIZE * scale

        for mult, a in [(2.3, 0.06), (1.7, 0.10), (1.25, 0.16 + 0.1 * fast_pulse)]:
            p.setPen(Qt.NoPen)
            p.setBrush(_alpha(GOLD_BRIGHT, a))
            p.drawEllipse(QPointF(0, 0), r * mult, r * mult)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#050506"))
        p.drawEllipse(QPointF(0, 0), r, r)

        pen = QPen(_alpha(GOLD_BRIGHT, 0.85 + 0.15 * fast_pulse), 0.17 * BASE_SIZE * scale * 0.32)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), r * 0.86, r * 0.86)

    def _paint_particles(self, p: QPainter, scale, cfg):
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for particle in self._particles:
            life_ratio = particle["age"] / particle["life"]
            alpha = math.sin(life_ratio * math.pi) * 0.85
            if alpha <= 0.01:
                continue
            dist = particle["dist"] * BASE_SIZE * scale
            x = math.cos(particle["angle"]) * dist
            y = math.sin(particle["angle"]) * dist
            size = particle["size"] * scale
            grad = QRadialGradient(QPointF(x, y), size * 2.2)
            grad.setColorAt(0, _alpha(GOLD_HOT, alpha))
            grad.setColorAt(1, _alpha(GOLD_BRIGHT, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(x, y), size * 2.2, size * 2.2)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
