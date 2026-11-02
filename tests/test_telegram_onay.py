# -*- coding: utf-8 -*-
"""
TELEGRAM YAZILI ONAY — "evet" yazınca bekleyen komut çalışmalı.

NEDEN VAR: 23 Eyl canlı kaydı — telefondan "Bilgisayarı kapat" → onay kartı →
kullanıcı "Evet bilgisayarı kapat" yazdı → bekleyen onay İPTAL edildi, yazı yeni
komut sayıldı, yeniden onay kartı geldi. Yazılı onay hiç çalışmıyordu; yalnızca
inline buton çalışıyordu.

Kural sıkıdır (güvenlik kapısı): onay ya TEK BAŞINA onay kelimesi ya da onay
kelimesi + bekleyen komutun AYNISI. Bu dosya hem kuralı hem de bağlantıyı
(mesaj gerçekten onaylı yürütücüye ulaşıyor mu) sınar.
"""
import sys
import time
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
from features.telegram_bridge import yazili_onay_coz  # noqa: E402

CHAT = 12345


class YaziliOnayKuraliTest(unittest.TestCase):

    def test_tek_basina_evet_onaydir(self):
        for m in ("evet", "Evet", "EVET!", "onayla", "onaylıyorum"):
            self.assertEqual(yazili_onay_coz(m, "Bilgisayarı kapat"), 'onay', m)

    def test_evet_arti_ayni_komut_onaydir(self):
        self.assertEqual(yazili_onay_coz("Evet bilgisayarı kapat", "Bilgisayarı kapat"), 'onay')
        self.assertEqual(yazili_onay_coz("evet BİLGİSAYARI KAPAT.", "Bilgisayarı kapat"), 'onay')

    def test_evet_arti_BASKA_sey_onay_degildir(self):
        """Ek bir istek taşıyan cevap onay sayılırsa kullanıcının yeni komutu yutulur
        ya da yanlış şey onaylanır."""
        self.assertIsNone(yazili_onay_coz("evet ama önce müziği aç", "Bilgisayarı kapat"))
        self.assertIsNone(yazili_onay_coz("evet anneme gönder", "babama gönder"))

    def test_ret(self):
        for m in ("hayır", "iptal", "İptal et", "vazgeç"):
            self.assertEqual(yazili_onay_coz(m, "Bilgisayarı kapat"), 'ret', m)

    def test_ret_kelimesiyle_baslayan_yeni_komut_ret_degildir(self):
        self.assertIsNone(yazili_onay_coz("iptal edilen uçuşları ara", "Bilgisayarı kapat"))

    def test_alakasiz_mesaj_None(self):
        self.assertIsNone(yazili_onay_coz("hava nasıl", "Bilgisayarı kapat"))
        self.assertIsNone(yazili_onay_coz("", "Bilgisayarı kapat"))


class _SahteTg:
    yazili_onay_coz = staticmethod(yazili_onay_coz)

    def __init__(self):
        self.mesajlar = []

    def send_message(self, token, chat_id, text, reply_markup=None):
        self.mesajlar.append(text)
        return True

    def menu_butonu_coz(self, text):
        return text

    def onay_butonlari(self):
        return telegram_bridge.onay_butonlari()


class _SahteController:
    def __init__(self):
        self.config = {'telegram_chat_id': str(CHAT)}


class YaziliOnayBaglantisiTest(unittest.TestCase):

    def _isci(self, komut="Bilgisayarı kapat", sure=60):
        w = TelegramWorkerThread(_SahteController())
        w.pending[CHAT] = (komut, time.time() + sure)
        return w

    def test_evet_bekleyen_komutu_yurutur(self):
        w, tg = self._isci(), _SahteTg()
        with patch('features.confirmed_executor.onayli_komut_yurut',
                   return_value=(True, 'kapatılıyor')) as yurut, \
                patch.object(TelegramWorkerThread, '_process_command') as isle:
            w._handle_text_command(tg, 'TOKEN', CHAT, "Evet bilgisayarı kapat")
        yurut.assert_called_once_with("Bilgisayarı kapat", kanal=str(CHAT))
        isle.assert_not_called()  # yeniden onay kartı ÜRETİLMEMELİ
        self.assertNotIn(CHAT, w.pending)
        self.assertTrue(any('ONAYLANDI' in m for m in tg.mesajlar))

    def test_iptal_yurutmez(self):
        w, tg = self._isci(), _SahteTg()
        with patch('features.confirmed_executor.onayli_komut_yurut') as yurut:
            w._handle_text_command(tg, 'TOKEN', CHAT, "iptal")
        yurut.assert_not_called()
        self.assertNotIn(CHAT, w.pending)

    def test_suresi_dolmus_onay_yurutulmez(self):
        w, tg = self._isci(sure=-1), _SahteTg()
        with patch('features.confirmed_executor.onayli_komut_yurut') as yurut:
            w._handle_text_command(tg, 'TOKEN', CHAT, "evet")
        yurut.assert_not_called()
        self.assertTrue(any('süresi dolmuş' in m for m in tg.mesajlar))

    def test_baska_komut_onayi_iptal_eder_ve_yeni_komutu_isler(self):
        w, tg = self._isci(), _SahteTg()
        with patch('features.confirmed_executor.onayli_komut_yurut') as yurut, \
                patch.object(TelegramWorkerThread, '_process_command',
                             return_value='güneşli') as isle:
            w._handle_text_command(tg, 'TOKEN', CHAT, "hava nasıl")
        yurut.assert_not_called()
        isle.assert_called_once()
        self.assertNotIn(CHAT, w.pending)


if __name__ == '__main__':
    unittest.main()
