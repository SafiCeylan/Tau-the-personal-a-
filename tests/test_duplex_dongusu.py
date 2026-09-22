# -*- coding: utf-8 -*-
"""
CANLI SESLİ SOHBET DÖNGÜSÜ — cevaptan sonra gerçekten dinlemeye dönüyor mu?

NEDEN VAR (16 Eyl 2026): `_konusma_bitince_duplex_devam` 13 Ağu'dan beri
`self._on_wake_word` çağırıyordu; sınıfta öyle bir metot yoktu. QTimer geri
çağrısındaki AttributeError'ı Qt yuttu → canlı sohbet ilk cevaptan sonra hiç
dinlemeye dönmedi. Ayrıca TTS kapalıyken devam tetiği HİÇ kurulmuyordu.

Pencerenin tamamını kurmak (DB, thread'ler, tepsi) gerekmesin diye metotlar
sahte bir `self` ile çağrılır — sınanan kod gerçek metot gövdesidir.
"""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt5 import QtWebEngineWidgets  # noqa: F401  — QApplication'dan ÖNCE (bkz. conftest.py)
from PyQt5.QtWidgets import QApplication

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


app = QApplication.instance() or QApplication(sys.argv)

from ui import tau_window as tw  # noqa: E402
from features import speech  # noqa: E402

Pencere = tw.TauMainWindow


def _sahte_pencere(config=None):
    """Pencerenin tamamını kurmadan gerçek metot gövdelerini çalıştırmak için
    sahte `self`. Karar uygulayıcı GERÇEK metottur — sınanan şey o."""
    p = SimpleNamespace(
        controller=SimpleNamespace(config=dict(config or {})),
        wake_worker=None,
        listen_worker=None,
        _post_assistant=MagicMock(),
        _set_ai_state=MagicMock(),
        on_user_send_message=MagicMock(),
        _on_wake_detected=MagicMock(),
    )
    p._duplex_kararini_uygula = lambda eylem, mesaj: Pencere._duplex_kararini_uygula(
        p, eylem, mesaj)
    return p


class DuplexDevamTest(unittest.TestCase):

    def tearDown(self):
        speech.set_duplex_voice_active(False)

    def test_devam_tetigi_VAR_OLAN_metoda_kurulur(self):
        speech.set_duplex_voice_active(True)
        p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot') as tek_atis:
            Pencere._konusma_bitince_duplex_devam(p)
        tek_atis.assert_called_once()
        hedef = tek_atis.call_args[0][1]
        self.assertIs(hedef, p._on_wake_detected)
        self.assertTrue(hasattr(Pencere, '_on_wake_detected'))

    def test_konusma_baslayinca_oturum_durumu_guncellenir(self):
        from features.duplex import KONUSUYOR, OTURUM
        OTURUM.baslat()
        p = _sahte_pencere({'tts_enabled': True, 'tts_engine': 'edge'})
        p._track_worker = MagicMock()
        p._konusma_bitince_duplex_devam = MagicMock()
        with patch.object(tw, 'FuncWorkerThread') as isci:
            Pencere._speak(p, 'Hava 20 derece.')
        self.assertEqual(OTURUM.durum, KONUSUYOR)
        isci.assert_called_once()
        OTURUM.kapat()

    def test_duplex_kapaliyken_tetik_kurulmaz(self):
        p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot') as tek_atis:
            Pencere._konusma_bitince_duplex_devam(p)
        tek_atis.assert_not_called()

    def test_tts_kapaliyken_de_dongu_devam_eder(self):
        speech.set_duplex_voice_active(True)
        p = _sahte_pencere({'tts_enabled': False})
        p._konusma_bitince_duplex_devam = MagicMock()
        Pencere._speak(p, 'Hava 20 derece.')
        p._konusma_bitince_duplex_devam.assert_called_once()


class DuplexKomutSonucuTest(unittest.TestCase):
    """Arayüz, DuplexOturumu'nun kararlarını uyguluyor mu? (Kuralların kendisi
    tests/test_duplex.py'de.)"""

    def setUp(self):
        from features.duplex import OTURUM
        self.oturum = OTURUM
        self.oturum.kapat()

    def tearDown(self):
        self.oturum.kapat()

    def _dinlemeye_dondu_mu(self, tek_atis):
        return any(c.args[1] == self.p._on_wake_detected for c in tek_atis.call_args_list)

    def test_komut_normal_akisa_gider(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        Pencere._on_wake_command(self.p, 'hava durumu nedir')
        self.assertTrue(self.oturum.aktif_mi())
        self.p.on_user_send_message.assert_called_once_with('hava durumu nedir')

    def test_muzigi_durdur_komuttur_sohbeti_kapatmaz(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        Pencere._on_wake_command(self.p, 'müziği durdur')
        self.assertTrue(self.oturum.aktif_mi())
        self.p.on_user_send_message.assert_called_once_with('müziği durdur')

    def test_dur_sohbeti_kapatir(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        Pencere._on_wake_command(self.p, 'dur')
        self.assertFalse(self.oturum.aktif_mi())
        self.p.on_user_send_message.assert_not_called()
        self.assertIn('kapandı', self.p._post_assistant.call_args[0][0])

    def test_ilk_sessizlik_tekrar_dinler(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot') as tek_atis:
            Pencere._on_wake_command(self.p, '')
        self.assertTrue(self.oturum.aktif_mi())
        self.assertTrue(self._dinlemeye_dondu_mu(tek_atis))
        self.p.on_user_send_message.assert_not_called()

    def test_ikinci_sessizlik_kapatir(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot'):
            Pencere._on_wake_command(self.p, '')
            Pencere._on_wake_command(self.p, '')
        self.assertFalse(self.oturum.aktif_mi())
        self.assertIn('Ses gelmedi', self.p._post_assistant.call_args[0][0])

    def test_duplex_kapaliyken_bos_sonuc_sessiz(self):
        self.p = _sahte_pencere()
        Pencere._on_wake_command(self.p, '')
        self.p._post_assistant.assert_not_called()

    def test_ilk_dinleme_hatasi_oturumu_kapatmaz(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot') as tek_atis:
            Pencere._on_wake_command_error(self.p, 'ağ hatası')
        self.assertTrue(self.oturum.aktif_mi())
        self.assertTrue(self._dinlemeye_dondu_mu(tek_atis))

    def test_ikinci_hata_kapatir(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot'):
            Pencere._on_wake_command_error(self.p, 'ağ hatası')
            Pencere._on_wake_command_error(self.p, 'ağ hatası')
        self.assertFalse(self.oturum.aktif_mi())

    def test_duplex_kapaliyken_hata_kullaniciya_soylenir(self):
        self.p = _sahte_pencere()
        Pencere._on_wake_command_error(self.p, 'Mikrofon hatası: aygıt yok')
        self.assertIn('Mikrofon hatası', self.p._post_assistant.call_args[0][0])

    def test_cevap_bitince_dinlemeye_doner(self):
        self.oturum.baslat()
        self.p = _sahte_pencere()
        self.oturum.kullanici_konustu('saat kaç')
        with patch.object(tw.QTimer, 'singleShot') as tek_atis:
            Pencere._konusma_bitince_duplex_devam(self.p)
        self.assertTrue(self._dinlemeye_dondu_mu(tek_atis))

    def test_bildirim_mesajlari_SESLENDIRILMEZ(self):
        """Seslendirilirse konuşma bitişi yeniden dinlemeyi tetikler → döngü kilitlenir."""
        self.oturum.baslat()
        self.p = _sahte_pencere()
        with patch.object(tw.QTimer, 'singleShot'):
            Pencere._on_wake_command(self.p, '')
        self.assertFalse(self.p._post_assistant.call_args.kwargs.get('speak', True))


class IkinciDinleyiciTest(unittest.TestCase):

    def test_dinleme_surerken_ikinci_dinleyici_acilmaz(self):
        p = _sahte_pencere()
        p.listen_worker = SimpleNamespace(isRunning=lambda: True)
        with patch.object(tw, 'ListenWorkerThread') as dinleyici, \
                patch.object(tw.QApplication, 'beep'):
            Pencere._on_wake_detected(p)
        dinleyici.assert_not_called()


class MikrofonUyarisiTest(unittest.TestCase):

    def test_ayni_uyari_bir_kez_gosterilir(self):
        p = _sahte_pencere({'mic_device_index': 1})
        uyari = '⚠️ Ayarlı ses aygıtı (Stereo Karışımı) bir mikrofon değil'
        with patch('features.mic_devices.mikrofon_sec', return_value=(None, uyari)):
            self.assertEqual(Pencere._mikrofon_aygiti(p), -1)
            self.assertEqual(Pencere._mikrofon_aygiti(p), -1)
        self.assertEqual(p._post_assistant.call_count, 1)

    def test_gecerli_mikrofon_numarasi_doner(self):
        p = _sahte_pencere()
        with patch('features.mic_devices.mikrofon_sec', return_value=(2, None)):
            self.assertEqual(Pencere._mikrofon_aygiti(p), 2)
        p._post_assistant.assert_not_called()


if __name__ == '__main__':
    unittest.main()
