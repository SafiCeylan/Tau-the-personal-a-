# -*- coding: utf-8 -*-
"""
Recovery Engine testleri (Faz 4).

    Dosya bulunamadı → yakın isim ara → indeksi güncelle → kullanıcıya sor

EN KRİTİK TEST: `test_riskli_arac_asla_tekrar_edilmez`.
"Gönderim başarısız oldu, tekrar deneyeyim" davranışı aynı mesajı/dosyayı
İKİ KEZ göndermek demektir. Kurtarma yalnızca güvenli araç çalıştırabilir.
"""

import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.recovery import (
    BULUNAMADI, ERISILEMEDI, BILINMIYOR, MAKS_DENEME,
    _sorguyu_gevset, hata_tipini_coz, kurtar, kurtarma_denemeleri, kurtarma_raporu,
)
from core.tools import DEFTER, AracSonuc, RISK_GUVENLI, RISK_ONAY
import core.builtin_tools  # noqa: F401


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class HataTipiTest(unittest.TestCase):

    def test_bulunamadi_taninir(self):
        for mesaj in ("🔍 `staj` için eşleşen dosya bulunamadı.",
                      "⚠️ rapor.pdf artık yerinde değil.",
                      "⚠️ O numarada bir dosya yok."):
            self.assertEqual(hata_tipini_coz(AracSonuc.hata(mesaj)), BULUNAMADI, mesaj)

    def test_ag_hatasi_taninir(self):
        for mesaj in ("Ollama'ya bağlanılamadı", "İnternet yok", "zaman aşımı"):
            self.assertEqual(hata_tipini_coz(AracSonuc.hata(mesaj)), ERISILEMEDI, mesaj)

    def test_taninmayan_hata_bilinmiyor(self):
        self.assertEqual(hata_tipini_coz(AracSonuc.hata("tuhaf bir şey oldu")), BILINMIYOR)

    def test_aracin_acik_bildirimi_oncelikli(self):
        """Mesaj metnine bakmak kırılgan; araç açıkça söylerse ona güven."""
        sonuc = AracSonuc.hata("herhangi bir metin", hata_tipi=BULUNAMADI)
        self.assertEqual(hata_tipini_coz(sonuc), BULUNAMADI)


class SorguGevsetmeTest(unittest.TestCase):

    def test_en_ayirt_edici_kelime_secilir(self):
        self.assertEqual(_sorguyu_gevset("staj raporu 2026 final"), "final")

    def test_zayif_kelimeler_elenir(self):
        """'dosya', 'son', 'rapor' ayırt edici değil."""
        self.assertEqual(_sorguyu_gevset("son maliyet dosya"), "maliyet")

    def test_tek_kelimelik_sorgu_gevsetilemez(self):
        self.assertIsNone(_sorguyu_gevset("staj"))

    def test_bos_sorgu_cokmez(self):
        self.assertIsNone(_sorguyu_gevset(""))
        self.assertIsNone(_sorguyu_gevset(None))

    def test_sadece_zayif_kelime_varsa_havuza_donulur(self):
        self.assertIsNotNone(_sorguyu_gevset("son dosya"))


class StratejiTest(unittest.TestCase):

    def _bulunamadi(self):
        return AracSonuc.hata("eşleşen dosya bulunamadı")

    def test_dosya_bulunamadida_gevsetme_denemesi_uretilir(self):
        denemeler = kurtarma_denemeleri(
            "dosya_ara", {"sorgu": "staj raporu 2026"}, self._bulunamadi())
        self.assertTrue(denemeler)
        self.assertEqual(denemeler[0].arac_adi, "indeks_ara")
        # 'raporu' zayıf kelime listesinde → elenir; kalanlardan en uzunu seçilir
        self.assertEqual(denemeler[0].parametreler["sorgu"], "staj")

    def test_riskli_arac_asla_tekrar_edilmez(self):
        """
        EN KRİTİK TEST. dosya_gonder başarısız olduğunda kurtarma onu TEKRAR
        ÇAĞIRAMAZ — aynı dosya iki kez gönderilir.
        """
        denemeler = kurtarma_denemeleri(
            "dosya_gonder", {"metin": "staj raporu anneme"}, self._bulunamadi())
        for deneme in denemeler:
            arac = DEFTER.getir(deneme.arac_adi)
            self.assertEqual(arac.risk, RISK_GUVENLI,
                             f"kurtarma riskli araç çalıştırıyor: {deneme.arac_adi}")

    def test_riskli_aracin_kurtarmasi_teshistir(self):
        """Gönderim kurtarması sadece bulur ve bildirir; kendiliğinden göndermez."""
        denemeler = kurtarma_denemeleri(
            "dosya_gonder", {"metin": "staj raporu anneme"}, self._bulunamadi())
        self.assertTrue(denemeler)
        self.assertTrue(all(d.teshis for d in denemeler))

    def test_guvenli_arac_kurtarmasi_teshis_degil(self):
        denemeler = kurtarma_denemeleri(
            "dosya_ara", {"sorgu": "staj raporu"}, self._bulunamadi())
        self.assertFalse(denemeler[0].teshis)

    def test_ag_hatasinda_tek_tekrar(self):
        denemeler = kurtarma_denemeleri(
            "hava_durumu", {"metin": "hava"}, AracSonuc.hata("bağlanılamadı"))
        self.assertEqual(len(denemeler), 1)
        self.assertEqual(denemeler[0].arac_adi, "hava_durumu")

    def test_bilinmeyen_hatada_kurtarma_yok(self):
        self.assertEqual(
            kurtarma_denemeleri("doviz", {}, AracSonuc.hata("tuhaf hata")), [])

    def test_bilinmeyen_arac_cokmez(self):
        self.assertEqual(
            kurtarma_denemeleri("olmayan_arac", {}, self._bulunamadi()), [])

    def test_deneme_sayisi_sinirli(self):
        with mock.patch("core.recovery._indeks_bayat_mi", return_value=True):
            denemeler = kurtarma_denemeleri(
                "dosya_ara", {"sorgu": "staj raporu 2026"}, self._bulunamadi())
        self.assertLessEqual(len(denemeler), MAKS_DENEME)


class KurtarmaYurutmeTest(unittest.TestCase):

    def _bulunamadi(self):
        return AracSonuc.hata("eşleşen dosya bulunamadı")

    def test_kurtarma_basarili_olursa_bildirilir(self):
        with mock.patch.object(DEFTER.getir("indeks_ara"), 'calistir',
                               return_value=AracSonuc.ok("bulundu: rapor.pdf")):
            kurtarma = kurtar("dosya_ara", {"sorgu": "staj raporu 2026"},
                              self._bulunamadi())
        self.assertTrue(kurtarma.denendi)
        self.assertTrue(kurtarma.basarili)
        self.assertIn("rapor.pdf", kurtarma.mesaj)

    def test_teshis_basarili_olsa_bile_gorev_tamamlanmaz(self):
        """Dosyayı buldu ama GÖNDERMEDİ — karar kullanıcının."""
        with mock.patch.object(DEFTER.getir("indeks_ara"), 'calistir',
                               return_value=AracSonuc.ok("bulundu: rapor.pdf")):
            kurtarma = kurtar("dosya_gonder", {"metin": "staj raporu anneme"},
                              self._bulunamadi())
        self.assertTrue(kurtarma.denendi)
        self.assertFalse(kurtarma.basarili)
        self.assertIn("rapor.pdf", kurtarma.mesaj)

    def test_hepsi_basarisizsa_denendi_ama_basarisiz(self):
        with mock.patch.object(DEFTER.getir("indeks_ara"), 'calistir',
                               return_value=AracSonuc.hata("yine bulunamadı")):
            kurtarma = kurtar("dosya_ara", {"sorgu": "staj raporu 2026"},
                              self._bulunamadi())
        self.assertTrue(kurtarma.denendi)
        self.assertFalse(kurtarma.basarili)
        self.assertTrue(kurtarma.adimlar)

    def test_kurtarma_araci_cokerse_yutulur(self):
        with mock.patch.object(DEFTER.getir("indeks_ara"), 'calistir',
                               side_effect=RuntimeError("patladı")):
            kurtarma = kurtar("dosya_ara", {"sorgu": "staj raporu 2026"},
                              self._bulunamadi())
        self.assertFalse(kurtarma.basarili)

    def test_kurtarilamayanda_hic_denenmez(self):
        kurtarma = kurtar("doviz", {}, AracSonuc.hata("tuhaf hata"))
        self.assertFalse(kurtarma.denendi)


class RaporTest(unittest.TestCase):

    def test_denenen_adimlar_kullaniciya_gosterilir(self):
        from core.recovery import KurtarmaSonucu
        kurtarma = KurtarmaSonucu(denendi=True, basarili=False,
                                  adimlar=["↳ adı gevşettim — sonuç yok"])
        rapor = kurtarma_raporu("bulunamadı", kurtarma)
        self.assertIn("bulunamadı", rapor)
        self.assertIn("gevşettim", rapor)
        self.assertIn("?", rapor)          # kullanıcıya soru sorulmalı

    def test_basarili_kurtarmada_soru_sorulmaz(self):
        from core.recovery import KurtarmaSonucu
        kurtarma = KurtarmaSonucu(denendi=True, basarili=True,
                                  mesaj="bulundu", adimlar=["↳ gevşettim ✅"])
        rapor = kurtarma_raporu("bulunamadı", kurtarma)
        self.assertNotIn("Devam etmemi ister misin", rapor)


class MotorKurtarmaTest(unittest.TestCase):
    """Tek adımlı komutta kurtarma boru hattında devrede mi?"""

    def setUp(self):
        from core.engine import UltronCoreEngine
        from core.context_manager import BAGLAM
        BAGLAM.hepsini_temizle()
        self.motor = UltronCoreEngine(config={"ai_provider": "ollama",
                                              "planner_enabled": False})

    def test_ustlenilmeyen_komutta_kurtarma_calismaz(self):
        """'Üstlenmedi' bir hata değil — komut sohbete ait, kurtarılacak bir şey yok."""
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.islenmedi()), \
             mock.patch("core.recovery.kurtar") as kurtarma:
            self.motor.process("hava durumu nasıl", allow_llm=False)
        kurtarma.assert_not_called()

    def test_gercek_hatada_kurtarma_calisir(self):
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.hata("bağlanılamadı")) as hava:
            ctx = self.motor.process("hava durumu nasıl", allow_llm=False)
        # ilk çağrı + kurtarma tekrarı
        self.assertEqual(hava.call_count, 2)
        self.assertIn("bir kez daha", ctx.execution_result)

    def test_kurtarma_basarili_olursa_komut_basarili_sayilir(self):
        cevaplar = [AracSonuc.hata("bağlanılamadı"), AracSonuc.ok("22 derece")]
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               side_effect=cevaplar):
            ctx = self.motor.process("hava durumu nasıl", allow_llm=False)
        self.assertTrue(ctx.execution_success)
        self.assertIn("22 derece", ctx.execution_result)


if __name__ == '__main__':
    unittest.main()


class IndeksAraTest(unittest.TestCase):
    """
    Kurtarmanın kullandığı GÜVENLİ indeks arama aracı.

    Neden ayrı araç: indeks araması `dosya_gonder` içinde gömülüydü ve o araç
    RISK_ONAY olduğu için kurtarma onu çalıştıramıyordu (haklı olarak — kurtarma
    dosya göndermemeli). `dosya_ara` ise klasör bazlı file_finder'a gidiyor.
    """

    def test_arac_guvenli_olmali(self):
        """Riskli olsaydı kurtarma zinciri onu da reddederdi."""
        self.assertEqual(DEFTER.getir("indeks_ara").risk, RISK_GUVENLI)

    def test_sonuc_yoksa_bulunamadi_isaretlenir(self):
        with mock.patch("core.builtin_tools.file_index.ara", return_value=[]):
            sonuc = DEFTER.getir("indeks_ara").calistir(sorgu="zzzqqq")
        self.assertTrue(sonuc.basarili, "mesaj gösterilmeli, LLM'e düşmemeli")
        self.assertEqual(sonuc.hata_tipi, BULUNAMADI)

    def test_sonuclar_listelenir_ve_kanala_kaydedilir(self):
        bulunanlar = [{'ad': 'a.pdf', 'yol': 'C:/a.pdf'}]
        with mock.patch("core.builtin_tools.file_index.ara", return_value=bulunanlar), \
             mock.patch("core.builtin_tools.file_index.sonuclari_bicimle",
                        return_value="liste"), \
             mock.patch("core.builtin_tools.file_index.son_sonuclari_kaydet") as kaydet:
            sonuc = DEFTER.getir("indeks_ara").calistir(sorgu="a", kanal="12345")
        self.assertTrue(sonuc.basarili)
        self.assertIsNone(sonuc.hata_tipi)
        kaydet.assert_called_once()
        self.assertEqual(kaydet.call_args[0][0], "12345")   # kanal ayrımı korunur

    def test_dosya_gondermez(self):
        """Salt-okunur: gönderim yolu hiç çağrılmamalı."""
        with mock.patch("core.builtin_tools.file_index.ara", return_value=[]), \
             mock.patch("core.builtin_tools.dosya_komutu_isle") as gonder:
            DEFTER.getir("indeks_ara").calistir(sorgu="x")
        gonder.assert_not_called()
