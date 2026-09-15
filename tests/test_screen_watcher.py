# -*- coding: utf-8 -*-
"""
ULTRON — Smart Screen Watcher Unit Tests
"""

import unittest
from unittest.mock import patch, MagicMock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from features import screen_watcher

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()


class TestScreenWatcher(unittest.TestCase):

    def tearDown(self):
        screen_watcher.takip_durdur()

    def test_ekran_takip_niyeti_algila(self):
        self.assertTrue(screen_watcher.ekran_takip_niyeti_algila("ekranda Notepad çıkınca haber ver"))
        self.assertTrue(screen_watcher.ekran_takip_niyeti_algila("ekranda İndirme Bitti görünce uyar"))
        self.assertTrue(screen_watcher.ekran_takip_niyeti_algila("ekran takibini durdur"))
        self.assertFalse(screen_watcher.ekran_takip_niyeti_algila("bugün hava nasıl"))

    def test_takip_baslat_ve_durdur(self):
        res = screen_watcher.takip_baslat("TestMetin")
        self.assertIn("Ekran Takibi Başlatıldı", res)
        self.assertIn("TestMetin", res)
        
        status = screen_watcher.takip_durumu()
        self.assertIn("Ekran Takibi Aktif", status)
        
        stop_res = screen_watcher.takip_durdur()
        self.assertIn("Ekran Takibi Durduruldu", stop_res)

    def test_ekran_takip_komutu_isle(self):
        res_durdur = screen_watcher.ekran_takip_komutu_isle("ekran takibini durdur")
        self.assertIsNotNone(res_durdur)
        self.assertIn("Aktif bir ekran takibi bulunmuyor", res_durdur["sonuc"])

        res_baslat = screen_watcher.ekran_takip_komutu_isle("ekranda Yükleme Tamamlandı çıkınca haber ver")
        self.assertIsNotNone(res_baslat)
        self.assertIn("Ekran Takibi Başlatıldı", res_baslat["sonuc"])


if __name__ == "__main__":
    unittest.main()
