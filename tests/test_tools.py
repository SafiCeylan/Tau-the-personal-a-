# -*- coding: utf-8 -*-
"""
Araç Defteri (core/tools.py + core/builtin_tools.py) ve yürütme dağıtıcısı testleri.

NEDEN ÖNEMLİ: `ExecutionEngineLayer` eskiden ~260 satırlık bir if/elif zinciriydi
ve neredeyse hiç test edilmiyordu. Zincir araçlara bölünürken davranışın
değişmediğini garanti eden tek şey bu dosya.

En kritik davranış — ÜÇ DURUM:
    islendi=False               → akış LLM'e düşer (ctx.execution_result BOŞ kalır)
    islendi=True, basarili=False → aracın hata mesajı kullanıcıya döner
İkisi karıştırılırsa "dosya bulunamadı" cevabı LLM'e düşer ve Ultron uydurur.

⚠️ Güvenlik zırhı ZORUNLU: araçlar gerçek yürütücüleri çağırıyor.
"""

import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.context import UltronContext
from core.layers.pipeline_layers import ExecutionEngineLayer
from core.tools import (
    AracDefteri, Arac, AracSonuc, DEFTER, RISK_GUVENLI, RISK_ONAY, arac_kaydet,
)
import core.builtin_tools  # noqa: F401  — araçların kaydolması için


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


def _ctx(intent, metin="test", **alanlar):
    ctx = UltronContext(raw_input=metin)
    ctx.normalized_input = metin
    ctx.intent = intent
    for k, v in alanlar.items():
        setattr(ctx, k, v)
    return ctx


# =========================================================================
# AracSonuc — üç durum
# =========================================================================
class AracSonucTest(unittest.TestCase):

    def test_islenmedi_llm_e_dusmeyi_isaretler(self):
        s = AracSonuc.islenmedi()
        self.assertFalse(s.islendi)
        self.assertFalse(s.basarili)

    def test_hata_islenmis_ama_basarisizdir(self):
        """'Üstlenmedi' ile 'başarısız' karışırsa hata mesajı LLM'e düşer."""
        s = AracSonuc.hata("dosya bulunamadı")
        self.assertTrue(s.islendi)
        self.assertFalse(s.basarili)
        self.assertEqual(s.mesaj, "dosya bulunamadı")

    def test_ok_veriyi_tasir(self):
        s = AracSonuc.ok("oldu", screenshot_path="C:/a.png")
        self.assertTrue(s.islendi and s.basarili)
        self.assertEqual(s.veri, {"screenshot_path": "C:/a.png"})


# =========================================================================
# Defter
# =========================================================================
class AracDefteriTest(unittest.TestCase):

    def setUp(self):
        self.defter = AracDefteri()

    def _arac(self, ad, intentler=()):
        return Arac(ad=ad, aciklama="x", calistir=lambda **_: AracSonuc.ok("y"),
                    intentler=intentler)

    def test_ayni_ad_iki_kez_kaydedilemez(self):
        self.defter.kaydet(self._arac("a"))
        with self.assertRaises(ValueError):
            self.defter.kaydet(self._arac("a"))

    def test_intent_ile_araca_ulasilir(self):
        self.defter.kaydet(self._arac("a", ("WEATHER",)))
        self.assertEqual(self.defter.intent_ile("WEATHER").ad, "a")

    def test_bir_arac_birden_fazla_intente_baglanabilir(self):
        self.defter.kaydet(self._arac("a", ("SYSTEM_CONTROL", "PLAY_MUSIC")))
        self.assertEqual(self.defter.intent_ile("SYSTEM_CONTROL").ad, "a")
        self.assertEqual(self.defter.intent_ile("PLAY_MUSIC").ad, "a")

    def test_ilk_kaydedilen_intenti_kazanir(self):
        """Kayıt sırası eski if/elif sırasıyla aynı kalmalı."""
        self.defter.kaydet(self._arac("once", ("FILE_SEARCH",)))
        self.defter.kaydet(self._arac("sonra", ("FILE_SEARCH",)))
        self.assertEqual(self.defter.intent_ile("FILE_SEARCH").ad, "once")

    def test_bilinmeyen_intent_none_doner(self):
        self.assertIsNone(self.defter.intent_ile("YOK"))

    def test_planner_katalogu_ad_ve_aciklama_icerir(self):
        self.defter.kaydet(Arac(ad="dosya_ara", aciklama="Dosya arar",
                                calistir=lambda **_: AracSonuc.ok(""),
                                parametreler={"sorgu": "aranacak"}))
        katalog = self.defter.planner_katalogu()
        self.assertIn("dosya_ara", katalog)
        self.assertIn("sorgu", katalog)
        self.assertIn("Dosya arar", katalog)


# =========================================================================
# Yerleşik araçların kaydı
# =========================================================================
class YerlesikAraclarTest(unittest.TestCase):

    # pipeline_layers'daki intent listesinin tamamı karşılanmalı
    BEKLENEN_INTENTLER = [
        "PLAY_MUSIC", "MEDIA_CONTROL", "SYSTEM_CONTROL", "WEB_SEARCH", "WEATHER",
        "CURRENCY", "CREATE_REMINDER", "SCHEDULE_TASK", "WHATSAPP_MESSAGE",
        "EMAIL_MESSAGE", "FILE_TRANSFER", "FILE_INDEX", "FILE_SEARCH",
        "FILE_OPERATION", "SCREENSHOT", "CLIPBOARD", "FOCUS_MODE", "NOTE_TAKE",
        "TIMER", "CALCULATOR", "TIME_DATE", "MORNING_BRIEFING", "EVENING_REPORT",
        "ANALYSIS_REPORT", "GENERAL_CONVERSATION",
    ]

    def test_her_intentin_bir_araci_var(self):
        eksik = [i for i in self.BEKLENEN_INTENTLER if DEFTER.intent_ile(i) is None]
        self.assertEqual(eksik, [], f"araçsız kalan intent'ler: {eksik}")

    def test_mesajlasma_ve_dosya_gonderimi_onay_ister(self):
        """Bu araçlar sessizce çalışırsa istenmeyen mesaj gider."""
        for ad in ("whatsapp_yonet", "eposta_yonet", "dosya_gonder"):
            self.assertEqual(DEFTER.getir(ad).risk, RISK_ONAY, f"{ad} risksiz kalmış")

    def test_araclarin_hepsinin_aciklamasi_var(self):
        """Açıklama planner prompt'una giriyor — boş olamaz."""
        for arac in DEFTER.hepsi():
            self.assertTrue(arac.aciklama.strip(), f"{arac.ad} açıklamasız")


# =========================================================================
# Dağıtıcı — ExecutionEngineLayer
# =========================================================================
class DagiticiTest(unittest.TestCase):

    def setUp(self):
        self.katman = ExecutionEngineLayer()

    def test_guvenlik_kesintisi_araci_calistirmaz(self):
        ctx = _ctx("WEATHER", security_level="CONFIRM",
                   security_message="onay bekleniyor")
        with mock.patch.object(DEFTER, 'intent_ile') as sahte:
            sonuc = self.katman.process(ctx)
        sahte.assert_not_called()
        self.assertFalse(sonuc.execution_success)
        self.assertEqual(sonuc.execution_result, "onay bekleniyor")

    def test_araci_olmayan_intent_llm_e_duser(self):
        ctx = self.katman.process(_ctx("BOYLE_BIR_INTENT_YOK"))
        self.assertFalse(ctx.execution_success)
        self.assertIsNone(ctx.execution_result)

    def test_basarili_arac_sonucu_baglama_yazilir(self):
        ctx = _ctx("WEATHER")
        with mock.patch.object(DEFTER.getir("hava_durumu"), 'calistir',
                               return_value=AracSonuc.ok("22 derece")):
            sonuc = self.katman.process(ctx)
        self.assertTrue(sonuc.execution_success)
        self.assertEqual(sonuc.execution_result, "22 derece")

    def test_basarisiz_arac_mesaji_kullaniciya_doner(self):
        """Hata mesajı LLM'e DÜŞMEMELİ — yoksa Ultron uydurur."""
        ctx = _ctx("CALCULATOR")
        with mock.patch.object(DEFTER.getir("hesap_makinesi"), 'calistir',
                               return_value=AracSonuc.hata("geçersiz ifade")):
            sonuc = self.katman.process(ctx)
        self.assertTrue(sonuc.execution_success is False)
        self.assertEqual(sonuc.execution_result, "geçersiz ifade")

    def test_ustlenilmeyen_istek_llm_e_duser(self):
        ctx = _ctx("WEB_SEARCH")
        with mock.patch.object(DEFTER.getir("web_ara"), 'calistir',
                               return_value=AracSonuc.islenmedi()):
            sonuc = self.katman.process(ctx)
        self.assertFalse(sonuc.execution_success)
        self.assertIsNone(sonuc.execution_result)

    def test_arac_verisi_entities_e_aktarilir(self):
        ctx = _ctx("SCREENSHOT")
        with mock.patch.object(DEFTER.getir("ekran_goruntusu"), 'calistir',
                               return_value=AracSonuc.ok("alındı", screenshot_path="C:/x.png")):
            sonuc = self.katman.process(ctx)
        self.assertEqual(sonuc.entities.get("screenshot_path"), "C:/x.png")

    def test_ustlenilmese_bile_veri_aktarilir(self):
        """Pano 'ai' yolu: araç üstlenmez ama içerik LLM prompt'una girmeli."""
        ctx = _ctx("CLIPBOARD")
        with mock.patch.object(
            DEFTER.getir("pano_isle"), 'calistir',
            return_value=AracSonuc(islendi=False, veri={"pano_icerik": "metin",
                                                        "pano_gorev": "ozetle"}),
        ):
            sonuc = self.katman.process(ctx)
        self.assertFalse(sonuc.execution_success)
        self.assertEqual(sonuc.entities.get("pano_icerik"), "metin")
        self.assertEqual(sonuc.entities.get("pano_gorev"), "ozetle")

    def test_arac_cokerse_boru_hatti_durmaz(self):
        ctx = _ctx("CURRENCY")
        with mock.patch.object(DEFTER.getir("doviz"), 'calistir',
                               side_effect=RuntimeError("patladı")):
            sonuc = self.katman.process(ctx)   # istisna DIŞARI SIZMAMALI
        self.assertFalse(sonuc.execution_success)


# =========================================================================
# Parametre köprüsü — LLM/entity değerleri doğru araç argümanına gitmeli
# =========================================================================
class ArgumanKoprusuTest(unittest.TestCase):

    def _hazirla(self, ctx, arac_adi, db_cursor=None, db_conn=None):
        return ExecutionEngineLayer._argumanlari_hazirla(
            ctx, DEFTER.getir(arac_adi), db_cursor, db_conn)

    def test_ham_metin_her_zaman_gecer(self):
        arg = self._hazirla(_ctx("WEATHER", "hava nasıl"), "hava_durumu")
        self.assertEqual(arg["metin"], "hava nasıl")

    def test_db_isteyen_araca_baglanti_verilir(self):
        arg = self._hazirla(_ctx("NOTE_TAKE"), "not_yonet", db_cursor="C", db_conn="B")
        self.assertEqual(arg["db_cursor"], "C")
        self.assertEqual(arg["db_conn"], "B")

    def test_db_istemeyen_araca_baglanti_verilmez(self):
        arg = self._hazirla(_ctx("WEATHER"), "hava_durumu", db_cursor="C")
        self.assertNotIn("db_cursor", arg)

    def test_llm_sarki_adi_koprulenir(self):
        ctx = _ctx("PLAY_MUSIC", "bir şeyler çal", intent_source="llm",
                   llm_entities={"song_title": "motivasyon"})
        self.assertEqual(self._hazirla(ctx, "uygulama_calistir")["sarki"], "motivasyon")

    def test_regex_niyetinde_kanonik_komut_kurulmaz(self):
        """intent_source='regex' iken ham metin kullanılmalı (eski davranış)."""
        ctx = _ctx("PLAY_MUSIC", "motivasyon çal", intent_source="regex",
                   llm_entities={"song_title": "baska"})
        self.assertNotIn("sarki", self._hazirla(ctx, "uygulama_calistir"))

    def test_llm_varliklari_entities_i_ezer(self):
        ctx = _ctx("CALCULATOR", "2+2",
                   entities={"expression": "1+1"},
                   llm_entities={"expression": "9+9"})
        self.assertEqual(self._hazirla(ctx, "hesap_makinesi")["ifade"], "9+9")

    def test_dosya_gonderiminde_kanal_ayrimi_korunur(self):
        """Kanal geçmezse telefondaki '2'yi gönder' masaüstü sonucunu gönderir."""
        ctx = _ctx("FILE_TRANSFER", "staj raporunu gönder", kanal="12345")
        self.assertEqual(self._hazirla(ctx, "dosya_gonder")["kanal"], "12345")

    def test_sayac_dakikasi_koprulenir(self):
        ctx = _ctx("TIMER", "sayaç kur", entities={"timer_minutes": 10})
        self.assertEqual(self._hazirla(ctx, "sayac")["dakika"], 10)

    def test_web_arama_sorgusu_koprulenir(self):
        ctx = _ctx("WEB_SEARCH", "ara", entities={"search_query": "python 3.13"})
        self.assertEqual(self._hazirla(ctx, "web_ara")["sorgu"], "python 3.13")

    def test_dosya_yolu_koprulenir(self):
        ctx = _ctx("FILE_OPERATION", "oku", entities={"file_path": "C:/a.txt"})
        self.assertEqual(self._hazirla(ctx, "dosya_oku")["yol"], "C:/a.txt")


# =========================================================================
# Araç davranışları — gerçek fonksiyonlar (zırh altında)
# =========================================================================
class AracDavranisTest(unittest.TestCase):

    def test_hesap_makinesi_gercekten_hesaplar(self):
        sonuc = DEFTER.getir("hesap_makinesi").calistir(metin="2 kere 21 kaç eder")
        self.assertTrue(sonuc.islendi)
        self.assertIn("42", sonuc.mesaj)

    def test_hesap_makinesi_bozuk_ifadede_hata_doner_llm_e_dusmez(self):
        sonuc = DEFTER.getir("hesap_makinesi").calistir(metin="2 +* /", ifade="2 +* /")
        self.assertTrue(sonuc.islendi, "bozuk ifade LLM'e düşerse Ultron sayı uydurur")
        self.assertFalse(sonuc.basarili)

    def test_saat_tarih_sistemden_okur(self):
        sonuc = DEFTER.getir("saat_tarih").calistir(metin="saat kaç")
        self.assertTrue(sonuc.islendi and sonuc.basarili)

    def test_odak_modu_varsayilan_25_dakika(self):
        sonuc = DEFTER.getir("odak_modu").calistir(metin="odak modu başlat")
        self.assertEqual(sonuc.veri["focus_action"], "start")
        self.assertEqual(sonuc.veri["focus_minutes"], 25)

    def test_odak_modu_sureyi_metinden_okur(self):
        sonuc = DEFTER.getir("odak_modu").calistir(metin="45 dakika odaklan")
        self.assertEqual(sonuc.veri["focus_minutes"], 45)

    def test_odak_modu_iptali_taninir(self):
        sonuc = DEFTER.getir("odak_modu").calistir(metin="odak modunu iptal et")
        self.assertEqual(sonuc.veri["focus_action"], "cancel")

    def test_db_siz_cagrilan_db_araci_cokmez(self):
        """Telegram/zamanlanmış görev yolunda cursor gelmeyebilir."""
        for ad in ("not_yonet", "sayac", "gorev_zamanla", "hatirlatma_kur"):
            sonuc = DEFTER.getir(ad).calistir(metin="bir şey", db_cursor=None, db_conn=None)
            self.assertFalse(sonuc.islendi, f"{ad} db'siz üstlenmemeli")


if __name__ == '__main__':
    unittest.main()
