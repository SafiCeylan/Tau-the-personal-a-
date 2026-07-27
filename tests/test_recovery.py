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
    _gevsetme_adaylari, _sorguyu_gevset, hata_tipini_coz, kurtar, kurtarma_denemeleri, kurtarma_raporu,
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


class GevsetmeAdaylariTest(unittest.TestCase):
    """Aday üretimi — saf metin işi, indekse dokunmaz."""

    def test_zayif_kelimeler_elenir(self):
        self.assertEqual(_gevsetme_adaylari("son maliyet dosya"), ["maliyet"])

    def test_dolgu_kelimeleri_elenir(self):
        """Canlıda 'falan' seçilip anlamsız arama yapıldı."""
        self.assertNotIn("falan", _gevsetme_adaylari("staj raporu 2026 falan"))

    def test_turkce_gurultu_elenir(self):
        """'dosyasını' (noktasız ı) ASCII listeyle eşleşmeliydi."""
        self.assertNotIn("dosyasini", _gevsetme_adaylari("staj dosyasını bul"))

    def test_uzun_aday_once_denenir(self):
        adaylar = _gevsetme_adaylari("ab maliyet tablosu")
        self.assertEqual(adaylar[0], "maliyet")

    def test_tek_kelimelik_sorgunun_adayi_yok(self):
        self.assertEqual(_gevsetme_adaylari("staj"), [])

    def test_bos_sorgu_cokmez(self):
        self.assertEqual(_gevsetme_adaylari(""), [])
        self.assertEqual(_gevsetme_adaylari(None), [])

    def test_sadece_zayif_kelime_varsa_havuza_donulur(self):
        self.assertTrue(_gevsetme_adaylari("son dosya"))


class SorguGevsetmeTest(unittest.TestCase):
    """
    Seçimi İNDEKS yapar.

    Saf metin sezgisi ("en uzun kelime") canlıda İKİ KEZ yanlış seçti:
    önce `dosyasını`, sonra `falan`. 134 bin dosyalık indeks varken tahmin
    etmek gereksiz — adayları sorup sonuç vereni seçiyoruz.
    """

    def test_indekste_eslesen_aday_secilir(self):
        # 'yedek' eşleşmiyor, 'staj' eşleşiyor → 'staj' seçilmeli
        def sahte_ara(sorgu, **kw):
            return [{'ad': 'staj.pdf'}] if sorgu == 'staj' else []
        with mock.patch("features.file_index.ara", side_effect=sahte_ara):
            self.assertEqual(_sorguyu_gevset("yedek staj dosyası"), "staj")

    def test_hicbiri_eslesmezse_ilk_aday_denenir(self):
        with mock.patch("features.file_index.ara", return_value=[]):
            secilen = _sorguyu_gevset("zzzqqq wwwyyy dosyası")
        self.assertIn(secilen, ("zzzqqq", "wwwyyy"))

    def test_indeks_cokerse_ilk_aday_donulur(self):
        with mock.patch("features.file_index.ara", side_effect=RuntimeError("db yok")):
            self.assertIsNotNone(_sorguyu_gevset("staj raporu dosyası"))

    def test_tek_kelimelik_sorgu_gevsetilemez(self):
        self.assertIsNone(_sorguyu_gevset("staj"))

    def test_bos_sorgu_cokmez(self):
        self.assertIsNone(_sorguyu_gevset(""))
        self.assertIsNone(_sorguyu_gevset(None))


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

    def test_hicbir_sonuc_yoksa_tam_ad_istenir(self):
        """Somut ve yapılabilir tek şey: dosyanın tam adı."""
        from core.recovery import KurtarmaSonucu
        kurtarma = KurtarmaSonucu(denendi=True, basarili=False, adimlar=["↳ denedim"])
        self.assertIn("tam yaz", kurtarma_raporu("bulunamadı", kurtarma))

    def test_sonuc_bulunduysa_cevaplanamaz_soru_sorulmaz(self):
        """
        CANLIDA YAKALANAN: kurtarma 9 dosya listeledikten sonra "Devam etmemi
        ister misin?" diye soruyordu. Kullanıcı "devam et" yazdı — sistemde onu
        karşılayan hiçbir şey yok, üstelik 9 sonuçtan hangisi olduğu da belirsiz.
        Liste zaten kendi yönergesini taşıyor ("1'i bana gönder").
        """
        from core.recovery import KurtarmaSonucu
        kurtarma = KurtarmaSonucu(denendi=True, basarili=False,
                                  mesaj="Bulunan dosyalar: 1. staj.pdf",
                                  adimlar=["↳ gevşettim ✅"])
        rapor = kurtarma_raporu("bulunamadı", kurtarma)
        self.assertIn("staj.pdf", rapor)
        self.assertNotIn("Devam etmemi", rapor)
        self.assertNotIn("tam yaz", rapor)

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


class TurkceGevsetmeTest(unittest.TestCase):
    """
    CANLIDA YAKALANAN HATA: kurtarma `dosyasını` diye arama yaptı.

    Zayıf kelime listesi ASCII ('dosyasini'), gerçek kelime Türkçe
    ('dosyasını' — noktasız ı). Eşleşmediği için gürültü kelime elenmedi ve
    "en uzun kelimeyi seç" kuralı onu seçti.
    """

    def test_turkce_gurultu_kelimesi_elenir(self):
        self.assertEqual(_sorguyu_gevset("staj raporu dosyasını bul"), "staj")

    def test_ascii_yazim_da_elenir(self):
        self.assertEqual(_sorguyu_gevset("staj raporu dosyasini bul"), "staj")

    def test_gurultu_kelimesi_asla_secilmez(self):
        """Gevşetilen sorgu bir gürültü kelimesi olamaz — arama anlamsızlaşır."""
        from core.recovery import _ZAYIF_TOKENLAR
        for cumle in ("ULTRON yedek spec dosyasını bul",
                      "maliyet tablosu dosyalarını göster",
                      "sunum belgesini bul"):
            secilen = _sorguyu_gevset(cumle)
            self.assertNotIn(secilen, _ZAYIF_TOKENLAR,
                             f"'{cumle}' → gürültü kelimesi seçildi: {secilen}")

    def test_uzun_gurultu_kisa_anlamliyi_ezmez(self):
        """'dosyasını' (9 harf) > 'staj' (4 harf) — uzunluk kuralı yanıltmamalı."""
        self.assertEqual(_sorguyu_gevset("staj dosyasını bul"), "staj")
