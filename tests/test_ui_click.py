# -*- coding: utf-8 -*-
"""
"Ekranda X'e tıkla" testleri — features/actions/ui_click.py

Bu komut kullanıcı adına DÜĞMEYE BASAR. En tehlikeli hata "yanlış tıklamak"
değil, **istenmediği hâlde tıklamaktır**: sıradan bir cümleyi tıklama komutu
sanmak, Ultron'un kendi kendine ekranda bir yere basması demektir.

KİLİTLENEN DAVRANIŞLAR:
  • `test_klavye_komutlarini_calmaz` — "enter bas" bir TUŞ komutudur. Buraya
    düşerse Ultron ekranda "enter" yazan bir şey arayıp ona tıklar.
  • `test_sirdan_cumleye_el_koymaz` — "spotify aç", "bana bir şarkı çal" gibi
    cümleler tıklama değildir.
  • `test_hedef_anlasilmazsa_hicbir_sey_yapmaz` — belirsizlikte varsayılan
    davranış HİÇBİR ŞEY YAPMAMAKTIR.
  • `test_zincir_uia_once_ocr_sonra` — fare son çaredir; UIA çalışıyorsa
    ekrana tıklanmamalı.
  • `test_zincir_basarisizsa_tiklamadigini_soyler` — sessizce başarısız olup
    "tıkladım" demek yalan söylemektir.

İZOLASYON: zırh kurulur; UIA ve OCR katmanları taklit edilir, gerçek fare/UIA
çağrısı yapılmaz.
"""

import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.interaction.base import InteractionResult
from features.actions import ui_click


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class HedefAyristirmaTest(unittest.TestCase):

    def test_tiklama_cumleleri_cozulur(self):
        ornekler = {
            "ekranda Kaydet'e tıkla": "Kaydet",
            "ekranda Tamam butonuna bas": "Tamam",
            'ekranda "İzin Ver"e tıkla': "İzin Ver",
            "Gönder butonuna tıkla": "Gönder",
            "ekranda Devam Et'e basar mısın": "Devam Et",
        }
        for cumle, beklenen in ornekler.items():
            with self.subTest(cumle=cumle):
                self.assertEqual(ui_click.tiklama_hedefi_coz(cumle), beklenen)

    def test_klavye_komutlarini_calmaz(self):
        for cumle in ("enter bas", "esc bas", "ctrl+s bas", "alt+f4 bas",
                      "tab bas", "f5 bas"):
            with self.subTest(cumle=cumle):
                self.assertIsNone(ui_click.tiklama_hedefi_coz(cumle),
                                  "TUŞ komutunu tıklama sandı")

    def test_sirdan_cumleye_el_koymaz(self):
        for cumle in ("spotify aç", "bana bir şarkı çal", "ekranda ne yazıyor",
                      "yarın 10'da hatırlat", "hava nasıl", ""):
            with self.subTest(cumle=cumle):
                self.assertIsNone(ui_click.tiklama_hedefi_coz(cumle))

    def test_hedef_anlasilmazsa_hicbir_sey_yapmaz(self):
        islendi, mesaj = ui_click.ekranda_tikla(None)
        self.assertFalse(islendi)
        self.assertIsNone(mesaj)


class ZincirTest(unittest.TestCase):
    """Fare son çaredir: UIA çalışıyorsa OCR'a HİÇ gidilmemeli."""

    def setUp(self):
        # Capability cache kullanıcının gerçek dosyasına yazmasın
        import tempfile, os
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        ui_click._engine._cache_path = os.path.join(self._tmp.name, "cache.json")
        ui_click._engine._cache = {}

    def test_zincir_uia_once_ocr_sonra(self):
        with mock.patch.object(ui_click._UiaClickStrategy, 'available', return_value=True), \
             mock.patch.object(ui_click._UiaClickStrategy, 'execute',
                               return_value=InteractionResult(True, "uia", "ok")) as uia, \
             mock.patch.object(ui_click.level3_ocr.OcrClickStrategy, 'execute') as ocr:
            islendi, mesaj = ui_click.ekranda_tikla("Kaydet")

        self.assertTrue(islendi)
        self.assertIn("Kaydet", mesaj)
        self.assertIn("Level 2", mesaj)
        uia.assert_called_once()
        ocr.assert_not_called()          # UIA yetti → fareye hiç dokunulmadı

    def test_uia_basarisizsa_ocr_devreye_girer(self):
        with mock.patch.object(ui_click._UiaClickStrategy, 'available', return_value=True), \
             mock.patch.object(ui_click._UiaClickStrategy, 'execute',
                               return_value=InteractionResult(False, "uia", "ağaçta yok")), \
             mock.patch.object(ui_click.level3_ocr.OcrClickStrategy, 'available',
                               return_value=True), \
             mock.patch.object(ui_click.level3_ocr.OcrClickStrategy, 'execute',
                               return_value=InteractionResult(True, "vision", "tıklandı")) as ocr:
            islendi, mesaj = ui_click.ekranda_tikla("Kaydet")

        self.assertTrue(islendi)
        self.assertIn("Level 3", mesaj)
        ocr.assert_called_once()

    def test_zincir_basarisizsa_tiklamadigini_soyler(self):
        with mock.patch.object(ui_click._UiaClickStrategy, 'available', return_value=True), \
             mock.patch.object(ui_click._UiaClickStrategy, 'execute',
                               return_value=InteractionResult(False, "uia", "ağaçta yok")), \
             mock.patch.object(ui_click.level3_ocr.OcrClickStrategy, 'available',
                               return_value=True), \
             mock.patch.object(ui_click.level3_ocr.OcrClickStrategy, 'execute',
                               return_value=InteractionResult(False, "vision", "3 yerde geçiyor")):
            islendi, mesaj = ui_click.ekranda_tikla("Kaydet")

        self.assertTrue(islendi)
        self.assertIn("tıklanamadı", mesaj)
        self.assertIn("hiçbir yere basılmadı", mesaj)
        self.assertIn("3 yerde geçiyor", mesaj)


class KayitTest(unittest.TestCase):

    def test_arac_onay_riskiyle_kayitli(self):
        import core.builtin_tools  # noqa: F401
        from core.tools import DEFTER, RISK_ONAY

        arac = DEFTER.intent_ile("SCREEN_CLICK")
        self.assertIsNotNone(arac)
        self.assertEqual(arac.ad, 'ekranda_tikla')
        self.assertEqual(arac.risk, RISK_ONAY,
                         "Tıklama aracı onaysız — planner kendi başına düğmeye basabilir")


if __name__ == '__main__':
    unittest.main()
