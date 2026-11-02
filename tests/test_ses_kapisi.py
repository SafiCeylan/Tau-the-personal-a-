# -*- coding: utf-8 -*-
"""
SES KAPISI — mikrofondan duyulan ortam konuşması eylem tetiklememeli.

NEDEN VAR (15 Eki 2026): 24 Eyl – 3 Eki canlı kaydında TV diyalogları komut
sanıldı; planner 18 plan üretti, SCREEN_CLICK / FINANCE_TRACK / SET_VOLUME
tetiklendi. Aşağıdaki cümleler O KAYITTAN alınmıştır (gerçek STT çıktısı).

Üç iddia ayrı ayrı sınanır:
  1. kural (ortam_konusmasi_mi) — gerçek ortam cümlelerini yakalar, gerçek
     komutları yakalamaz
  2. motor — sesle gelen ortam cümlesi araç/plan çalıştırmaz; AYNI cümle
     yazıyla gelirse davranış değişmez (kapı yalnız sese uygulanır)
  3. arayüz — canlı sohbet kapalıyken ortam cümlesi motora hiç gitmez
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

from features import ses_kapisi  # noqa: E402
from features.duplex import OTURUM  # noqa: E402
from ui import tau_window as tw  # noqa: E402

# ogrenme.db'den — her biri canlıda bir niyeti tetikledi
ORTAM_CUMLELERI = [
    # → SCREEN_CLICK
    "bunu yapıyorsa büyük fabrikalar bizim gözümüzün yaşına bakmaz şimdi bu elemanın "
    "ne yaptığını anlamamız lazım hemen gidip bakalım",
    # → SET_VOLUME
    "öğrencileri her gün bu sessiz çocuğu köşeye sıkıştırıyor harçlığını alıyor sonra "
    "da hiçbir şey olmamış gibi sınıfa giriyorlar",
    # → FINANCE_TRACK + plan
    "yektayı direkt içeri alırlar zaten bu yaştan sonra da oradan çıkması mümkün değil "
    "bir de üstüne 5000 lira borcu var",
    # → CREATE_REMINDER + plan
    "unutma bir 3 kişi şüphesiz eldivenini ortaya atmadık izmarit ile bir ayak iziyle "
    "olay yerinde ne bulduysak onu söyleyeceğiz",
]

GERCEK_KOMUTLAR = [
    "chrome aç", "sesi %50 yap", "türkü çal", "staj raporunu bul ve anneme whatsapptan gönder",
    "zen aç sonra youtube yaz enter bas sonra ekran oku ve 1'e tıkla",
    "ben 22 yaşındayım ve mersin üniversitesi bilişim sistemleri ve teknolojileri bölümünde okuyorum",
]


class KuralTest(unittest.TestCase):

    def test_gercek_ortam_cumleleri_yakalanir(self):
        for c in ORTAM_CUMLELERI:
            self.assertTrue(ses_kapisi.ortam_konusmasi_mi(c), c)

    def test_olculen_gercek_komutlar_yakalanmaz(self):
        for c in GERCEK_KOMUTLAR:
            self.assertFalse(ses_kapisi.ortam_konusmasi_mi(c), c)

    def test_ultron_diye_baslayan_uzun_cumle_komuttur(self):
        c = "ultron " + ORTAM_CUMLELERI[0]
        self.assertFalse(ses_kapisi.ortam_konusmasi_mi(c))
        self.assertFalse(ses_kapisi.ortam_konusmasi_mi("hey ultra " + ORTAM_CUMLELERI[1]))

    def test_bos_metin(self):
        self.assertFalse(ses_kapisi.ortam_konusmasi_mi(""))
        self.assertFalse(ses_kapisi.ortam_konusmasi_mi(None))


def _motor():
    import sqlite3
    from core.engine import UltronCoreEngine
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    with open('database/schema.sql', encoding='utf-8') as f:
        cur.executescript(f.read())
    return UltronCoreEngine(cursor=cur, conn=conn,
                            config={'ai_provider': 'none', 'llm_intent_enabled': False,
                                    'planner_enabled': True})


class MotorTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.motor = _motor()

    def test_sesli_ortam_cumlesi_arac_ve_plan_calistirmaz(self):
        for c in ORTAM_CUMLELERI:
            with patch.object(self.motor, '_plani_kur_ve_calistir') as plan, \
                    patch.object(self.motor.l12_exec, 'process') as yurut:
                ctx = self.motor.process(c, input_type="voice")
            plan.assert_not_called()
            yurut.assert_not_called()
            self.assertEqual(ctx.intent, "GENERAL_CONVERSATION", c)
            self.assertIsNone(ctx.son_arac, c)

    def test_ayni_cumle_yaziyla_gelirse_kapi_uygulanmaz(self):
        """Kapı yalnız mikrofona uygulanır — klavyeden yazılan cümle kullanıcınındır."""
        c = ORTAM_CUMLELERI[0]
        with patch.object(self.motor.l12_exec, 'process',
                          side_effect=lambda ctx, **kw: ctx) as yurut:
            self.motor.process(c, input_type="text")
        yurut.assert_called_once()

    def test_kisa_sesli_komut_normal_calisir(self):
        with patch.object(self.motor.l12_exec, 'process',
                          side_effect=lambda ctx, **kw: ctx) as yurut:
            ctx = self.motor.process("sesi %50 yap", input_type="voice")
        yurut.assert_called_once()
        self.assertEqual(ctx.intent, "SET_VOLUME")


class ArayuzTest(unittest.TestCase):

    def _pencere(self):
        return SimpleNamespace(
            _post_assistant=MagicMock(),
            chat_view=MagicMock(), ultron_focus_view=MagicMock(),
            pending_confirmation_cmd=None,
        )

    def tearDown(self):
        OTURUM.kapat()

    def test_canli_sohbet_kapaliyken_ortam_cumlesi_motora_gitmez(self):
        p = self._pencere()
        with patch.object(tw, 'EngineWorkerThread') as isci:
            tw.TauMainWindow.on_user_send_message(p, ORTAM_CUMLELERI[0], input_type="voice")
        isci.assert_not_called()
        p._post_assistant.assert_called_once()
        self.assertIn('işlemedim', p._post_assistant.call_args[0][0])
        p.chat_view.add_message.assert_not_called()

    def test_canli_sohbette_ortam_cumlesi_motora_SES_olarak_gider(self):
        OTURUM.baslat()
        p = MagicMock()
        p.pending_confirmation_cmd = None
        p.recent_chat_history = []
        with patch.object(tw, 'EngineWorkerThread') as isci:
            tw.TauMainWindow.on_user_send_message(p, ORTAM_CUMLELERI[0], input_type="voice")
        isci.assert_called_once()
        self.assertEqual(isci.call_args.kwargs.get('input_type'), "voice")


if __name__ == '__main__':
    unittest.main()
