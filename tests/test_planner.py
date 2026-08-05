# -*- coding: utf-8 -*-
"""
Planner + Plan Yürütücü testleri (Faz 1).

LLM ÇAĞRILMAZ. Planner'ın LLM'den bağımsız tasarlanmasının bütün amacı buydu:
veri modeli ve doğrulama, model çıktısı olmadan test edilebilir olmalı.

En kritik iki davranış:
  1. LLM çıktısına ASLA doğrudan güvenilmez — uydurma araç/parametre elenir
     ve elenen şey `uyarilar`a yazılır (sessizce yutulmaz).
  2. Riskli adım (WhatsApp/mail/dosya gönderimi) onaysız YÜRÜTÜLMEZ.
"""

import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.planner import (
    ATLANDI, BASARISIZ, BITTI, ONAY_BEKLIYOR, MAKS_GOREV,
    Gorev, Plan, cok_adimli_olabilir, istem_kur, plan_semasi, plani_dogrula,
    plan_uret,
)
from core.plan_executor import PlanYurutucu
from core.tools import DEFTER, AracSonuc
import core.builtin_tools  # noqa: F401


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


# =========================================================================
# Şema
# =========================================================================
class SemaTest(unittest.TestCase):

    def test_eylem_sadece_kayitli_araclardan_secilebilir(self):
        """enum, modelin araç adı uydurmasını kaynağında engeller."""
        sema = plan_semasi()
        enum = sema["properties"]["gorevler"]["items"]["properties"]["eylem"]["enum"]
        self.assertIn("dosya_ara", enum)
        self.assertEqual(sorted(enum), sorted(DEFTER.adlar()))

    def test_istem_arac_katalogunu_icerir(self):
        istem = istem_kur("staj raporunu bul")
        self.assertIn("dosya_ara", istem)
        self.assertIn("staj raporunu bul", istem)


# =========================================================================
# Doğrulama — LLM çıktısı temizleme
# =========================================================================
class DogrulamaTest(unittest.TestCase):

    def test_gecerli_plan_gorevlere_cevrilir(self):
        plan = plani_dogrula({
            "hedef": "staj raporu",
            "gorevler": [{"id": 1, "eylem": "dosya_ara",
                          "parametreler": {"sorgu": "staj raporu"}}],
        })
        self.assertEqual(len(plan.gorevler), 1)
        self.assertEqual(plan.gorevler[0].eylem, "dosya_ara")
        self.assertEqual(plan.gorevler[0].parametreler, {"sorgu": "staj raporu"})

    def test_uydurma_arac_elenir_ve_uyari_birakir(self):
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [{"id": 1, "eylem": "roketi_firlat"}],
        })
        self.assertEqual(plan.gorevler, [])
        self.assertTrue(any("roketi_firlat" in u for u in plan.uyarilar))

    def test_uydurma_parametre_suzulur(self):
        """Test edildi: model dosya_gonder'e olmayan 'alan' parametresi ekledi."""
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [{"id": 1, "eylem": "dosya_gonder",
                          "parametreler": {"metin": "rapor", "alan": "annem"}}],
        })
        self.assertEqual(plan.gorevler[0].parametreler, {"metin": "rapor"})
        self.assertTrue(any("alan" in u for u in plan.uyarilar))

    def test_id_ler_modele_birakilmaz(self):
        """Model id atlayabilir/çakıştırabilir — sıra numarası kullanılır."""
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [{"id": 7, "eylem": "hava_durumu"},
                         {"id": 7, "eylem": "doviz"}],
        })
        self.assertEqual([g.id for g in plan.gorevler], [1, 2])

    def test_ileriye_referansli_kosul_reddedilir(self):
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [
                {"id": 1, "eylem": "hava_durumu",
                 "kosul": {"tip": "basarili_ise", "gorev_id": 2}},
                {"id": 2, "eylem": "doviz"},
            ],
        })
        self.assertIsNone(plan.gorevler[0].kosul)
        self.assertTrue(any("koşul" in u for u in plan.uyarilar))

    def test_bilinmeyen_kosul_tipi_reddedilir(self):
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [
                {"id": 1, "eylem": "hava_durumu"},
                {"id": 2, "eylem": "doviz",
                 "kosul": {"tip": "her_ihtimale_karsi", "gorev_id": 1}},
            ],
        })
        self.assertIsNone(plan.gorevler[1].kosul)

    def test_gecerli_kosul_korunur(self):
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [
                {"id": 1, "eylem": "dosya_ara"},
                {"id": 2, "eylem": "indeks_yonet",
                 "kosul": {"tip": "basarisiz_ise", "gorev_id": 1}},
            ],
        })
        self.assertEqual(plan.gorevler[1].kosul["tip"], "basarisiz_ise")

    def test_asiri_uzun_plan_kesilir(self):
        plan = plani_dogrula({
            "hedef": "x",
            "gorevler": [{"id": i, "eylem": "doviz"} for i in range(20)],
        })
        self.assertEqual(len(plan.gorevler), MAKS_GOREV)
        self.assertTrue(any("adım" in u for u in plan.uyarilar))

    def test_bos_cikti_cokmez(self):
        plan = plani_dogrula({})
        self.assertEqual(plan.gorevler, [])
        self.assertTrue(plan.uyarilar)


# =========================================================================
# Planner kapısı — gecikme koruması
# =========================================================================
class KapiTest(unittest.TestCase):

    def test_tek_adimli_komut_planlanmaz(self):
        """25 saniyelik planner 'chrome aç' için çalışmamalı."""
        for komut in ["chrome aç", "saat kaç", "sesi kıs", "hava nasıl"]:
            self.assertFalse(cok_adimli_olabilir(komut), komut)

    def test_siralama_ifadesi_planlamayi_tetikler(self):
        for komut in ["staj raporunu bul sonra anneme gönder",
                      "dosyayı ara bulamazsan indeksi güncelle",
                      "önce hava durumuna bak, sonra not al"]:
            self.assertTrue(cok_adimli_olabilir(komut), komut)

    def test_bos_metin_cokmez(self):
        self.assertFalse(cok_adimli_olabilir(""))
        self.assertFalse(cok_adimli_olabilir(None))


# =========================================================================
# Üretim — sağlayıcı kapısı
# =========================================================================
class UretimTest(unittest.TestCase):

    def test_ollama_disinda_planner_calismaz(self):
        """Şema zorlaması yoksa bozuk JSON riski var — planner devre dışı."""
        plan, hata = plan_uret("bul ve gönder", {"ai_provider": "gemini"})
        self.assertIsNone(plan)
        self.assertIn("Ollama", hata)

    def test_llm_hatasi_yukari_tasinir(self):
        with mock.patch("features.ollama.ollama_json",
                        return_value=(None, "Ollama'ya bağlanılamadı")):
            plan, hata = plan_uret("bul ve gönder", {"ai_provider": "ollama"})
        self.assertIsNone(plan)
        self.assertIn("bağlanılamadı", hata)

    def test_ham_cikti_dogrulamadan_gecer(self):
        ham = {"hedef": "test", "gorevler": [{"id": 1, "eylem": "roketi_firlat"}]}
        with mock.patch("features.ollama.ollama_json", return_value=(ham, None)):
            plan, hata = plan_uret("bir şey yap", {"ai_provider": "ollama"})
        self.assertIsNone(hata)
        self.assertEqual(plan.gorevler, [])   # uydurma araç elendi


# =========================================================================
# Yürütücü
# =========================================================================
class YurutucuTest(unittest.TestCase):

    def _plan(self, *gorevler):
        return Plan(hedef="test", gorevler=list(gorevler))

    def test_gorevler_sirayla_calisir(self):
        plan = self._plan(Gorev(1, "hava_durumu"), Gorev(2, "doviz"))
        cagrilar = []
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               side_effect=lambda **_: (cagrilar.append("hava"), AracSonuc.ok("22"))[1]), \
             mock.patch.object(DEFTER.getir("doviz"), 'calistir',
                               side_effect=lambda **_: (cagrilar.append("doviz"), AracSonuc.ok("35"))[1]):
            sonuc = PlanYurutucu().calistir(plan)
        self.assertEqual(cagrilar, ["hava", "doviz"])
        self.assertTrue(sonuc.basarili)

    def test_basarisizlik_kosulu_tetiklenir(self):
        plan = self._plan(
            Gorev(1, "dosya_ara"),
            Gorev(2, "indeks_yonet", kosul={"tip": "basarisiz_ise", "gorev_id": 1}),
        )
        with mock.patch.object(DEFTER.getir("dosya_ara"), 'calistir',
                               return_value=AracSonuc.hata("bulunamadı")), \
             mock.patch.object(DEFTER.getir("indeks_yonet"), 'calistir',
                               return_value=AracSonuc.ok("indeks güncellendi")) as indeks:
            sonuc = PlanYurutucu().calistir(plan)
        indeks.assert_called_once()
        self.assertEqual(plan.gorevler[1].durum, BITTI)
        self.assertFalse(sonuc.basarili)

    def test_tutmayan_kosul_adimi_atlar(self):
        plan = self._plan(
            Gorev(1, "dosya_ara"),
            Gorev(2, "indeks_yonet", kosul={"tip": "basarisiz_ise", "gorev_id": 1}),
        )
        with mock.patch.object(DEFTER.getir("dosya_ara"), 'calistir',
                               return_value=AracSonuc.ok("bulundu")), \
             mock.patch.object(DEFTER.getir("indeks_yonet"), 'calistir') as indeks:
            sonuc = PlanYurutucu().calistir(plan)
        indeks.assert_not_called()
        self.assertEqual(plan.gorevler[1].durum, ATLANDI)
        self.assertTrue(sonuc.basarili, "atlanan adım planı başarısız yapmamalı")

    def test_riskli_adim_onaysiz_calismaz(self):
        """En kritik test: onaysız mesaj/dosya gönderilmemeli."""
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir') as gonder:
            sonuc = PlanYurutucu().calistir(plan)
        gonder.assert_not_called()
        self.assertEqual(plan.gorevler[0].durum, ONAY_BEKLIYOR)
        self.assertIsNotNone(sonuc.onay_bekleyen)
        self.assertFalse(sonuc.basarili)

    def test_guvenli_arac_riskli_cumleyle_onay_ister(self):
        """
        Motor, çok adımlı cümlede tek intent'in onay kartını atlayıp kararı
        yürütücüye bırakıyor. `uygulama_calistir` RISK_GUVENLI etiketli ama
        "chrome'u kapat" güvenlik katmanında CONFIRM 75. Aracın etiketine
        bakmak, o komutu onaysız çalıştırmaktı.
        """
        plan = self._plan(Gorev(1, "uygulama_calistir", {"metin": "chrome kapat"}))
        with mock.patch.object(DEFTER.getir("uygulama_calistir"), 'calistir') as calistir:
            sonuc = PlanYurutucu().calistir(plan)
        calistir.assert_not_called()
        self.assertEqual(plan.gorevler[0].durum, ONAY_BEKLIYOR)
        self.assertIsNotNone(sonuc.onay_bekleyen)

    def test_zararsiz_adim_onay_istemez(self):
        """Güvenlik kontrolü her adımı beklemeye almamalı — akış kilitlenmesin."""
        plan = self._plan(Gorev(1, "uygulama_calistir", {"metin": "chrome aç"}))
        with mock.patch.object(DEFTER.getir("uygulama_calistir"), 'calistir',
                               return_value=AracSonuc.ok("açıldı")) as calistir:
            sonuc = PlanYurutucu().calistir(plan)
        calistir.assert_called_once()
        self.assertTrue(sonuc.basarili)

    def test_yasakli_adim_onaylansa_da_calismaz(self):
        """FORBIDDEN onaylanabilir bir şey değildir — adım düşer."""
        plan = self._plan(Gorev(1, "uygulama_calistir", {"metin": "bilgisayarı kapat"}))
        with mock.patch.object(DEFTER.getir("uygulama_calistir"), 'calistir') as calistir:
            sonuc = PlanYurutucu(onaylanan_gorevler={1}).calistir(plan)
        calistir.assert_not_called()
        self.assertEqual(plan.gorevler[0].durum, BASARISIZ)
        self.assertIsNone(sonuc.onay_bekleyen)

    def test_onay_verilince_calisir(self):
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir',
                               return_value=AracSonuc.ok("gönderildi")) as gonder:
            sonuc = PlanYurutucu(onaylanan_gorevler={1}).calistir(plan)
        gonder.assert_called_once()
        self.assertTrue(sonuc.basarili)

    def test_onay_beklerken_sonraki_adimlar_calismaz(self):
        """Sonraki adım, onaylanmamış adımın çıktısına dayanıyor olabilir."""
        plan = self._plan(Gorev(1, "dosya_gonder"), Gorev(2, "doviz"))
        with mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir'), \
             mock.patch.object(DEFTER.getir("doviz"), 'calistir') as doviz:
            PlanYurutucu().calistir(plan)
        doviz.assert_not_called()

    def test_arac_cokerse_plan_durmaz(self):
        plan = self._plan(Gorev(1, "hava_durumu"), Gorev(2, "doviz"))
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               side_effect=RuntimeError("patladı")), \
             mock.patch.object(DEFTER.getir("doviz"), 'calistir',
                               return_value=AracSonuc.ok("35")) as doviz:
            sonuc = PlanYurutucu().calistir(plan)
        doviz.assert_called_once()
        self.assertEqual(plan.gorevler[0].durum, BASARISIZ)

    def test_db_isteyen_araca_baglanti_gecer(self):
        plan = self._plan(Gorev(1, "not_yonet", {"icerik": "test"}))
        with mock.patch.object(DEFTER.getir("not_yonet"), 'calistir',
                               return_value=AracSonuc.ok("eklendi")) as arac:
            PlanYurutucu(db_cursor="C", db_conn="B").calistir(plan)
        self.assertEqual(arac.call_args.kwargs["db_cursor"], "C")

    def test_dosya_gonderiminde_kanal_gecer(self):
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir',
                               return_value=AracSonuc.ok("gitti")) as arac:
            PlanYurutucu(kanal="12345", onaylanan_gorevler={1}).calistir(plan)
        self.assertEqual(arac.call_args.kwargs["kanal"], "12345")

    def test_arac_verisi_toplanir(self):
        plan = self._plan(Gorev(1, "ekran_goruntusu"))
        with mock.patch.object(DEFTER.getir("ekran_goruntusu"), 'calistir',
                               return_value=AracSonuc.ok("alındı", screenshot_path="C:/a.png")):
            sonuc = PlanYurutucu().calistir(plan)
        self.assertEqual(sonuc.veri["screenshot_path"], "C:/a.png")

    def test_bos_plan_basarili_sayilmaz(self):
        sonuc = PlanYurutucu().calistir(Plan(hedef="bos"))
        self.assertFalse(sonuc.basarili)


if __name__ == '__main__':
    unittest.main()


# =========================================================================
# Motor entegrasyonu — planner kapısı ve onay akışı
# =========================================================================
class MotorPlannerTest(unittest.TestCase):
    """
    LLM çağrılmaz: plan_uret sahtelenir. Test edilen şey planner'ın NE ZAMAN
    devreye girdiği ve onay akışının doğru işlediğidir.
    """

    def setUp(self):
        from core.engine import UltronCoreEngine
        self.motor = UltronCoreEngine(config={"ai_provider": "ollama"})

    def _plan(self, *gorevler):
        return Plan(hedef="test", gorevler=list(gorevler))

    def test_tek_adimli_komutta_planner_cagrilmaz(self):
        """En pahalı hata: 'saat kaç' için 25 saniye plan beklemek."""
        with mock.patch("core.engine.plan_uret") as uret:
            self.motor.process("saat kaç", allow_llm=False)
        uret.assert_not_called()

    def test_tek_komut_deterministik_yoldan_gider(self):
        """
        Sıralama ifadesi yoksa planner görülmez; komut eski hızlı yoldan
        cevaplanır. ("Deterministik önce" kuralı korunuyor.)
        """
        with mock.patch("core.engine.plan_uret") as uret, \
             mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22 derece")):
            ctx = self.motor.process("hava durumu nasıl", allow_llm=False)
        self.assertTrue(ctx.execution_success)
        uret.assert_not_called()

    def test_cok_adimli_cumlede_tek_intent_kazanamaz(self):
        """
        CANLI TESTTE YAKALANAN HATA: "önce hava durumuna bak, sonra dövizi
        söyle, en son not al" cümlesini regex NOTE_TAKE sanıp içeriği "al" olan
        saçma bir not kaydediyordu. Planner yürütmeden ÖNCE devreye girmeli.
        """
        plan = self._plan(Gorev(1, "hava_durumu"), Gorev(2, "doviz"))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)) as uret, \
             mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22 derece")), \
             mock.patch.object(DEFTER.getir("doviz"), 'calistir',
                               return_value=AracSonuc.ok("35 TL")), \
             mock.patch.object(DEFTER.getir("not_yonet"), 'calistir') as notlar:
            ctx = self.motor.process(
                "önce hava durumuna bak, sonra dövizi söyle, en son not al",
                allow_llm=False)
        uret.assert_called_once()
        notlar.assert_not_called()          # saçma not KAYDEDİLMEMELİ
        self.assertIn("22 derece", ctx.execution_result)
        self.assertIn("35 TL", ctx.execution_result)

    def test_plan_uretilemezse_normal_yurutmeye_dusulur(self):
        """Ollama kapalıysa Ultron çalışmaya devam etmeli."""
        with mock.patch("core.engine.plan_uret", return_value=(None, "Ollama kapalı")), \
             mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22 derece")) as hava:
            ctx = self.motor.process("hava durumuna bak sonra söyle", allow_llm=False)
        hava.assert_called_once()           # eski yol devrede
        self.assertTrue(ctx.execution_success)

    def test_cok_adimli_komut_planlanir(self):
        """Hiçbir intent tutmayan, sıralama içeren cümle planner'a düşer."""
        plan = self._plan(Gorev(1, "hava_durumu"))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)) as uret, \
             mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22 derece")):
            ctx = self.motor.process("önce şunu hallet sonra bunu hallet", allow_llm=False)
        uret.assert_called_once()
        self.assertTrue(ctx.execution_success)
        self.assertIn("22 derece", ctx.execution_result)

    def test_planner_hatasi_akisi_bozmaz(self):
        with mock.patch("core.engine.plan_uret", return_value=(None, "Ollama kapalı")):
            ctx = self.motor.process("bunu yap sonra şunu yap", allow_llm=False)
        self.assertFalse(ctx.execution_success)   # cevabı LLM üretecek

    def test_riskli_adim_once_onay_ister(self):
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir') as gonder:
            ctx = self.motor.process("raporu bul sonra anneme gönder", allow_llm=False)
        gonder.assert_not_called()
        self.assertIn("Onay gerekiyor", ctx.execution_result)
        self.assertIn("desktop", self.motor.bekleyen_planlar)

    def test_evet_deyince_plan_devam_eder(self):
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir',
                               return_value=AracSonuc.ok("gönderildi")) as gonder:
            self.motor.process("raporu bul sonra anneme gönder", allow_llm=False)
            gonder.assert_not_called()
            ctx = self.motor.process("evet", allow_llm=False)
        gonder.assert_called_once()
        self.assertIn("gönderildi", ctx.execution_result)
        self.assertNotIn("desktop", self.motor.bekleyen_planlar)

    def test_izin_veriyorum_deyince_plan_devam_eder(self):
        """Kullanıcının 'izin veriyorum' yanıtı plan onayını çözmeli."""
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir',
                               return_value=AracSonuc.ok("gönderildi")) as gonder:
            self.motor.process("raporu bul sonra anneme gönder", allow_llm=False)
            gonder.assert_not_called()
            ctx = self.motor.process("izin veriyorum", allow_llm=False)
        gonder.assert_called_once()
        self.assertIn("gönderildi", ctx.execution_result)
        self.assertNotIn("desktop", self.motor.bekleyen_planlar)

    def test_hayir_deyince_plan_iptal(self):
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir') as gonder:
            self.motor.process("raporu bul sonra anneme gönder", allow_llm=False)
            ctx = self.motor.process("iptal", allow_llm=False)
        gonder.assert_not_called()
        self.assertIn("iptal", ctx.execution_result.lower())
        self.assertNotIn("desktop", self.motor.bekleyen_planlar)

    def test_konu_degisince_plan_dusurulur(self):
        """Üç mesaj sonra gelen 'evet' eski planı tetiklememeli."""
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir') as gonder:
            self.motor.process("raporu bul sonra anneme gönder", allow_llm=False)
            self.motor.process("saat kaç", allow_llm=False)      # konu değişti
            self.motor.process("evet", allow_llm=False)          # geç kalan onay
        gonder.assert_not_called()
        self.assertNotIn("desktop", self.motor.bekleyen_planlar)

    def test_onay_baska_kanaldan_verilemez(self):
        """Telefondan başlatılan planın onayı masaüstünde verilmemeli."""
        plan = self._plan(Gorev(1, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir') as gonder:
            self.motor.process("raporu bul sonra gönder", allow_llm=False, kanal="12345")
            self.motor.process("evet", allow_llm=False, kanal="desktop")
        gonder.assert_not_called()
        self.assertIn("12345", self.motor.bekleyen_planlar)

    def test_devam_ederken_tamamlanan_adim_tekrar_calismaz(self):
        """Onaydan önceki adımların yan etkisi ikinci kez olmamalı."""
        plan = self._plan(Gorev(1, "hava_durumu"),
                          Gorev(2, "dosya_gonder", {"metin": "rapor"}))
        with mock.patch("core.engine.plan_uret", return_value=(plan, None)), \
             mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22")) as hava, \
             mock.patch.object(DEFTER.getir("dosya_gonder"), 'calistir',
                               return_value=AracSonuc.ok("gitti")):
            self.motor.process("havaya bak sonra raporu gönder", allow_llm=False)
            self.assertEqual(hava.call_count, 1)
            self.motor.process("evet", allow_llm=False)
        self.assertEqual(hava.call_count, 1, "tamamlanan adım onaydan sonra tekrar çalıştı")

    def test_eylem_baglaclari_ve_numarali_adimlari_yakalar(self):
        """'zen aç ve youtube yaz' gibi bağlaçlı veya '1. x 2. y' gibi numaralı cümleler planlamaya girmeli."""
        self.assertTrue(cok_adimli_olabilir("zen aç ve youtube yaz"))
        self.assertTrue(cok_adimli_olabilir("ekranı oku ve 1'e tıkla"))
        self.assertTrue(cok_adimli_olabilir("1. chrome aç 2. youtube gir"))
        self.assertTrue(cok_adimli_olabilir("hava durumuna bak, sonra not al"))
        # Sıradan selamlaşma veya tek eylem girmemeli
        self.assertFalse(cok_adimli_olabilir("iyi günler, nasılsın"))
        self.assertFalse(cok_adimli_olabilir("chrome aç"))
