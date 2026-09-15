# -*- coding: utf-8 -*-
"""
ULTRON — Floating Desktop Avatar Unit Tests
"""

import sys
import unittest
from PyQt5.QtWidgets import QApplication

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()

# Ensure single QApplication instance for unit tests
app = QApplication.instance() or QApplication(sys.argv)

from ui.components.floating_avatar import UltronFloatingAvatar
from ui.components.floating_chat_bubble import FloatingChatBubble


class TestFloatingAvatar(unittest.TestCase):

    def setUp(self):
        self.avatar = UltronFloatingAvatar()

    def tearDown(self):
        if hasattr(self, 'avatar') and self.avatar:
            self.avatar.close()

    def test_avatar_initialization(self):
        self.assertIsNotNone(self.avatar)
        self.assertEqual(self.avatar.width(), 160)
        self.assertEqual(self.avatar.height(), 160)

    def test_theme_and_state(self):
        self.avatar.set_theme("gold")
        if self.avatar.core_widget:
            self.assertEqual(self.avatar.core_widget._theme, "gold")

        self.avatar.set_state("thinking")
        if self.avatar.core_widget:
            self.assertEqual(self.avatar.core_widget.state(), "thinking")

    def test_toggle_chat_bubble(self):
        self.assertFalse(self.avatar.chat_bubble.isVisible())
        self.avatar.toggle_chat_bubble()
        self.assertTrue(self.avatar.chat_bubble.isVisible())
        self.avatar.toggle_chat_bubble()
        self.assertFalse(self.avatar.chat_bubble.isVisible())

    def test_bubble_response(self):
        self.avatar.set_response("Test Yanıtı")
        self.assertTrue(self.avatar.chat_bubble.isVisible())
        self.assertIn("Test Yanıtı", self.avatar.chat_bubble.txt_response.toPlainText())

    def test_cursor_tracking_toggle(self):
        self.assertFalse(self.avatar._cursor_tracking)
        self.avatar.toggle_cursor_tracking(True)
        self.assertTrue(self.avatar._cursor_tracking)
        self.avatar.toggle_cursor_tracking(False)
        self.assertFalse(self.avatar._cursor_tracking)

    def test_dropped_file_signal(self):
        submitted = []
        self.avatar.command_submitted.connect(lambda cmd: submitted.append(cmd))
        from unittest.mock import patch
        with patch('os.path.exists', return_value=True):
            self.avatar.process_dropped_file("test_raporu.pdf")
        self.assertEqual(len(submitted), 1)
        self.assertIn("test_raporu.pdf", submitted[0])


if __name__ == "__main__":
    unittest.main()
