# -*- coding: utf-8 -*-
"""
TELEGRAM SESLİ YANIT — sesli mesaja sesli not ile cevap.

NEDEN BU KADAR TEST: 1 Eyl'de `telegram_bridge.send_voice` ve
`speech.metni_sese_cevir_dosya` yazılmış, testleri yeşildi — ama HİÇBİR YERDEN
çağrılmıyorlardı. 15 Eyl'de ölü kod diye silindiler. Bu dosya fonksiyonu değil
BAĞLANTIYI sınar: Telegram'dan gelen sesli mesaj gerçekten `send_voice`'a
ulaşıyor mu? ("fonksiyon çalışıyor" ile "komut oraya gidiyor" ayrı iddialardır.)

Ağa çıkmaz: tg modülü, STT ve edge-tts taklit edilir.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt5 import QtWebEngineWidgets  # noqa: F401  — QApplication'dan ÖNCE (bkz. conftest.py)
from PyQt5.QtWidgets import QApplication

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


app = QApplication.instance() or QApplication(sys.argv)

from ui.tau_window import TelegramWorkerThread  # noqa: E402
from features import telegram_bridge  # noqa: E402

CHAT = 12345


class _SahteTg:
    """telegram_bridge taklidi — her çağrıyı kaydeder."""

    def __init__(self, send_voice_sonuc=True):
        self.mesajlar = []
        self.sesler = []
        self._send_voice_sonuc = send_voice_sonuc

    def get_file_path(self, token, file_id):
        return 'voice/file_1.oga'

    def download_file(self, token, fp, dest):
        with open(dest, 'wb') as f:
            f.write(b'OggS')
        return True

    def send_message(self, token, chat_id, text, reply_markup=None):
        self.mesajlar.append(text)
        return True

    def send_voice(self, token, chat_id, yol, caption=''):
        self.sesler.append((yol, os.path.exists(yol)))
        return self._send_voice_sonuc

    def menu_butonu_coz(self, text):
        return text


class _SahteController:
    def __init__(self, config=None):
        self.config = {'telegram_chat_id': str(CHAT)}
        self.config.update(config or {})


def _gecici_ses_dosyasi():
    fd, yol = tempfile.mkstemp(suffix='.ogg', prefix='ultron_test_sesli_')
    os.write(fd, b'OggS')
    os.close(fd)
    return yol


class SesliMesajaSesliYanitTest(unittest.TestCase):

    def _calistir(self, config=None, stt=('hava durumu nasıl', 'google', None),
                  cevap='İstanbul 21 derece, parçalı bulutlu.', tg=None, ses_yolu='uret'):
        tg = tg or _SahteTg()
        w = TelegramWorkerThread(_SahteController(config))
        self.ses_yolu = _gecici_ses_dosyasi() if ses_yolu == 'uret' else ses_yolu
        with patch('features.speech.ogg_sesi_yaziya_cevir_ayrintili', return_value=stt), \
                patch.object(TelegramWorkerThread, '_process_command', return_value=cevap), \
                patch('features.speech.sesli_yanit_dosyasi_uret',
                      return_value=self.ses_yolu) as uret:
            w._handle_voice_message(tg, 'TOKEN', CHAT, {'file_id': 'f1', 'file_unique_id': 'u1'})
        self.uret = uret
        return tg

    def tearDown(self):
        yol = getattr(self, 'ses_yolu', None)
        if yol and os.path.exists(yol):
            os.remove(yol)

    def test_sesli_mesaj_send_voice_a_ULASIR(self):
        tg = self._calistir()
        self.assertEqual(len(tg.sesler), 1, 'sesli yanıt hiç gönderilmedi')
        yol, o_an_vardi = tg.sesler[0]
        self.assertTrue(o_an_vardi, 'gönderim anında dosya diskte yoktu')
        self.uret.assert_called_once_with('İstanbul 21 derece, parçalı bulutlu.')

    def test_yazili_cevap_da_gider(self):
        tg = self._calistir()
        self.assertIn('İstanbul 21 derece, parçalı bulutlu.', tg.mesajlar)
        self.assertTrue(any('Algılanan' in m for m in tg.mesajlar))

    def test_gonderimden_sonra_gecici_dosya_silinir(self):
        self._calistir()
        self.assertFalse(os.path.exists(self.ses_yolu))

    def test_ayar_kapaliysa_sesli_yanit_yok(self):
        tg = self._calistir(config={'telegram_voice_reply': False})
        self.assertEqual(tg.sesler, [])
        self.uret.assert_not_called()

    def test_onay_bekleyen_komuta_sesli_yanit_yok(self):
        """_process_command None dönerse (onay kartı) seslendirilecek cevap yoktur."""
        tg = self._calistir(cevap=None)
        self.assertEqual(tg.sesler, [])

    def test_cevrimdisi_tanima_kullaniciya_soylenir(self):
        tg = self._calistir(stt=('hava durumu nasıl', 'vosk', None))
        self.assertTrue(any('çevrimdışı' in m for m in tg.mesajlar))

    def test_stt_hatasi_komut_calistirmaz(self):
        tg = _SahteTg()
        w = TelegramWorkerThread(_SahteController())
        with patch('features.speech.ogg_sesi_yaziya_cevir_ayrintili',
                   return_value=(None, None, 'Google konuşma tanımaya ulaşılamadı')), \
                patch.object(TelegramWorkerThread, '_process_command') as isle:
            w._handle_voice_message(tg, 'TOKEN', CHAT, {'file_id': 'f1'})
        isle.assert_not_called()
        self.assertTrue(any('çevrilemedi' in m for m in tg.mesajlar))

    def test_ses_uretilemezse_sessiz_kalmaz(self):
        tg = self._calistir(ses_yolu=None)
        self.assertEqual(tg.sesler, [])
        self.assertTrue(any('Sesli yanıt üretilemedi' in m for m in tg.mesajlar))

    def test_gonderilemezse_bildirir_ve_dosyayi_siler(self):
        tg = self._calistir(tg=_SahteTg(send_voice_sonuc=False))
        self.assertTrue(any('gönderilemedi' in m for m in tg.mesajlar))
        self.assertFalse(os.path.exists(self.ses_yolu))

    def test_yazili_komuta_sesli_yanit_gitmez(self):
        """Yalnız SESLİ mesajın cevabı seslendirilir."""
        tg = _SahteTg()
        w = TelegramWorkerThread(_SahteController())
        with patch.object(TelegramWorkerThread, '_process_command', return_value='Tamam.'), \
                patch.object(TelegramWorkerThread, '_sesli_yanit_gonder') as sesli, \
                patch('features.custom_shortcuts.komut_bul', return_value=None):
            donen = w._handle_text_command(tg, 'TOKEN', CHAT, 'saat kaç')
        self.assertEqual(donen, 'Tamam.')
        sesli.assert_not_called()


class SendVoiceTest(unittest.TestCase):

    def test_sendvoice_multipart_gonderir(self):
        yol = _gecici_ses_dosyasi()
        self.addCleanup(os.remove, yol)

        class _Cevap:
            @staticmethod
            def json():
                return {'ok': True}

        with patch.object(telegram_bridge.requests, 'post', return_value=_Cevap()) as post:
            self.assertTrue(telegram_bridge.send_voice('TOKEN', CHAT, yol))
        url = post.call_args[0][0]
        self.assertTrue(url.endswith('/sendVoice'))
        self.assertIn('voice', post.call_args[1]['files'])

    def test_olmayan_dosya(self):
        self.assertFalse(telegram_bridge.send_voice('TOKEN', CHAT, 'yok/boyle/bir.ogg'))


if __name__ == '__main__':
    unittest.main()
