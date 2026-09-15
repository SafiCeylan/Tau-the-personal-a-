# -*- coding: utf-8 -*-
"""
ULTRON — Arka Plan Uygulama Yönetimi Testleri

⚠️ BU DOSYANIN EN KRİTİK TESTİ `test_masum_cumle_uygulama_oldurmez`.
   12 Ağu 2026'da modül şöyle davranıyordu: "başka var mı?" bayrağı bir kez
   açılınca KALICIYDI ve içeride cümledeki HERHANGİ bir 1-2 haneli sayı liste
   indeksi sayılıyordu. Ölçülen sonuç: `"saat 3 te hatırlat"` → listedeki
   3. uygulama (ChatGPT) kapatıldı. Aynı şekilde "chrome aç" (Chrome açıkken)
   isim eşleşmesine takılıp Chrome'u ÖLDÜRÜYORDU.
"""

import unittest
from unittest.mock import patch

from features import background_apps


class TestBackgroundApps(unittest.TestCase):

    def setUp(self):
        background_apps._SON_LISTE.clear()
        background_apps._BEKLEYEN_SORU.clear()

    def test_calisan_uygulamalar(self):
        apps = background_apps.çalışan_uygulamaları_getir()
        self.assertIsInstance(apps, list)

    def test_liste_olustur(self):
        res = background_apps.arka_plan_listesi_olustur()
        self.assertIsInstance(res, str)
        self.assertTrue("ARKA PLANDA" in res or "bulunamadı" in res)

    def test_altyapi_surecleri_listelenmez(self):
        """`msedgewebview2.exe`, "System Idle Process" kullanıcı uygulaması değildir."""
        adlar = {a['proc_name'].lower() for a in background_apps.çalışan_uygulamaları_getir()}
        for gurultu in ('msedgewebview2.exe', 'system idle process', 'crashpad_handler.exe'):
            self.assertNotIn(gurultu, adlar)

    def test_kapatma_hayir(self):
        background_apps.arka_plan_listesi_olustur()
        status, msg = background_apps.arka_plan_uygulamasi_kapat("hayır")
        self.assertTrue(status)
        self.assertTrue("Anlaşıldı" in msg)
        self.assertFalse(background_apps.bekleyen_kapatma_sorusu_var_mi())

    def test_masum_cumle_uygulama_oldurmez(self):
        """Kapatma fiili olmayan hiçbir cümle süreç sonlandırmamalı."""
        with patch('features.actions.system_control.surec_kapat') as sahte:
            sahte.return_value = (True, "sahte")
            background_apps.arka_plan_listesi_olustur()   # bayrağı aç
            for cumle in ["saat 3 te hatırlat", "saat 3'te hatırlat", "chrome aç",
                          "spotify aç", "5 dakika sonra uyut", "sesi 30 yap",
                          "bugün hava nasıl", "2 saat sonra toplantım var"]:
                with self.subTest(cumle=cumle):
                    background_apps.arka_plan_komutu_isle(cumle)
                    self.assertEqual(sahte.call_count, 0,
                                     f"{cumle!r} süreç öldürdü: {sahte.call_args}")

    def test_numarali_kapatma_dogru_hedefi_secer(self):
        with patch('features.actions.system_control.surec_kapat') as sahte:
            sahte.return_value = (True, "sahte")
            background_apps.arka_plan_listesi_olustur()
            liste = background_apps._SON_LISTE.get("desktop") or []
            if not liste:
                self.skipTest("Listelenecek arka plan uygulaması yok")
            sonuc = background_apps.arka_plan_komutu_isle("1'i kapat")
            self.assertIsNotNone(sonuc)
            self.assertEqual(sahte.call_args[0][0], liste[0]['proc_name'])

    def test_ilgisiz_komut_none_doner(self):
        """None dönmezse akış burada kesilir ve komut asıl sahibine ulaşamaz."""
        self.assertIsNone(background_apps.arka_plan_komutu_isle("bugün hava nasıl"))
        self.assertIsNone(background_apps.arka_plan_komutu_isle("chrome aç"))

    def test_kanal_ayrimi(self):
        """Telefondaki '1'i kapat', masaüstü listesinin 1. uygulamasını vurmamalı."""
        with patch('features.actions.system_control.surec_kapat') as sahte:
            sahte.return_value = (True, "sahte")
            background_apps.arka_plan_listesi_olustur(kanal="desktop")
            self.assertTrue(background_apps.bekleyen_kapatma_sorusu_var_mi("desktop"))
            self.assertFalse(background_apps.bekleyen_kapatma_sorusu_var_mi("123456"))


if __name__ == "__main__":
    unittest.main()
