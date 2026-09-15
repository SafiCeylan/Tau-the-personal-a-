# -*- coding: utf-8 -*-
import unittest
import tempfile
import shutil

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
import features.finance_tracker as ft


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class TestFinanceTracker(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.orig_db_yolu = ft.veri_dizini
        ft.veri_dizini = lambda: self.tmp_dir

    def tearDown(self):
        ft.veri_dizini = self.orig_db_yolu
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # TÜRKÇE SAYI BİÇİMİ — bu testler ölçülmüş bir para hatasını kilitler:
    # "1.200 TL" naif replace(",",".") ile 1.2 TL oluyordu (1000 kat eksik).
    # ------------------------------------------------------------------
    def test_binlik_ayraci_bin_kati_kaybettirmez(self):
        self.assertEqual(ft.turkce_para_coz("1.200"), 120000)       # 1200,00 TL
        self.assertEqual(ft.turkce_para_coz("12.500"), 1250000)     # 12500,00 TL
        self.assertEqual(ft.turkce_para_coz("1.250,75"), 125075)    # 1250,75 TL

    def test_ondalik_virgul_ve_nokta(self):
        self.assertEqual(ft.turkce_para_coz("87,50"), 8750)
        self.assertEqual(ft.turkce_para_coz("50.50"), 5050)   # 3 hane değil → ondalık
        self.assertEqual(ft.turkce_para_coz("350"), 35000)

    def test_bozuk_girdi_none_doner(self):
        for kotu in ("", "abc", "1.2.3,4,5"):
            self.assertIsNone(ft.turkce_para_coz(kotu), kotu)

    def test_kurus_tl_metnine_cevrilir(self):
        self.assertEqual(ft.kurus_to_tl(125075), "1.250,75")
        self.assertEqual(ft.kurus_to_tl(35000), "350,00")
        self.assertEqual(ft.kurus_to_tl(5), "0,05")

    # ------------------------------------------------------------------
    def test_harcama_cumlesi_coz(self):
        m, _a, k = ft.harcama_cumlesi_coz("bugün markete 350 TL harcadım")
        self.assertEqual(m, 35000)
        self.assertEqual(k, "market")

        m2, _a2, k2 = ft.harcama_cumlesi_coz("benzine 1200 lira verdim")
        self.assertEqual(m2, 120000)
        self.assertEqual(k2, "ulasim")

        m3, _a3, _k3 = ft.harcama_cumlesi_coz("kiraya 12.500 TL ödedim")
        self.assertEqual(m3, 1250000)

    def test_tutarsiz_cumle_kayit_uretmez(self):
        m, a, k = ft.harcama_cumlesi_coz("harcamalarım ne durumda")
        self.assertIsNone(m)
        self.assertIsNone(a)
        self.assertEqual(k, "Genel")

    def test_harcama_ekle_ve_ozeti(self):
        self.assertTrue(ft.harcama_ekle(35000, "markete 350 TL harcadım", "market")["basarili"])
        self.assertTrue(ft.harcama_ekle(15000, "öğle yemeği 150 TL", "yemek")["basarili"])

        ozet = ft.harcama_ozeti()
        self.assertTrue(ozet["basarili"])
        self.assertEqual(ozet["toplam_kurus"], 50000)
        self.assertEqual(ozet["adet"], 2)

    def test_kayit_yokken_sifir_degil_aciklama_doner(self):
        ozet = ft.harcama_ozeti()
        self.assertTrue(ozet["basarili"])
        self.assertEqual(ozet["adet"], 0)
        self.assertIn("harcama yok", ozet["mesaj"])

    def test_kategori_filtresi_dagilima_da_uygulanir(self):
        """Eskiden kategori filtresi yalnız toplama uygulanıyordu; dağılım
        filtresizdi ve toplam ile kalemler tutmuyordu."""
        ft.harcama_ekle(35000, "market", "market")
        ft.harcama_ekle(15000, "yemek", "yemek")

        ozet = ft.harcama_ozeti(kategori="market")
        self.assertEqual(ozet["toplam_kurus"], 35000)
        self.assertEqual(list(ozet["kategoriler"].keys()), ["market"])
        self.assertEqual(sum(ozet["kategoriler"].values()), ozet["toplam_kurus"])

    # ------------------------------------------------------------------
    # DÖNEM — "bugün ne kadar harcadım" ile "toplam harcamam" aynı şey değil.
    # ------------------------------------------------------------------
    def test_donem_coz(self):
        self.assertEqual(ft.donem_coz("bugün ne kadar harcadım")[0], 'gun')
        self.assertEqual(ft.donem_coz("bu hafta harcamalarım")[0], 'hafta')
        self.assertEqual(ft.donem_coz("bu ay ne harcadım")[0], 'ay')
        self.assertEqual(ft.donem_coz("tüm zamanların harcaması")[0], 'hepsi')
        # Pencere belirtilmemişse varsayılan AY olmalı — tüm zamanlar DEĞİL.
        self.assertEqual(ft.donem_coz("harcama özeti")[0], 'ay')

    def test_gunluk_ozet_bugunun_kaydini_gorur(self):
        ft.harcama_ekle(35000, "bugünkü market", "market")
        ozet = ft.harcama_ozeti(donem='gun', donem_etiketi='bugün')
        self.assertEqual(ozet["toplam_kurus"], 35000)
        self.assertIn("bugün", ozet["mesaj"])

    def test_finans_niyeti_algila(self):
        self.assertTrue(ft.finans_niyeti_algila("bugün markete 350 TL harcadım"))
        self.assertTrue(ft.finans_niyeti_algila("bu ayki harcamalarım nerede"))
        self.assertTrue(ft.finans_niyeti_algila("harcama özeti göster"))
        self.assertTrue(ft.finans_niyeti_algila("kiraya 12.500 TL ödedim"))
        # Alakasız cümle finans sanılmamalı
        self.assertFalse(ft.finans_niyeti_algila("chrome aç"))
        self.assertFalse(ft.finans_niyeti_algila("saat kaç"))


if __name__ == "__main__":
    unittest.main()
