# -*- coding: utf-8 -*-
"""
AYARLAR EKRANI — çizim ve kaydetme duman testi.

Bu ekranın hiç testi yoktu; alan eklerken bir yazım hatası yapmak uygulamayı
AÇILIŞTA çökertir ve bunu ancak canlıda fark edersin. Testler ağır değil:
ekran kuruluyor mu, webhook alanları config'e doğru gidiyor mu, kötü girdi
(boş port, harf) çökertiyor mu?
"""
import sys
import unittest

from PyQt5.QtWidgets import QApplication

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


app = QApplication.instance() or QApplication(sys.argv)

from ui.components.settings_view import SettingsViewWidget  # noqa: E402


TEMEL_CONFIG = {
    "ai_provider": "ollama",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5:7b",
    "webhook_enabled": False,
    "webhook_port": 8899,
    "webhook_token": "",
}


class AyarlarCizimTest(unittest.TestCase):

    def setUp(self):
        self.w = SettingsViewWidget(dict(TEMEL_CONFIG))

    def tearDown(self):
        self.w.deleteLater()

    def test_ekran_kuruluyor(self):
        self.assertIsNotNone(self.w)

    def test_webhook_alanlari_var(self):
        for alan in ('webhook_check', 'webhook_port_in',
                     'webhook_token_in', 'webhook_token_btn'):
            self.assertTrue(hasattr(self.w, alan), f'{alan} eksik')

    def test_webhook_varsayilani_KAPALI(self):
        """Bu sunucu komut çalıştırıyor — varsayılan açık olamaz."""
        self.assertFalse(self.w.webhook_check.isChecked())

    def test_token_alani_gizli_baslar(self):
        from PyQt5.QtWidgets import QLineEdit
        self.assertEqual(self.w.webhook_token_in.echoMode(), QLineEdit.Password)

    def test_mevcut_config_alanlara_yansir(self):
        cfg = dict(TEMEL_CONFIG)
        cfg.update({"webhook_enabled": True, "webhook_port": 9100,
                    "webhook_token": "abcdefghijklmnop"})
        w = SettingsViewWidget(cfg)
        try:
            self.assertTrue(w.webhook_check.isChecked())
            self.assertEqual(w.webhook_port_in.text(), "9100")
            self.assertEqual(w.webhook_token_in.text(), "abcdefghijklmnop")
        finally:
            w.deleteLater()


class AyarlarKaydetmeTest(unittest.TestCase):

    def setUp(self):
        self.w = SettingsViewWidget(dict(TEMEL_CONFIG))
        self.kaydedilen = []
        self.w.config_saved.connect(self.kaydedilen.append)

    def tearDown(self):
        self.w.deleteLater()

    def _kaydet(self):
        # QMessageBox.information'ı sustur — test diyalog açmasın
        from unittest.mock import patch
        with patch('ui.components.settings_view.QMessageBox.information'):
            self.w.save_settings()
        self.assertTrue(self.kaydedilen, 'config_saved sinyali hiç gelmedi')
        return self.kaydedilen[-1]

    def test_webhook_ayarlari_kaydedilir(self):
        self.w.webhook_check.setChecked(True)
        self.w.webhook_port_in.setText("9300")
        self.w.webhook_token_in.setText("bu-token-yeterince-uzundur")

        cfg = self._kaydet()
        self.assertTrue(cfg["webhook_enabled"])
        self.assertEqual(cfg["webhook_port"], 9300)
        self.assertEqual(cfg["webhook_token"], "bu-token-yeterince-uzundur")

    def test_bozuk_port_varsayilana_duser(self):
        """Harf girilirse çökmemeli, 8899'a düşmeli."""
        self.w.webhook_port_in.setText("port yok")
        cfg = self._kaydet()
        self.assertEqual(cfg["webhook_port"], 8899)

    def test_bos_port_varsayilana_duser(self):
        self.w.webhook_port_in.setText("")
        cfg = self._kaydet()
        self.assertEqual(cfg["webhook_port"], 8899)

    def test_token_ureteci_uzun_token_yazar(self):
        from unittest.mock import patch
        from features.webhook_api import ASGARI_TOKEN_UZUNLUGU
        with patch('ui.components.settings_view.QMessageBox.information'):
            self.w._webhook_token_uret()
        self.assertGreaterEqual(len(self.w.webhook_token_in.text()),
                                ASGARI_TOKEN_UZUNLUGU)


if __name__ == '__main__':
    unittest.main()
