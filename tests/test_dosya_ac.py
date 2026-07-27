# -*- coding: utf-8 -*-
"""
Dosya açma (`islem='ac'`) testleri.

İKİ BÜYÜK RİSK:

1. REGRESYON — "aç" fiili SYSTEM_CONTROL ile çakışır. "chrome aç" komutu
   indekste chrome.exe bulup dosya açmaya kalkarsa uygulama başlatma bozulur.
   Bu yüzden 'ac' işlemi YALNIZCA güçlü dosya sinyalinde üretilir.

2. PROGRAM ÇALIŞTIRMA — `os.startfile` bir .exe'yi açmaz, ÇALIŞTIRIR. İndekste
   134 bin dosya var; yanlış eşleşme istenmeyen program başlatmak demektir.
   Çalıştırılabilir dosyalar onay kartından geçmeden açılmamalı.
"""

import os
import tempfile
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir, CAGRI_KAYDI

from features import file_send
from features.file_send import (
    calistirilabilir_mi, dosya_komutu_ayristir, _dosyayi_ac,
)


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class UzantiTest(unittest.TestCase):

    def test_calistirilabilir_uzantilar_taninir(self):
        for yol in ("C:/a/kurulum.exe", "C:/a/script.bat", "C:/a/x.ps1",
                    "C:/a/y.msi", "C:/a/z.cmd", "C:/a/k.vbs", "C:/a/s.lnk"):
            self.assertTrue(calistirilabilir_mi(yol), yol)

    def test_belgeler_calistirilabilir_sayilmaz(self):
        for yol in ("C:/a/rapor.pdf", "C:/a/tez.docx", "C:/a/foto.jpg",
                    "C:/a/not.txt", "C:/a/kod.py", "C:/a/ULTRON.spec"):
            self.assertFalse(calistirilabilir_mi(yol), yol)

    def test_buyuk_harf_uzanti_da_yakalanir(self):
        self.assertTrue(calistirilabilir_mi("C:/a/SETUP.EXE"))

    def test_bos_deger_cokmez(self):
        self.assertFalse(calistirilabilir_mi(None))
        self.assertFalse(calistirilabilir_mi(""))


class AyristirmaTest(unittest.TestCase):
    """'ac' işlemi ne zaman üretilir?"""

    def test_guclu_sinyalli_acma_komutu_taninir(self):
        plan = dosya_komutu_ayristir("ULTRON.spec dosyasını aç")
        self.assertIsNotNone(plan)
        self.assertEqual(plan['islem'], 'ac')

    def test_uygulama_acma_dosya_komutu_sayilmaz(self):
        """EN ÖNEMLİ REGRESYON TESTİ: 'chrome aç' uygulama açmalı."""
        for komut in ("chrome aç", "spotify aç", "hesap makinesini aç",
                      "youtube aç", "whatsapp aç"):
            plan = dosya_komutu_ayristir(komut)
            self.assertNotEqual(
                (plan or {}).get('islem'), 'ac',
                f"'{komut}' dosya açmaya kaydı — uygulama başlatma bozulur")

    def test_tur_belirtilince_acma_taninir(self):
        plan = dosya_komutu_ayristir("son pdf'i aç")
        self.assertEqual((plan or {}).get('islem'), 'ac')

    def test_ac_kelime_siniri_korunur(self):
        """'ac' alt dizisi 'ihtiyac', 'acele' içinde geçer — tetiklememeli."""
        plan = dosya_komutu_ayristir("ihtiyac listesi dosyasını bul")
        self.assertNotEqual((plan or {}).get('islem'), 'ac')

    def test_gonderim_acmadan_onceliklidir(self):
        """'dosyayı aç ve anneme gönder' → gönderim kazanır."""
        plan = dosya_komutu_ayristir("rapor dosyasını anneme mail at")
        self.assertEqual((plan or {}).get('islem'), 'gonder')


class AcmaDavranisTest(unittest.TestCase):

    def setUp(self):
        self.dizin = tempfile.mkdtemp(prefix='ultron_ac_test_')
        CAGRI_KAYDI.clear()

    def _dosya(self, ad):
        yol = os.path.join(self.dizin, ad)
        open(yol, 'w').close()
        return yol

    def _plan(self, sorgu='x', tur=None):
        return {'islem': 'ac', 'sorgu': sorgu, 'secim': None, 'hedef': None,
                'alici': None, 'tur': tur, 'zayif': False}

    def test_belge_onaysiz_acilir(self):
        yol = self._dosya('rapor.pdf')
        with mock.patch.object(file_send, 'hedef_dosyayi_coz', return_value=yol):
            islendi, cevap = _dosyayi_ac(self._plan(), 'desktop')
        self.assertTrue(islendi)
        self.assertIn('Açılıyor', cevap)
        self.assertTrue(any('startfile' in e for e, _ in CAGRI_KAYDI))

    def test_program_onaysiz_ACILMAZ(self):
        """En kritik test: onaysız program çalıştırılmamalı."""
        yol = self._dosya('kurulum.exe')
        with mock.patch.object(file_send, 'hedef_dosyayi_coz', return_value=yol):
            islendi, cevap = _dosyayi_ac(self._plan(), 'desktop')
        self.assertTrue(islendi)
        self.assertIn('program', cevap.lower())
        self.assertFalse(any('startfile' in e for e, _ in CAGRI_KAYDI),
                         "onaysız program ÇALIŞTIRILDI")

    def test_program_onaylandiysa_acilir(self):
        yol = self._dosya('kurulum.exe')
        with mock.patch.object(file_send, 'hedef_dosyayi_coz', return_value=yol):
            islendi, cevap = _dosyayi_ac(self._plan(), 'desktop', onaylandi=True)
        self.assertIn('Açılıyor', cevap)
        self.assertTrue(any('startfile' in e for e, _ in CAGRI_KAYDI))

    def test_silinmis_dosya_uyarir(self):
        """İndeks bayat olabilir — dosya artık yerinde olmayabilir."""
        yol = os.path.join(self.dizin, 'yok.pdf')
        with mock.patch.object(file_send, 'hedef_dosyayi_coz', return_value=yol):
            islendi, cevap = _dosyayi_ac(self._plan(), 'desktop')
        self.assertIn('yerinde değil', cevap)
        self.assertFalse(any('startfile' in e for e, _ in CAGRI_KAYDI))

    def test_birden_fazla_esleme_sorulur(self):
        sonuclar = [{'ad': 'a.pdf', 'yol': 'C:/a.pdf'}, {'ad': 'b.pdf', 'yol': 'C:/b.pdf'}]
        with mock.patch.object(file_send, 'hedef_dosyayi_coz', return_value=None), \
             mock.patch.object(file_send.file_index, 'ara', return_value=sonuclar), \
             mock.patch.object(file_send.file_index, 'son_sonuclari_kaydet'), \
             mock.patch.object(file_send.file_index, 'sonuclari_bicimle',
                               return_value="liste"):
            islendi, cevap = _dosyayi_ac(self._plan(), 'desktop')
        self.assertIn('Hangisini', cevap)
        self.assertFalse(any('startfile' in e for e, _ in CAGRI_KAYDI))

    def test_zayif_sinyalde_eslesme_yoksa_devredilir(self):
        """Dosya komutu değilmiş — çağıran katman (LLM/WhatsApp) devam etsin."""
        plan = self._plan()
        plan['zayif'] = True
        with mock.patch.object(file_send, 'hedef_dosyayi_coz', return_value=None), \
             mock.patch.object(file_send.file_index, 'ara', return_value=[]):
            islendi, cevap = _dosyayi_ac(plan, 'desktop')
        self.assertFalse(islendi)


class GuvenlikKatmaniTest(unittest.TestCase):
    """Çalıştırılabilir dosya onay kartı üretmeli."""

    def setUp(self):
        from core.layers.pipeline_layers import SecurityAnalyzerLayer
        from core.context import UltronContext
        self.katman = SecurityAnalyzerLayer()
        self.UltronContext = UltronContext

    def _ctx(self, plan):
        ctx = self.UltronContext(raw_input="dosyayı aç")
        ctx.normalized_input = "dosyayı aç"
        ctx.intent = "FILE_TRANSFER"
        ctx.entities = {'dosya_plani': plan}
        return ctx

    def _plan(self):
        return {'islem': 'ac', 'sorgu': 'x', 'secim': None, 'hedef': None,
                'alici': None, 'tur': None, 'zayif': False}

    def test_program_onay_ister(self):
        with mock.patch('core.layers.pipeline_layers.hedef_dosyayi_coz',
                        return_value="C:/a/kurulum.exe"):
            ctx = self.katman.process(self._ctx(self._plan()))
        self.assertEqual(ctx.security_level, "CONFIRM")
        self.assertIn("program", ctx.security_message.lower())

    def test_belge_onay_istemez(self):
        with mock.patch('core.layers.pipeline_layers.hedef_dosyayi_coz',
                        return_value="C:/a/rapor.pdf"):
            ctx = self.katman.process(self._ctx(self._plan()))
        self.assertEqual(ctx.security_level, "SAFE")


class OnayliYurutucuTest(unittest.TestCase):

    def test_onayli_acma_tekrar_onay_istemez(self):
        """
        Onay kartından geçen komut `onaylandi=True` ile çağrılmazsa
        file_send tekrar onay ister ve kullanıcı sonsuz döngüye girer.
        """
        from features.confirmed_executor import onayli_komut_yurut
        plan = {'islem': 'ac', 'sorgu': 'kurulum', 'secim': None, 'hedef': None,
                'alici': None, 'tur': '.exe', 'zayif': False}
        with mock.patch('features.file_send.dosya_niyeti_coz', return_value=plan), \
             mock.patch('features.file_send.dosya_komutu_isle',
                        return_value=(True, "açıldı")) as isle:
            onayli_komut_yurut("kurulum.exe dosyasını aç")
        self.assertTrue(isle.call_args.kwargs.get('onaylandi'),
                        "onaylı çağrı onaylandi=True geçmiyor → sonsuz onay döngüsü")


if __name__ == '__main__':
    unittest.main()
