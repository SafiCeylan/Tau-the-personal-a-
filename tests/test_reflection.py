# -*- coding: utf-8 -*-
"""
REFLECTION (Faz 8) — "gerçekten oldu mu?"

LLM'e SORULMAZ: eylemi uydurmuş bir model, kontrolü de uydurur. Deterministik
kanıt aranır.

⚠️ EN ÖNEMLİ KURAL: yansıma BİLGİ EKLER, sonucu tersine ÇEVİRMEZ.
Belirsiz kanıtla "aslında olmadı" demek, çalışan bir işi başarısız
göstermektir — hiç kontrol etmemekten kötüdür. Sonuç yalnızca kanıt
TARTIŞMASIZ olduğunda çevrilir.
"""

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.context import UltronContext
from core.reflection import eylemi_dogrula, hayali_eylem_var_mi, yansit


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


def _ctx(arac=None, basarili=True, sonuc="tamam", **alanlar):
    ctx = UltronContext(raw_input="test")
    ctx.normalized_input = "test"
    ctx.son_arac = arac
    ctx.execution_success = basarili
    ctx.execution_result = sonuc
    for k, v in alanlar.items():
        setattr(ctx, k, v)
    return ctx


class KanitKontroluTest(unittest.TestCase):
    """Ekran görüntüsü gerçekten alındı mı?"""

    def setUp(self):
        self.dizin = tempfile.mkdtemp(prefix='ultron_yansima_')

    def test_dosya_varsa_gecer(self):
        yol = os.path.join(self.dizin, 'ekran.png')
        with open(yol, 'wb') as f:
            f.write(b'x' * 100)
        ctx = _ctx('ekran_goruntusu', entities={'screenshot_path': yol})
        dogrulama = eylemi_dogrula(ctx)
        self.assertTrue(dogrulama.kontrol_edildi)
        self.assertTrue(dogrulama.gecti)

    def test_dosya_yoksa_kesin_basarisiz(self):
        ctx = _ctx('ekran_goruntusu',
                   entities={'screenshot_path': os.path.join(self.dizin, 'yok.png')})
        dogrulama = eylemi_dogrula(ctx)
        self.assertFalse(dogrulama.gecti)
        self.assertTrue(dogrulama.kesin, "dosya yoksa kanıt tartışmasızdır")

    def test_bos_dosya_basarisiz_sayilir(self):
        yol = os.path.join(self.dizin, 'bos.png')
        open(yol, 'wb').close()
        ctx = _ctx('ekran_goruntusu', entities={'screenshot_path': yol})
        self.assertFalse(eylemi_dogrula(ctx).gecti)

    def test_yol_yoksa_kontrol_yapilmaz(self):
        ctx = _ctx('ekran_goruntusu', entities={})
        self.assertFalse(eylemi_dogrula(ctx).kontrol_edildi)

    def test_dogrulayicisi_olmayan_arac_atlanir(self):
        self.assertFalse(eylemi_dogrula(_ctx('hava_durumu')).kontrol_edildi)

    def test_basarisiz_calistirma_dogrulanmaz(self):
        """Zaten başarısızsa doğrulanacak bir iddia yok."""
        ctx = _ctx('ekran_goruntusu', basarili=False,
                   entities={'screenshot_path': '/yok'})
        self.assertFalse(eylemi_dogrula(ctx).kontrol_edildi)


class VeritabaniKanitiTest(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute("CREATE TABLE notlar (id INTEGER PRIMARY KEY, metin TEXT)")
        self.conn.execute(
            "CREATE TABLE hatirlatmalar (id INTEGER PRIMARY KEY, durum TEXT)")
        self.conn.commit()
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def test_not_kaydi_varsa_gecer(self):
        self.cursor.execute("INSERT INTO notlar (metin) VALUES ('x')")
        self.assertTrue(eylemi_dogrula(_ctx('not_yonet'), self.cursor).gecti)

    def test_not_kaydi_yoksa_uyarir(self):
        dogrulama = eylemi_dogrula(_ctx('not_yonet'), self.cursor)
        self.assertFalse(dogrulama.gecti)
        self.assertIn("notlarda görünmüyor", dogrulama.mesaj)

    def test_hatirlatma_kaydi_varsa_gecer(self):
        self.cursor.execute("INSERT INTO hatirlatmalar (durum) VALUES ('bekliyor')")
        self.assertTrue(eylemi_dogrula(_ctx('hatirlatma_kur'), self.cursor).gecti)

    def test_db_yoksa_kontrol_yapilmaz(self):
        self.assertFalse(eylemi_dogrula(_ctx('not_yonet'), None).kontrol_edildi)

    def test_tablo_farkliysa_sessizce_gecer(self):
        """Şema değişmişse yansıma gürültü üretmemeli."""
        bos = sqlite3.connect(':memory:').cursor()
        self.assertFalse(eylemi_dogrula(_ctx('not_yonet'), bos).kontrol_edildi)


class HalusinasyonFreniTest(unittest.TestCase):
    """
    `CLAUDE.md`: "qwen2.5:3b eylemi yapmış gibi rol yapar."
    PromptGenerator bunu yasaklıyordu ama hiçbir şey DOĞRULAMIYORDU.
    """

    def test_arac_calismadan_yaptim_demek_uyarir(self):
        for cevap in ("Chrome'u açtım.", "Dosyayı anneme gönderdim.",
                      "Hatırlatmayı kaydettim.", "Ayarı güncelledim."):
            self.assertIsNotNone(hayali_eylem_var_mi(cevap, False), cevap)

    def test_arac_calistiysa_uyarilmaz(self):
        """Gerçekten olduysa 'açtım' demek doğrudur."""
        self.assertIsNone(hayali_eylem_var_mi("Chrome'u açtım.", True))

    def test_teklif_ve_kosul_uyarilmaz(self):
        for cevap in ("Chrome'u açabilirim, ister misin?",
                      "İstersen dosyayı gönderebilirim.",
                      "Onaylarsan kaydettim sayılır.",
                      "Eğer istersen açarım."):
            self.assertIsNone(hayali_eylem_var_mi(cevap, False), cevap)

    def test_sıradan_sohbet_uyarilmaz(self):
        for cevap in ("Bugün hava güzel.", "Python bir programlama dilidir.",
                      "Nasıl yardımcı olabilirim?"):
            self.assertIsNone(hayali_eylem_var_mi(cevap, False), cevap)

    def test_bos_cevap_cokmez(self):
        self.assertIsNone(hayali_eylem_var_mi("", False))
        self.assertIsNone(hayali_eylem_var_mi(None, False))


class YansitmaTest(unittest.TestCase):
    """KURAL: bilgi ekler, sonucu tersine çevirmez (kesin kanıt hariç)."""

    def test_kesin_kanit_sonucu_cevirir(self):
        ctx = _ctx('ekran_goruntusu', entities={'screenshot_path': '/olmayan.png'})
        sonuc = yansit(ctx)
        self.assertFalse(sonuc.execution_success)
        self.assertIn("diskte yok", sonuc.execution_result)

    def test_belirsizlikte_sonuc_korunur(self):
        """Doğrulayıcısı olmayan araç başarılı kalmalı."""
        ctx = _ctx('hava_durumu', sonuc="22 derece")
        sonuc = yansit(ctx)
        self.assertTrue(sonuc.execution_success)
        self.assertEqual(sonuc.execution_result, "22 derece")

    def test_hayali_eylem_cevaba_eklenir(self):
        ctx = _ctx(None, basarili=False, sonuc=None)
        ctx.llm_response = "Chrome'u senin için açtım."
        sonuc = yansit(ctx)
        self.assertIn("hiçbir işlem çalıştırılmadı", sonuc.llm_response)
        self.assertFalse(sonuc.verification_passed)

    def test_gercek_eylemde_cevap_kirletilmez(self):
        ctx = _ctx('uygulama_calistir', basarili=True)
        ctx.llm_response = "Chrome'u açtım."
        self.assertEqual(yansit(ctx).llm_response, "Chrome'u açtım.")

    def test_yansima_cokerse_akis_bozulmaz(self):
        ctx = _ctx('ekran_goruntusu', entities={'screenshot_path': '/x.png'})
        with mock.patch('core.reflection.eylemi_dogrula',
                        side_effect=RuntimeError("patladı")):
            with self.assertRaises(RuntimeError):
                yansit(ctx)   # engine try/except ile sarmalıyor


if __name__ == '__main__':
    unittest.main()
