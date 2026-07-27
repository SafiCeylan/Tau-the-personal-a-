# -*- coding: utf-8 -*-
"""
Context Manager testleri (Faz 2).

Çözülen sorun: "Dosyayı yükle." → hangi dosya?

EN TEHLİKELİ HATA BİÇİMİ: yanlış referans çözümü. "onu anneme gönder" yanlış
dosyaya bağlanırsa kullanıcı farkında olmadan yanlış dosyayı gönderir. Bu yüzden
testlerin çoğu "ÇÖZMEMESİ gereken durumlar" üzerine.
"""

import time
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.context_manager import BaglamYoneticisi, KanalBaglami
from core.tools import DEFTER, AracSonuc
import core.builtin_tools  # noqa: F401


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class HatirlamaTest(unittest.TestCase):

    def setUp(self):
        self.y = BaglamYoneticisi()

    def test_bos_baglamda_none_doner(self):
        self.assertIsNone(self.y.getir("desktop"))

    def test_hatirlanan_deger_geri_gelir(self):
        self.y.hatirla("desktop", son_dosya="rapor.pdf")
        self.assertEqual(self.y.getir("desktop").son_dosya, "rapor.pdf")

    def test_kismi_guncelleme_digerlerini_silmez(self):
        """Yeni uygulama açmak, konuşulan dosyayı unutturmamalı."""
        self.y.hatirla("desktop", son_dosya="rapor.pdf")
        self.y.hatirla("desktop", son_uygulama="chrome")
        baglam = self.y.getir("desktop")
        self.assertEqual(baglam.son_dosya, "rapor.pdf")
        self.assertEqual(baglam.son_uygulama, "chrome")

    def test_none_deger_mevcudu_ezmez(self):
        self.y.hatirla("desktop", son_dosya="rapor.pdf")
        self.y.hatirla("desktop", son_dosya=None)
        self.assertEqual(self.y.getir("desktop").son_dosya, "rapor.pdf")

    def test_bilinmeyen_alan_yok_sayilir(self):
        self.y.hatirla("desktop", uydurma_alan="x")
        self.assertIsNotNone(self.y.getir("desktop"))

    def test_kanallar_birbirine_karismaz(self):
        """Telefondaki dosya masaüstündeki 'onu gönder'e karışmamalı."""
        self.y.hatirla("12345", son_dosya="telefon.pdf")
        self.y.hatirla("desktop", son_dosya="masaustu.pdf")
        self.assertEqual(self.y.getir("12345").son_dosya, "telefon.pdf")
        self.assertEqual(self.y.getir("desktop").son_dosya, "masaustu.pdf")

    def test_bayat_baglam_dusurulur(self):
        """İki saat önceki dosya 'dosyayı gönder' komutuna karışmamalı."""
        y = BaglamYoneticisi(omur_sn=1)
        y.hatirla("desktop", son_dosya="eski.pdf")
        with mock.patch("core.context_manager.time.time", return_value=time.time() + 10):
            self.assertIsNone(y.getir("desktop"))

    def test_temizle_kanali_siler(self):
        self.y.hatirla("desktop", son_dosya="x.pdf")
        self.y.temizle("desktop")
        self.assertIsNone(self.y.getir("desktop"))


class ReferansCozumTest(unittest.TestCase):

    def setUp(self):
        self.y = BaglamYoneticisi()

    # --- çözmesi gerekenler ------------------------------------------
    def test_onu_son_dosyaya_baglanir(self):
        self.y.hatirla("desktop", son_dosya="staj raporu.pdf")
        metin, notlar = self.y.coz("onu anneme gönder", "desktop")
        self.assertIn("staj raporu.pdf", metin)
        self.assertTrue(notlar)

    def test_ciplak_dosyayi_son_dosyaya_baglanir(self):
        self.y.hatirla("desktop", son_dosya="staj raporu.pdf")
        metin, _ = self.y.coz("dosyayı yükle", "desktop")
        self.assertIn("staj raporu.pdf", metin)

    def test_ona_son_kisiye_baglanir(self):
        self.y.hatirla("desktop", son_kisi="Ahmet")
        metin, _ = self.y.coz("ona mesaj at", "desktop")
        self.assertIn("Ahmet", metin)

    def test_dosya_yoksa_son_konu_kullanilir(self):
        self.y.hatirla("desktop", son_konu="python öğrenmek")
        metin, _ = self.y.coz("onu araştır", "desktop")
        self.assertIn("python öğrenmek", metin)

    def test_her_cozum_not_birakir(self):
        """Sessiz tahmin yok — kullanıcı neyin varsayıldığını görmeli."""
        self.y.hatirla("desktop", son_dosya="rapor.pdf")
        _, notlar = self.y.coz("onu gönder", "desktop")
        self.assertEqual(len(notlar), 1)
        self.assertIn("rapor.pdf", notlar[0])

    # --- ÇÖZMEMESİ gerekenler (asıl tehlike burada) ------------------
    def test_baglam_yoksa_metin_degismez(self):
        metin, notlar = self.y.coz("onu gönder", "desktop")
        self.assertEqual(metin, "onu gönder")
        self.assertEqual(notlar, [])

    def test_bayat_baglam_cozum_yapmaz(self):
        y = BaglamYoneticisi(omur_sn=1)
        y.hatirla("desktop", son_dosya="eski.pdf")
        with mock.patch("core.context_manager.time.time", return_value=time.time() + 10):
            metin, notlar = y.coz("onu gönder", "desktop")
        self.assertEqual(metin, "onu gönder")
        self.assertEqual(notlar, [])

    def test_baska_kanalin_baglami_kullanilmaz(self):
        self.y.hatirla("12345", son_dosya="telefon.pdf")
        metin, _ = self.y.coz("onu gönder", "desktop")
        self.assertNotIn("telefon.pdf", metin)

    def test_adi_verilmis_dosya_ezilmez(self):
        """'staj raporunu gönder' zaten kendi adını taşıyor — dokunma."""
        self.y.hatirla("desktop", son_dosya="baska.pdf")
        metin, notlar = self.y.coz("staj raporunu gönder", "desktop")
        self.assertEqual(metin, "staj raporunu gönder")
        self.assertEqual(notlar, [])

    def test_referanssiz_cumle_degismez(self):
        self.y.hatirla("desktop", son_dosya="rapor.pdf", son_kisi="Ahmet")
        metin, notlar = self.y.coz("hava durumu nasıl", "desktop")
        self.assertEqual(metin, "hava durumu nasıl")
        self.assertEqual(notlar, [])

    def test_bos_metin_cokmez(self):
        self.assertEqual(self.y.coz("", "desktop"), ("", []))
        self.assertEqual(self.y.coz(None, "desktop"), (None, []))

    def test_sadece_ilk_esleme_degistirilir(self):
        """Cümlede iki 'onu' varsa ikisi birden şişirilmemeli."""
        self.y.hatirla("desktop", son_dosya="rapor.pdf")
        metin, _ = self.y.coz("onu aç onu gönder", "desktop")
        self.assertEqual(metin.count("rapor.pdf"), 1)


class MotorBaglamTest(unittest.TestCase):
    """Motor entegrasyonu: bağlam kaydı ve çözümü boru hattında."""

    def setUp(self):
        from core.engine import UltronCoreEngine
        from core.context_manager import BAGLAM
        BAGLAM.hepsini_temizle()
        self.motor = UltronCoreEngine(config={"ai_provider": "ollama"})

    def test_basarisiz_komut_baglami_kirletmez(self):
        """Başarısız komutun konusu 'en son konuşulan şey' sayılmamalı."""
        from core.context_manager import BAGLAM
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.islenmedi()):
            self.motor.process("hava durumu nasıl", allow_llm=False)
        self.assertIsNone(BAGLAM.getir("desktop"))

    def test_basarili_komut_intenti_hatirlanir(self):
        from core.context_manager import BAGLAM
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22 derece")):
            self.motor.process("hava durumu nasıl", allow_llm=False)
        self.assertEqual(BAGLAM.getir("desktop").son_intent, "WEATHER")

    def test_cozulen_referans_kullaniciya_bildirilir(self):
        from core.context_manager import BAGLAM
        BAGLAM.hatirla("desktop", son_dosya="staj raporu.pdf")
        with mock.patch.object(DEFTER.getir("dosya_ara"), 'calistir',
                               return_value=AracSonuc.ok("bulundu")):
            ctx = self.motor.process("dosyayı bul", allow_llm=False)
        self.assertIn("bağlamdan", ctx.execution_result)
        self.assertIn("staj raporu.pdf", ctx.execution_result)

    def test_baglam_cozumu_niyet_analizinden_once_calisir(self):
        """
        "onu anneme gönder" cümlesinde dosya adı yoksa FILE_TRANSFER regex'i
        eşleşmez ve komut sohbete düşer. Çözüm intent'ten ÖNCE olmalı.
        """
        from core.context_manager import BAGLAM
        BAGLAM.hatirla("desktop", son_dosya="staj raporu.pdf")
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("x")):
            ctx = self.motor.process("onu bana göster", allow_llm=False)
        self.assertIn("staj raporu.pdf", ctx.normalized_input)


if __name__ == '__main__':
    unittest.main()


class DosyaIkameBicimiTest(unittest.TestCase):
    """
    CANLI TESTTE YAKALANAN: çıplak dosya adı hiçbir dosya aracına gitmiyor.
    "ULTRON.spec aç" → SYSTEM_CONTROL ("ULTRON.spec adlı uygulamayı aç").
    Dosya ikamesine "dosyasını" eki eklenerek güçlü dosya sinyali üretilir.
    """

    def setUp(self):
        self.y = BaglamYoneticisi()
        self.y.hatirla("desktop", son_dosya="ULTRON.spec")

    def test_dosya_ikamesi_guclu_sinyal_tasir(self):
        metin, _ = self.y.coz("onu bana gönder", "desktop")
        self.assertIn("ULTRON.spec", metin)
        self.assertIn("dosya", metin.lower())

    def test_kullaniciya_gosterilen_notta_teknik_ek_yok(self):
        """Not sade olmalı: 'onu → ULTRON.spec', 'dosyasını' eki görünmesin."""
        _, notlar = self.y.coz("onu bana gönder", "desktop")
        self.assertEqual(notlar, ["'onu' → ULTRON.spec"])

    def test_konu_ikamesine_dosya_eki_eklenmez(self):
        y = BaglamYoneticisi()
        y.hatirla("desktop", son_konu="python öğrenmek")
        metin, _ = y.coz("onu araştır", "desktop")
        self.assertNotIn("dosyasını", metin)
