# -*- coding: utf-8 -*-
"""
ULTRON — Deep Media Integration Unit Tests
"""

import unittest
from unittest.mock import patch

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from features.actions import media_deep

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()


class TestMediaDeep(unittest.TestCase):

    def test_spotify_cal(self):
        with patch('subprocess.Popen') as mock_popen:
            status, res = media_deep.spotify_cal("Barış Manço")
            self.assertTrue(status)
            self.assertIn("Barış Manço", res)

    def test_calan_sarki_bilgisi(self):
        with patch('features.actions.media_deep.get_currently_playing_track', return_value={"playing": True, "title": "Gülpembe", "artist": "Barış Manço", "album": "Best of"}):
            status, res = media_deep.calan_sarki_bilgisi()
            self.assertTrue(status)
            self.assertIn("Gülpembe", res)
            self.assertIn("Barış Manço", res)

    def test_medya_derin_komutu_isle(self):
        res_calan = media_deep.medya_derin_komutu_isle("şu an ne çalıyor")
        self.assertIsNotNone(res_calan)
        
        with patch('subprocess.Popen'):
            res_spotify = media_deep.medya_derin_komutu_isle("spotify'da Tarkan çal")
            self.assertIsNotNone(res_spotify)
            self.assertIn("Spotify", res_spotify["sonuc"])


if __name__ == "__main__":
    unittest.main()
