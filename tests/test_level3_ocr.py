# -*- coding: utf-8 -*-
"""
AIP Level 3 (OCR ile tıklama) testleri — core/interaction/level3_ocr.py

Bu katmanın tek işi FAREYİ KULLANICI ADINA HAREKET ETTİRMEK. Bu yüzden burada
sınanan şey "tıklıyor mu" değil, **NE ZAMAN TIKLAMADIĞI**. Yanlış yere yapılan
bir tıklama geri alınamaz: bir onay kutusunu, bir "Sil" düğmesini, bir ödeme
butonunu tetikleyebilir.

DÖRT KİLİDİN HER BİRİ AYRI TESTLE KİLİTLENMİŞTİR:

  • `test_coklu_eslesmede_tiklamaz` — "Kaydet" üç yerde geçiyorsa hangisi
    olduğunu bilemeyiz. Tahmin yürütmek en tehlikeli davranıştır.
  • `test_odak_disindaysa_tiklamaz` — hedef pencere önde değilken tıklamak,
    o an önde olan pencereye basmak demektir.
  • `test_pencere_kaydiysa_tiklamaz` — OCR ile tıklama arasında pencere
    taşınırsa koordinat bayattır; aynı pencerenin YANLIŞ yerine basılır.
  • `test_nokta_baska_pencereye_aitse_tiklamaz` — araya bildirim/açılır pencere
    girerse tıklama ona gider.

İZOLASYON: `tests/safety.py` zırhı level3_ocr'ın ctypes'ını taklitler; hiçbir
test gerçekten fareyi oynatmaz. Zırhın kendisi de `test_zirh_fareyi_kesiyor`
ile doğrulanır — zırh sessizce düşerse bu paket kullanıcının ekranına tıklar.
"""

import unittest
from unittest import mock

from tests.safety import CAGRI_KAYDI, guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.interaction import level3_ocr as l3


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


def okuma(kelimeler, baslik="Not Defteri", bolge=None):
    """Sahte `ekrani_oku()` çıktısı. kelimeler: [(metin, x, y, w, h)]"""
    return {
        "ok": True,
        "metin": " ".join(m for (m, *_r) in kelimeler),
        "satirlar": [" ".join(m for (m, *_r) in kelimeler)],
        "kelimeler": [{"metin": m, "x": x, "y": y, "w": w, "h": h}
                      for (m, x, y, w, h) in kelimeler],
        "baslik": baslik,
        "bolge": bolge or {"left": 0, "top": 0, "width": 800, "height": 600},
        "hata": "",
    }


class TiklamaKilitleriTest(unittest.TestCase):
    """Dört güvenlik kilidi — her biri tıklamayı iptal ETMELİ."""

    def setUp(self):
        CAGRI_KAYDI.clear()
        self.ocr = mock.patch.object(l3, 'ocr_click_available', return_value=True)
        self.ocr.start()
        self.addCleanup(self.ocr.stop)
        # Varsayılan: her şey yolunda (odak doğru, pencere kaymadı, nokta hedefte)
        self._yamala('_onplan_basligi', "Not Defteri")
        self._yamala('_bolge_ayni_mi', True)
        self._yamala('_noktadaki_pencere_basligi', "Not Defteri")

    def _yamala(self, ad, deger):
        y = mock.patch.object(l3, ad, return_value=deger)
        y.start()
        self.addCleanup(y.stop)

    def _tiklandi_mi(self):
        return any(c[0] == 'user32.mouse_event' for c in CAGRI_KAYDI)

    # --- mutlu yol: dördü de sağlanınca TIKLAR ---
    def test_tek_eslesmede_tiklar(self):
        sonuc = l3.metne_tikla("Kaydet", okuma=okuma([("Kaydet", 100, 200, 60, 20)]))
        self.assertTrue(sonuc.success, sonuc.message)
        self.assertEqual(sonuc.level, "vision")
        self.assertEqual((sonuc.detail['x'], sonuc.detail['y']), (130, 210))
        self.assertTrue(self._tiklandi_mi())

    # --- KİLİT 1 ---
    def test_coklu_eslesmede_tiklamaz(self):
        sonuc = l3.metne_tikla("Kaydet", okuma=okuma([
            ("Kaydet", 100, 200, 60, 20),
            ("Kaydet", 400, 500, 60, 20),
        ]))
        self.assertFalse(sonuc.success)
        self.assertIn("belirsiz", sonuc.message)
        self.assertFalse(self._tiklandi_mi(), "ÇOK EŞLEŞMEDE TIKLADI — tehlikeli")

    def test_sira_verilirse_coklu_eslesmede_tiklar(self):
        sonuc = l3.metne_tikla("Kaydet", sira=1, okuma=okuma([
            ("Kaydet", 100, 200, 60, 20),
            ("Kaydet", 400, 500, 60, 20),
        ]))
        self.assertTrue(sonuc.success, sonuc.message)
        self.assertEqual((sonuc.detail['x'], sonuc.detail['y']), (430, 510))

    # --- KİLİT 2 ---
    def test_odak_disindaysa_tiklamaz(self):
        with mock.patch.object(l3, '_onplan_basligi', return_value="Banka - Chrome"):
            sonuc = l3.metne_tikla("Kaydet", okuma=okuma([("Kaydet", 10, 10, 60, 20)]))
        self.assertFalse(sonuc.success)
        self.assertIn("Odak koruması", sonuc.message)
        self.assertFalse(self._tiklandi_mi(), "ODAK DIŞINDA TIKLADI — tehlikeli")

    # --- KİLİT 3 ---
    def test_pencere_kaydiysa_tiklamaz(self):
        with mock.patch.object(l3, '_bolge_ayni_mi', return_value=False):
            sonuc = l3.metne_tikla("Kaydet", okuma=okuma([("Kaydet", 10, 10, 60, 20)]))
        self.assertFalse(sonuc.success)
        self.assertIn("taşındı", sonuc.message)
        self.assertFalse(self._tiklandi_mi(), "BAYAT KOORDİNATA TIKLADI — tehlikeli")

    # --- KİLİT 4 ---
    def test_nokta_baska_pencereye_aitse_tiklamaz(self):
        with mock.patch.object(l3, '_noktadaki_pencere_basligi',
                               return_value="Windows Güvenliği"):
            sonuc = l3.metne_tikla("Kaydet", okuma=okuma([("Kaydet", 10, 10, 60, 20)]))
        self.assertFalse(sonuc.success)
        self.assertIn("Windows Güvenliği", sonuc.message)
        self.assertFalse(self._tiklandi_mi(), "ARAYA GİREN PENCEREYE TIKLADI — tehlikeli")

    # --- diğer red yolları ---
    def test_metin_bulunamazsa_tiklamaz(self):
        sonuc = l3.metne_tikla("İptal", okuma=okuma([("Kaydet", 10, 10, 60, 20)]))
        self.assertFalse(sonuc.success)
        self.assertIn("bulunamadı", sonuc.message)
        self.assertFalse(self._tiklandi_mi())

    def test_bos_metin_reddedilir(self):
        sonuc = l3.metne_tikla("   ", okuma=okuma([("Kaydet", 10, 10, 60, 20)]))
        self.assertFalse(sonuc.success)
        self.assertFalse(self._tiklandi_mi())

    def test_okuma_basarisizsa_tiklamaz(self):
        sonuc = l3.metne_tikla("Kaydet", okuma={"ok": False, "hata": "⚠️ OCR yok"})
        self.assertFalse(sonuc.success)
        self.assertIn("OCR yok", sonuc.message)
        self.assertFalse(self._tiklandi_mi())

    def test_ocr_yoksa_nazikce_reddeder(self):
        with mock.patch.object(l3, 'ocr_click_available', return_value=False):
            sonuc = l3.metne_tikla("Kaydet")
        self.assertFalse(sonuc.success)
        self.assertIn("kullanılamıyor", sonuc.message)


class StratejiTest(unittest.TestCase):
    """Karar motoruna takılan sarmalayıcı."""

    def test_seviye_vision(self):
        self.assertEqual(l3.OcrClickStrategy.level, "vision")

    def test_metin_verilmezse_zinciri_bloklamaz(self):
        s = l3.OcrClickStrategy()
        with mock.patch.object(l3, 'ocr_click_available', return_value=True):
            sonuc = s.execute(uygulama="spotify")     # başka katmanın kwargs'ı
        self.assertFalse(sonuc.success)
        self.assertIn("ocr_text", sonuc.message)

    def test_karar_motoru_zincirinde_uia_ile_input_arasinda(self):
        """L2 başarısız olursa L3 denenmeli; L3 başarılıysa L4'e HİÇ gidilmemeli."""
        from core.interaction.base import InteractionResult, InteractionStrategy
        from core.interaction.decision_engine import InteractionDecisionEngine

        cagrilar = []

        class Sahte(InteractionStrategy):
            def __init__(self, level, basarili):
                self.level, self.name, self._ok = level, level, basarili

            def execute(self, **kwargs):
                cagrilar.append(self.level)
                return InteractionResult(self._ok, self.level, "")

        import tempfile, os
        with tempfile.TemporaryDirectory() as gecici:
            motor = InteractionDecisionEngine(os.path.join(gecici, "cache.json"))
            sonuc = motor.run_with("test_tikla", [
                Sahte("uia", False),
                Sahte("vision", True),
                Sahte("input", True),
            ])

        self.assertTrue(sonuc.success)
        self.assertEqual(sonuc.level, "vision")
        self.assertEqual(cagrilar, ["uia", "vision"], "L3 başarılıyken L4'e gidildi")


class ZirhTest(unittest.TestCase):
    """Zırhın kendisi çalışıyor mu? Düşerse bu paket kullanıcının ekranına tıklar."""

    def test_zirh_fareyi_kesiyor(self):
        CAGRI_KAYDI.clear()
        l3._sol_tikla(500, 500)
        adlar = [c[0] for c in CAGRI_KAYDI]
        self.assertIn('user32.SetCursorPos', adlar)
        self.assertIn('user32.mouse_event', adlar)


if __name__ == '__main__':
    unittest.main()
