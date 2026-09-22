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


class ModelListesiTazelemeTest(unittest.TestCase):
    """22 Eyl: yeni indirilen model menüde görünmüyordu (liste yalnız açılışta çekiliyordu)."""

    def test_sayfa_acilinca_liste_yeniden_cekilir(self):
        from unittest.mock import patch
        with patch.object(SettingsViewWidget, '_list_ollama_models',
                          return_value=['qwen2.5:7b']):
            w = SettingsViewWidget(dict(TEMEL_CONFIG))
        self.addCleanup(w.deleteLater)
        self.assertEqual(w.ollama_model_combo.count(), 1)

        # Kullanıcı bu sırada `ollama pull qwen3:4b-instruct` çalıştırdı
        with patch.object(SettingsViewWidget, '_list_ollama_models',
                          return_value=['qwen2.5:7b', 'qwen3:4b-instruct']):
            w.show()
            w.hide()
        adlar = [w.ollama_model_combo.itemText(i) for i in range(w.ollama_model_combo.count())]
        self.assertIn('qwen3:4b-instruct', adlar)

    def test_secili_model_tazelemede_korunur(self):
        from unittest.mock import patch
        with patch.object(SettingsViewWidget, '_list_ollama_models',
                          return_value=['qwen2.5:7b', 'qwen2.5:3b']):
            w = SettingsViewWidget(dict(TEMEL_CONFIG))
            self.addCleanup(w.deleteLater)
            w.show()
            w.hide()
        self.assertEqual(w.ollama_model_combo.currentText(), 'qwen2.5:7b')

    def test_ollama_kapaliysa_cokmez(self):
        from unittest.mock import patch
        with patch.object(SettingsViewWidget, '_list_ollama_models', return_value=[]):
            w = SettingsViewWidget(dict(TEMEL_CONFIG))
            self.addCleanup(w.deleteLater)
            w.show()
            w.hide()
        # Kayıtlı model yazı olarak korunur ki "Kaydet" onu silmesin
        self.assertEqual(w.ollama_model_combo.currentText(), 'qwen2.5:7b')


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


# 16 Eyl 2026'da bu makinede ölçülen MME giriş aygıtları
OLCULEN_AYGITLAR = [
    (0, 'Microsoft Ses Eşleştiricisi - Input'),
    (1, 'Stereo Karışımı (Realtek(R) Aud'),
    (2, 'Mikrofon Dizisi (Realtek(R) Aud'),
]


class AyarlarMikrofonTest(unittest.TestCase):
    """Hoparlör kaydı listede yok, aygıt adıyla saklanır, eski yanlış ayar görünür uyarı verir."""

    def _ekran(self, config_eki=None, aygitlar=OLCULEN_AYGITLAR):
        from unittest.mock import patch
        cfg = dict(TEMEL_CONFIG)
        cfg.update(config_eki or {})
        with patch('features.mic_devices.giris_aygitlari', return_value=aygitlar):
            w = SettingsViewWidget(cfg)
        self.addCleanup(w.deleteLater)
        return w

    def _menudeki_adlar(self, w):
        return [w.mic_combo.itemText(i) for i in range(w.mic_combo.count())]

    def test_hoparlor_kaydi_menude_YOK(self):
        adlar = self._menudeki_adlar(self._ekran())
        self.assertFalse(any('Stereo Karışımı' in a for a in adlar), adlar)
        self.assertFalse(any('Eşleştiricisi' in a for a in adlar), adlar)
        self.assertTrue(any('Mikrofon Dizisi' in a for a in adlar), adlar)

    def test_16_eyl_yanlis_ayari_gorunur_uyari_verir(self):
        w = self._ekran({'mic_device_index': 1})
        self.assertEqual(w.mic_combo.currentData(), -1)
        self.assertFalse(w.mic_uyari_lbl.isHidden())
        self.assertIn('mikrofon değil', w.mic_uyari_lbl.text())

    def test_kayitli_ad_numara_kaysa_da_secilir(self):
        kaymis = [(0, 'Microsoft Ses Eşleştiricisi - Input'),
                  (4, 'Mikrofon Dizisi (Realtek(R) Aud')]
        w = self._ekran({'mic_device_index': 2,
                         'mic_device_name': 'Mikrofon Dizisi (Realtek(R) Aud'}, kaymis)
        self.assertEqual(w.mic_combo.currentData(), 4)
        self.assertTrue(w.mic_uyari_lbl.isHidden())

    def test_kaydetme_adi_da_yazar(self):
        from unittest.mock import patch
        w = self._ekran()
        w.mic_combo.setCurrentIndex(w.mic_combo.findData(2))
        kaydedilen = []
        w.config_saved.connect(kaydedilen.append)
        with patch('ui.components.settings_view.QMessageBox.information'):
            w.save_settings()
        self.assertEqual(kaydedilen[-1]['mic_device_index'], 2)
        self.assertEqual(kaydedilen[-1]['mic_device_name'], 'Mikrofon Dizisi (Realtek(R) Aud')

    def test_sistem_varsayilani_kaydedilince_ad_bos(self):
        from unittest.mock import patch
        w = self._ekran({'mic_device_name': 'Mikrofon Dizisi (Realtek(R) Aud'})
        w.mic_combo.setCurrentIndex(0)
        kaydedilen = []
        w.config_saved.connect(kaydedilen.append)
        with patch('ui.components.settings_view.QMessageBox.information'):
            w.save_settings()
        self.assertEqual(kaydedilen[-1]['mic_device_index'], -1)
        self.assertEqual(kaydedilen[-1]['mic_device_name'], '')

    def test_seviye_cubugu_ve_telegram_sesli_yanit_alani_var(self):
        w = self._ekran()
        for alan in ('mic_level_bar', 'mic_durum_lbl', 'mic_test_btn', 'tg_voice_reply_check'):
            self.assertTrue(hasattr(w, alan), f'{alan} eksik')
        self.assertTrue(w.tg_voice_reply_check.isChecked())  # varsayılan açık

    def test_mikrofon_testi_sonucu_yazar_ve_dugmeyi_geri_acar(self):
        """Gerçek mikrofona dokunmadan test bitişi: tepe %25 → 'hazır'."""
        w = self._ekran()
        w.mic_test_btn.setEnabled(False)
        w._mic_tepe_max = 0.25
        w._mikrofon_testini_bitir()
        self.assertTrue(w.mic_test_btn.isEnabled())
        self.assertIn('hazır', w.mic_durum_lbl.text())
        self.assertEqual(w.mic_level_bar.value(), 0)


if __name__ == '__main__':
    unittest.main()
