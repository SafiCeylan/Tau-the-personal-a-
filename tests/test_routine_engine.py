# -*- coding: utf-8 -*-
import unittest
from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from core.layers.routine_engine import RoutineEngine

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()

class TestRoutineEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RoutineEngine()

    def test_uygulama_surec_modu_tetikle(self):
        triggered, msg = self.engine.uygulama_surec_modu_tetikle("code.exe")
        self.assertTrue(triggered)
        self.assertIn("ÇALIŞMA MOD", msg)

        triggered_game, msg_game = self.engine.uygulama_surec_modu_tetikle("discord.exe")
        self.assertTrue(triggered_game)
        self.assertIn("OYUN MOD", msg_game)

        triggered_none, _ = self.engine.uygulama_surec_modu_tetikle("notepad.exe")
        self.assertFalse(triggered_none)

if __name__ == "__main__":
    unittest.main()
