# -*- coding: utf-8 -*-
"""
ULTRON — Full Duplex Speech State Unit Tests
"""

import unittest
from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from features import speech

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()


class TestSpeechDuplex(unittest.TestCase):

    def tearDown(self):
        speech.set_duplex_voice_active(False)

    def test_duplex_state_toggle(self):
        self.assertFalse(speech.is_duplex_voice_active())
        speech.set_duplex_voice_active(True)
        self.assertTrue(speech.is_duplex_voice_active())
        speech.set_duplex_voice_active(False)
        self.assertFalse(speech.is_duplex_voice_active())


if __name__ == "__main__":
    unittest.main()
