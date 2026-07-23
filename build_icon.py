# -*- coding: utf-8 -*-
"""Ultron kırmızı çekirdek ikonunu .ico olarak üretir (installer için)."""
import sys

from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication


def ciz(boyut: int) -> QPixmap:
    pm = QPixmap(boyut, boyut)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    k = boyut / 64.0
    p.setPen(QPen(QColor('#ff1a26'), 5 * k))
    p.setBrush(QBrush(QColor(18, 4, 6)))
    p.drawEllipse(int(5 * k), int(5 * k), int(54 * k), int(54 * k))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor('#ff1a26')))
    p.drawEllipse(int(22 * k), int(22 * k), int(20 * k), int(20 * k))
    p.setBrush(QBrush(QColor('#ffffff')))
    p.drawEllipse(int(29 * k), int(29 * k), int(6 * k), int(6 * k))
    p.end()
    return pm


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ciz(256).save('ultron.ico', 'ICO')
    print('ultron.ico uretildi')
