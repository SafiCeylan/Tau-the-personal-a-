# -*- coding: utf-8 -*-
"""
AJAN ÇEKİRDEĞİ (Faz 1) — core/ajan.py + features/ajan_saglayici.py

Model taklit edilir (betikli sağlayıcı): sınanan şey DÖNGÜNÜN kuralları —
güvenlik kapısı, onay devri, yedeğe düşme, adım tavanı, motor bağlantısı —
ve iki gerçek sağlayıcının istek/yanıt biçimi (ağsız).

Projenin dersi burada da geçerli: "fonksiyon çalışıyor" ile "cümle oraya
gidiyor" ayrı iddialardır → MotorBaglantisiTest ikincisini sınar.
"""
import sqlite3
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt5 import QtWebEngineWidgets  # noqa: F401  — QApplication'dan ÖNCE (bkz. conftest.py)
from PyQt5.QtWidgets import QApplication

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


app = QApplication.instance() or QApplication(sys.argv)

import core.builtin_tools  # noqa: E402,F401  — defteri doldurur
from core import ajan as ajan_mod  # noqa: E402
from core.ajan import Ajan, arac_semalari, bekleyen_araci_yurut  # noqa: E402
from core.tools import DEFTER, AracSonuc  # noqa: E402
from features import ajan_saglayici as sg  # noqa: E402
from features.ajan_saglayici import Adim, Cagri, SaglayiciHatasi  # noqa: E402


class BetikliSaglayici:
    """Sırayla önceden yazılmış Adim'ları döndüren sahte model."""
    ad = "yerel"
    etiket = "test · betik"

    def __init__(self, adimlar, hata=None):
        self.adimlar = list(adimlar)
        self.hata = hata
        self.gelen_sonuclar = []
        self.gorulen_araclar = None
        self.baslangic = None

    def baslat(self, sistem, gecmis, kullanici, baglam=""):
        self.baslangic = (sistem, gecmis, kullanici)
        self.baglam = baglam
        self.eklenen_kullanici = []

    def kullanici_ekle(self, metin):
        self.eklenen_kullanici.append(metin)

    def uret(self, araclar):
        self.gorulen_araclar = [a['ad'] for a in araclar]
        if self.hata:
            raise self.hata
        return self.adimlar.pop(0) if self.adimlar else Adim(metin="bitti")

    def sonuclari_ekle(self, sonuclar):
        self.gelen_sonuclar.append([(c.ad, m, h) for c, m, h in sonuclar])


def cagri(ad, metin, **ek):
    return Cagri(id=f"c_{ad}", ad=ad, girdi={"metin": metin, **ek})


class _AracYamasi:
    """Defterdeki bir aracın fonksiyonunu geçici olarak taklitle değiştirir."""

    def __init__(self, ad, sonuc):
        self.arac = DEFTER.getir(ad)
        self.sahte = MagicMock(return_value=sonuc)

    def __enter__(self):
        self.eski = self.arac.calistir
        self.arac.calistir = self.sahte
        return self.sahte

    def __exit__(self, *a):
        self.arac.calistir = self.eski


# =========================================================================
class SemaTest(unittest.TestCase):

    def test_her_arac_metin_ister_ve_sira_sabittir(self):
        s1, s2 = arac_semalari(), arac_semalari()
        self.assertEqual([a['ad'] for a in s1], [a['ad'] for a in s2])
        for a in s1:
            self.assertIn('metin', a['sema']['properties'], a['ad'])
            self.assertEqual(a['sema']['required'], ['metin'])
            self.assertNotIn('kanal', a['sema']['properties'])

    def test_sohbet_ve_ogrenme_araclari_ajana_verilmez(self):
        adlar = {a['ad'] for a in arac_semalari()}
        self.assertNotIn('ogrenilmis_cevap', adlar)
        self.assertNotIn('ogrenme_raporu', adlar)
        self.assertIn('uygulama_calistir', adlar)

    def test_buluta_ekran_pano_dosya_icerigi_verilmez(self):
        bulut = {a['ad'] for a in arac_semalari(bulut=True)}
        yerel = {a['ad'] for a in arac_semalari(bulut=False)}
        for ad in ('ekrani_oku', 'pano_isle', 'dosya_oku'):
            self.assertIn(ad, yerel)
            self.assertNotIn(ad, bulut)


# =========================================================================
class DonguTest(unittest.TestCase):

    def test_arac_cagrilir_sonuc_modele_doner_ve_cevap_gelir(self):
        model = BetikliSaglayici([
            Adim(cagrilar=[cagri('hava_durumu', 'hava nasıl')]),
            Adim(metin="İstanbul'da hava güneşli."),
        ])
        with _AracYamasi('hava_durumu', AracSonuc.ok("güneşli 21°C")) as hava:
            sonuc = Ajan(model).calistir("dışarısı nasıl")
        hava.assert_called_once()
        self.assertEqual(model.gelen_sonuclar, [[('hava_durumu', 'güneşli 21°C', False)]])
        self.assertEqual(sonuc.metin, "İstanbul'da hava güneşli.")
        self.assertEqual(sonuc.son_arac, 'hava_durumu')
        self.assertEqual(sonuc.adimlar[0]['durum'], 'ok')

    def test_cok_adim_sirayla(self):
        model = BetikliSaglayici([
            Adim(cagrilar=[cagri('hava_durumu', 'hava')]),
            Adim(cagrilar=[cagri('doviz', 'dolar kaç')]),
            Adim(metin="tamam"),
        ])
        with _AracYamasi('hava_durumu', AracSonuc.ok("güneşli")), \
                _AracYamasi('doviz', AracSonuc.ok("40 TL")):
            sonuc = Ajan(model).calistir("önce hava sonra dolar")
        self.assertEqual([a['arac'] for a in sonuc.adimlar], ['hava_durumu', 'doviz'])

    def test_bilinmeyen_arac_hata_olarak_geri_bildirilir(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('rm_rf', 'her şeyi sil')]),
                                  Adim(metin="yapamadım")])
        sonuc = Ajan(model).calistir("x")
        self.assertTrue(model.gelen_sonuclar[0][0][2], "hata bayrağı yok")
        self.assertIn("araç yok", model.gelen_sonuclar[0][0][1])
        self.assertEqual(sonuc.metin, "yapamadım")

    def test_basarisiz_arac_modelden_gizlenmez(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('hava_durumu', 'hava')]),
                                  Adim(metin="ulaşamadım")])
        with _AracYamasi('hava_durumu', AracSonuc.hata("servis yok")):
            Ajan(model).calistir("hava")
        ad, metin, hata = model.gelen_sonuclar[0][0]
        self.assertTrue(hata)
        self.assertIn("BAŞARISIZ", metin)

    def test_bos_metinli_cagri_calistirilmaz(self):
        model = BetikliSaglayici([Adim(cagrilar=[Cagri(id='1', ad='hava_durumu', girdi={})]),
                                  Adim(metin="?")])
        with _AracYamasi('hava_durumu', AracSonuc.ok("x")) as hava:
            Ajan(model).calistir("hava")
        hava.assert_not_called()

    def test_adim_tavani(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('hava_durumu', 'hava')])] * 10)
        with _AracYamasi('hava_durumu', AracSonuc.ok("güneşli")) as hava:
            sonuc = Ajan(model, {'ajan_max_adim': 3}).calistir("sonsuz")
        self.assertEqual(hava.call_count, 3)
        self.assertIn("adım sınırına", sonuc.metin)

    def test_saat_ve_hafiza_BAGLAMDA_kullanici_cumlesi_yalin_sistem_sabit(self):
        """15 Eki ölçümü: bağlam kullanıcı cümlesinin önüne eklenince küçük model
        komutu görmeyi bıraktı. Cümle yalın gitmeli, bağlam ayrı."""
        model = BetikliSaglayici([Adim(metin="selam")])
        Ajan(model).calistir("merhaba", hafiza=["kedinin adı Pamuk"])
        sistem, _g, mesaj = model.baslangic
        self.assertEqual(sistem, ajan_mod.SISTEM_TALIMATI)
        self.assertEqual(mesaj, "merhaba")
        self.assertIn("Pamuk", model.baglam)
        self.assertIn("Şu an", model.baglam)

    def test_aracsiz_eylem_iddiasi_bir_kez_duzeltilir(self):
        """Ölçüm: "Tab+1 bas" → model araç çağırmadan "basıldı" dedi."""
        model = BetikliSaglayici([
            Adim(metin="Tab+1 tuş kombinasyonu basıldı."),
            Adim(cagrilar=[cagri('klavye_tusu', 'tab+1')]),
            Adim(metin="Tab+1'e bastım."),
        ])
        with _AracYamasi('klavye_tusu', AracSonuc.ok("tuş gönderildi")) as tus:
            sonuc = Ajan(model).calistir("Tab+1 bas")
        tus.assert_called_once()
        self.assertEqual(len(model.eklenen_kullanici), 1)
        self.assertIn("basıldı", model.eklenen_kullanici[0])
        self.assertNotIn("Dikkat", sonuc.metin)

    def test_duzeltmeden_sonra_da_iddia_ederse_uyari_eklenir(self):
        model = BetikliSaglayici([Adim(metin="Mesajı gönderdim."),
                                  Adim(metin="Evet gönderildi.")])
        sonuc = Ajan(model).calistir("anneme yaz")
        self.assertIn("hiçbir işlem çalıştırılmadı", sonuc.metin)

    def test_arac_calistiysa_iddia_serbesttir(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('hava_durumu', 'hava')]),
                                  Adim(metin="Hava raporunu açtım.")])
        with _AracYamasi('hava_durumu', AracSonuc.ok("güneşli")):
            sonuc = Ajan(model).calistir("hava")
        self.assertEqual(model.eklenen_kullanici, [])
        self.assertEqual(sonuc.metin, "Hava raporunu açtım.")

    def test_teklif_cumlesi_iddia_sayilmaz(self):
        self.assertIsNone(ajan_mod.eylem_iddiasi("İstersen Chrome'u açabilirim."))
        self.assertEqual(ajan_mod.eylem_iddiasi("Tab tuşu basıldı."), "basıldı")

    def test_bu_turun_cumlesi_gecmiste_iki_kez_gitmez(self):
        model = BetikliSaglayici([Adim(metin="ok")])
        gecmis = [{'role': 'user', 'text': 'eski'}, {'role': 'assistant', 'text': 'cevap'},
                  {'role': 'user', 'text': 'merhaba'}]
        Ajan(model).calistir("merhaba", gecmis=gecmis)
        self.assertEqual([m['text'] for m in model.baslangic[1]], ['eski', 'cevap'])


# =========================================================================
class GuvenlikTest(unittest.TestCase):

    def tearDown(self):
        ajan_mod._BEKLEYEN.clear()

    def test_riskli_arac_calismaz_onaya_devredilir(self):
        model = BetikliSaglayici([Adim(cagrilar=[
            cagri('whatsapp_yonet', 'anneme whatsapptan merhaba yaz'),
            cagri('hava_durumu', 'hava'),        # onaydan SONRAKİ adım
        ])])
        with _AracYamasi('whatsapp_yonet', AracSonuc.ok("gönderildi")) as wa, \
                _AracYamasi('hava_durumu', AracSonuc.ok("x")) as hava:
            sonuc = Ajan(model).calistir("anneme selam söyle sonra hava")
        wa.assert_not_called()
        hava.assert_not_called()
        self.assertTrue(sonuc.onay_gerekli)
        self.assertEqual(sonuc.onay_komutu, 'anneme whatsapptan merhaba yaz')
        self.assertTrue(sonuc.onay_mesaji)

    def test_guvenlik_katmani_yasaklarsa_calismaz_ve_model_gorur(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('uygulama_calistir', 'bilgisayarı kapat')]),
                                  Adim(metin="Bunun için onay cümlesini yazman gerek.")])
        with _AracYamasi('uygulama_calistir', AracSonuc.ok("kapatılıyor")) as uyg:
            sonuc = Ajan(model).calistir("pc'yi kapat")
        uyg.assert_not_called()
        self.assertIn("YASAK", model.gelen_sonuclar[0][0][1])
        self.assertEqual(sonuc.adimlar[0]['durum'], 'yasak')

    def test_guvenlik_olculemezse_sorulur(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('uygulama_calistir', 'chrome aç')])])
        with _AracYamasi('uygulama_calistir', AracSonuc.ok("açıldı")) as uyg, \
                patch('core.layers.pipeline_layers.SecurityAnalyzerLayer.process',
                      side_effect=RuntimeError("bozuk")):
            sonuc = Ajan(model).calistir("chrome")
        uyg.assert_not_called()
        self.assertTrue(sonuc.onay_gerekli)

    def test_ekrana_tiklama_onaydan_sonra_ayni_aracla_bir_kez_calisir(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('ekranda_tikla', 'tamam düğmesine tıkla')])])
        with _AracYamasi('ekranda_tikla', AracSonuc.ok("tıklandı")) as tikla:
            sonuc = Ajan(model, kanal='desktop').calistir("tamama bas")
            tikla.assert_not_called()
            self.assertIsNone(bekleyen_araci_yurut("başka komut", 'desktop'))
            self.assertEqual(bekleyen_araci_yurut(sonuc.onay_komutu, 'desktop'), (True, "tıklandı"))
            self.assertIsNone(bekleyen_araci_yurut(sonuc.onay_komutu, 'desktop'), "tek kullanımlık değil")
        tikla.assert_called_once()

    def test_onayli_yurutucu_bekleyen_ajan_aracini_kullanir(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('ekranda_tikla', 'kaydet düğmesine tıkla')])])
        with _AracYamasi('ekranda_tikla', AracSonuc.ok("tıklandı")) as tikla:
            sonuc = Ajan(model).calistir("kaydet")
            from features.confirmed_executor import onayli_komut_yurut
            self.assertEqual(onayli_komut_yurut(sonuc.onay_komutu), (True, "tıklandı"))
        tikla.assert_called_once()


# =========================================================================
class YedekTest(unittest.TestCase):

    def test_bulut_duserse_yerel_devralir_ve_soylenir(self):
        bulut = BetikliSaglayici([], hata=SaglayiciHatasi("Claude'a ulaşılamadı"))
        yerel = BetikliSaglayici([Adim(metin="yerelden selam")])
        sonuc = Ajan(bulut, yedek_saglayici=yerel).calistir("selam")
        self.assertIn("yerelden selam", sonuc.metin)
        self.assertIn("yerel modelle devam", sonuc.metin)
        self.assertIsNone(sonuc.hata)

    def test_yedek_yoksa_hata_doner(self):
        sonuc = Ajan(BetikliSaglayici([], hata=SaglayiciHatasi("yok"))).calistir("selam")
        self.assertEqual(sonuc.hata, "yok")


# =========================================================================
def _motor(config):
    from core.engine import UltronCoreEngine
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    with open('database/schema.sql', encoding='utf-8') as f:
        cur.executescript(f.read())
    base = {'ai_provider': 'none', 'llm_intent_enabled': False}
    base.update(config)
    return UltronCoreEngine(cursor=cur, conn=conn, config=base)


class MotorBaglantisiTest(unittest.TestCase):

    def _calistir(self, cumle, model, mod='yerel', **kw):
        motor = _motor({'ajan_modu': mod})
        with patch('features.ajan_saglayici.saglayici_sec', return_value=(model, None)) as sec:
            ctx = motor.process(cumle, **kw)
        return ctx, sec

    def test_sohbete_dusen_is_ajana_gider(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('hava_durumu', 'hava')]),
                                  Adim(metin="Hava güneşli.")])
        with _AracYamasi('hava_durumu', AracSonuc.ok("güneşli")):
            ctx, sec = self._calistir("bugün dışarı çıksam üşür müyüm acaba", model)
        sec.assert_called_once()
        self.assertTrue(ctx.execution_success)
        self.assertIn("Hava güneşli.", ctx.execution_result)
        self.assertIn("hava_durumu", ctx.execution_result, "iz satırı yok — sessiz ajan")
        self.assertEqual(ctx.intent_source, "ajan")

    def test_regexin_bildigi_komut_ajana_GITMEZ(self):
        model = BetikliSaglayici([])
        with _AracYamasi('saat_tarih', AracSonuc.ok("02:00")):
            ctx, sec = self._calistir("saat kaç", model)
        sec.assert_not_called()
        self.assertEqual(ctx.intent, "TIME_DATE")

    def test_ajan_kapaliyken_cagrilmaz(self):
        ctx, sec = self._calistir("bugün dışarı çıksam üşür müyüm acaba",
                                  BetikliSaglayici([]), mod='kapali')
        sec.assert_not_called()

    def test_ajan_onayi_motorda_onay_kartina_doner(self):
        model = BetikliSaglayici([Adim(cagrilar=[cagri('whatsapp_yonet', 'anneme whatsapptan merhaba yaz')])])
        ctx, _ = self._calistir("annemi bir selamlasana", model)
        self.assertEqual(ctx.security_level, "CONFIRM")
        self.assertEqual(ctx.onay_komutu, 'anneme whatsapptan merhaba yaz')
        self.assertFalse(ctx.execution_success)

    def test_saglayiciya_ulasilamazsa_eski_akis_devam_eder(self):
        model = BetikliSaglayici([], hata=SaglayiciHatasi("Ollama kapalı"))
        ctx, _ = self._calistir("bugün dışarı çıksam üşür müyüm acaba", model)
        self.assertFalse(ctx.execution_success)
        self.assertEqual(ctx.intent_source, "regex")

    def test_cok_adimli_cumle_planner_yerine_ajana_gider(self):
        model = BetikliSaglayici([Adim(metin="tamam")])
        motor = _motor({'ajan_modu': 'yerel'})
        with patch('features.ajan_saglayici.saglayici_sec', return_value=(model, None)), \
                patch.object(motor, '_plani_kur_ve_calistir') as plan:
            motor.process("önce hava durumuna bak sonra dövizi söyle")
        plan.assert_not_called()

    def test_sesli_ortam_konusmasi_ajana_da_gitmez(self):
        model = BetikliSaglayici([])
        uzun = ("bunu yapıyorsa büyük fabrikalar bizim gözümüzün yaşına bakmaz şimdi bu "
                "elemanın ne yaptığını anlamamız lazım hemen gidip bakalım")
        _ctx, sec = self._calistir(uzun, model, input_type="voice")
        sec.assert_not_called()


# =========================================================================
class TelegramOnayKomutuTest(unittest.TestCase):

    def test_bekleyen_komut_ajanin_komutudur(self):
        from ui.tau_window import TelegramWorkerThread
        ctx = SimpleNamespace(security_level="CONFIRM", security_message="kart",
                              onay_komutu="anneme whatsapptan merhaba yaz")
        controller = SimpleNamespace(config={'telegram_chat_id': '1'},
                                     engine=MagicMock(process=MagicMock(return_value=ctx)))
        w = TelegramWorkerThread(controller)
        tg = MagicMock()
        self.assertIsNone(w._process_command(tg, 'T', 1, "annemi selamla"))
        self.assertEqual(w.pending[1][0], "anneme whatsapptan merhaba yaz")


# =========================================================================
class SaglayiciSecimiTest(unittest.TestCase):

    def test_kapali(self):
        self.assertEqual(sg.saglayici_sec({'ajan_modu': 'kapali'}), (None, None))
        self.assertEqual(sg.saglayici_sec({}), (None, None))

    def test_yerel(self):
        b, y = sg.saglayici_sec({'ajan_modu': 'yerel'})
        self.assertIsInstance(b, sg.OllamaSaglayici)
        self.assertIsNone(y)

    def test_hibrit_anahtarsiz_yerele_duser(self):
        with patch.dict('os.environ', {}, clear=False) as _e:
            import os
            os.environ.pop('ANTHROPIC_API_KEY', None)
            b, y = sg.saglayici_sec({'ajan_modu': 'hibrit'}, internet_var=True)
        self.assertIsInstance(b, sg.OllamaSaglayici)

    def test_hibrit_anahtar_ve_internetle_claude_yedek_yerel(self):
        b, y = sg.saglayici_sec({'ajan_modu': 'hibrit', 'claude_api_key': 'sk-test'},
                                internet_var=True)
        self.assertIsInstance(b, sg.ClaudeSaglayici)
        self.assertIsInstance(y, sg.OllamaSaglayici)

    def test_hibrit_internetsiz_yerel(self):
        b, _ = sg.saglayici_sec({'ajan_modu': 'hibrit', 'claude_api_key': 'sk-test'},
                                internet_var=False)
        self.assertIsInstance(b, sg.OllamaSaglayici)


# =========================================================================
def _blok(**kw):
    return SimpleNamespace(**kw)


class ClaudeBicimTest(unittest.TestCase):
    """Ağa çıkmaz: istemci taklit edilir, istek gövdesi incelenir."""

    def _saglayici(self, yanitlar):
        istemci = MagicMock()
        istemci.beta.messages.create.side_effect = yanitlar
        s = sg.ClaudeSaglayici({'claude_api_key': 'sk-test'}, istemci=istemci)
        return s, istemci.beta.messages.create

    def test_istek_govdesi(self):
        yanit = _blok(stop_reason="end_turn", content=[_blok(type="text", text="selam")])
        s, create = self._saglayici([yanit])
        s.baslat("SİSTEM", [{'role': 'assistant', 'text': 'baştaki asistan'},
                            {'role': 'user', 'text': 'önceki'}], "merhaba", "Şu an: 02:00.")
        adim = s.uret([{"ad": "hava_durumu", "aciklama": "hava", "sema": {"type": "object"}}])
        kw = create.call_args.kwargs
        self.assertEqual(kw['model'], 'claude-opus-5-5')
        self.assertIn('server-side-fallback-2026-07-01', kw['betas'])
        self.assertEqual(kw['extra_body'], {'fallbacks': 'default'})
        self.assertEqual(kw['output_config'], {'effort': 'low'})
        self.assertEqual(kw['system'][0]['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(kw['tools'][0]['input_schema'], {"type": "object"})
        self.assertNotIn('tool_choice', kw)   # zorlanmış seçim Opus 5.5'te 400
        self.assertEqual(kw['messages'][0]['role'], 'user', 'ilk mesaj user olmalı')
        self.assertEqual(kw['system'][0]['text'], "SİSTEM", 'değişken bağlam sisteme girdi — önbellek kaçar')
        # (liste referansla yakalandı; cevaptan sonra asistan mesajı da eklendi)
        son = [m for m in kw['messages'] if m['role'] == 'user'][-1]['content']
        self.assertTrue(son.startswith("merhaba"), 'bağlam kullanıcı cümlesinin ÖNÜNE geçti')
        self.assertIn("Şu an: 02:00.", son)
        self.assertEqual(adim.metin, "selam")

    def test_arac_cagrisi_ve_sonuclar_tek_user_mesajinda(self):
        icerik = [_blok(type="thinking", thinking=""),
                  _blok(type="tool_use", id="t1", name="hava_durumu", input={"metin": "hava"}),
                  _blok(type="tool_use", id="t2", name="doviz", input={"metin": "dolar"})]
        s, _ = self._saglayici([_blok(stop_reason="tool_use", content=icerik)])
        s.baslat("S", [], "x")
        adim = s.uret([])
        self.assertEqual([c.ad for c in adim.cagrilar], ["hava_durumu", "doviz"])
        # Asistan içeriği OLDUĞU GİBİ (thinking dahil) geri eklendi
        self.assertIs(s.mesajlar[-1]['content'], icerik)
        s.sonuclari_ekle([(adim.cagrilar[0], "güneşli", False), (adim.cagrilar[1], "hata", True)])
        son = s.mesajlar[-1]
        self.assertEqual(son['role'], 'user')
        self.assertEqual([b['tool_use_id'] for b in son['content']], ["t1", "t2"])
        self.assertEqual([b['is_error'] for b in son['content']], [False, True])

    def test_ret_durumu_icerik_okunmadan_islenir(self):
        s, _ = self._saglayici([_blok(stop_reason="refusal", content=[])])
        s.baslat("S", [], "x")
        adim = s.uret([])
        self.assertTrue(adim.reddedildi)
        self.assertFalse(adim.cagrilar)

    def test_baglanti_hatasi_gecici_saglayici_hatasina_cevrilir(self):
        import anthropic
        hata = anthropic.APIConnectionError(request=MagicMock())
        s, _ = self._saglayici(hata)
        s.baslat("S", [], "x")
        with self.assertRaises(SaglayiciHatasi) as cm:
            s.uret([])
        self.assertTrue(cm.exception.gecici)


class OllamaBicimTest(unittest.TestCase):

    def _cevap(self, mesaj, kod=200):
        r = MagicMock(status_code=kod, text="")
        r.json.return_value = {"message": mesaj}
        return r

    def test_arac_cagrisi_ayristirilir_metin_argumanli_da(self):
        s = sg.OllamaSaglayici({'ollama_model': 'm'})
        s.baslat("S", [], "x", "Şu an: 02:00.")
        self.assertEqual(s.mesajlar[0], {"role": "system", "content": "S\n\nŞu an: 02:00."})
        self.assertEqual(s.mesajlar[-1], {"role": "user", "content": "x"})
        mesaj = {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "hava_durumu", "arguments": {"metin": "hava"}}},
            {"function": {"name": "doviz", "arguments": '{"metin": "dolar"}'}},
        ]}
        with patch.object(sg.requests, 'post', return_value=self._cevap(mesaj)) as post:
            adim = s.uret([{"ad": "hava_durumu", "aciklama": "h", "sema": {"type": "object"}}])
        govde = post.call_args.kwargs['json']
        self.assertEqual(govde['tools'][0]['function']['name'], 'hava_durumu')
        self.assertFalse(govde['stream'])
        self.assertGreaterEqual(govde['options']['num_ctx'], 8192)
        self.assertEqual([(c.ad, c.girdi['metin']) for c in adim.cagrilar],
                         [("hava_durumu", "hava"), ("doviz", "dolar")])
        s.sonuclari_ekle([(adim.cagrilar[0], "güneşli", False)])
        self.assertEqual(s.mesajlar[-1], {"role": "tool", "content": "güneşli",
                                          "tool_name": "hava_durumu"})

    def test_ulasilamazsa_saglayici_hatasi(self):
        s = sg.OllamaSaglayici({})
        s.baslat("S", [], "x")
        with patch.object(sg.requests, 'post', side_effect=sg.requests.ConnectionError()):
            with self.assertRaises(SaglayiciHatasi):
                s.uret([])


if __name__ == '__main__':
    unittest.main()
