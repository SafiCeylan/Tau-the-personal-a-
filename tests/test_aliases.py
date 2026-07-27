# -*- coding: utf-8 -*-
"""
TAKMA ADLAR (Faz 3: Memory) — "patronuma gönder" kime gider?

⚠️ BU MODÜLÜN HATASI GERİ ALINAMAZ. Yanlış takma ad çözümü = yanlış kişiye
mesaj/dosya gitmesi. Bu yüzden testlerin çoğu "ÇÖZMEMESİ gereken" durumlar
üzerine — tıpkı Context Manager'da olduğu gibi, ama sonuçları daha ağır.

Dört kural test edilir:
  1. Sadece AÇIK öğretim kaydedilir (sohbetten çıkarım YOK)
  2. Bulanık eşleşme YOK
  3. Rehber takma addan ÖNCE gelir
  4. Çözüm her zaman GÖRÜNÜR (onay kartında)
"""

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core import aliases


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class _DBTest(unittest.TestCase):
    """Her test kendi geçici memory tablosuyla çalışır."""

    def setUp(self):
        self.dizin = tempfile.mkdtemp(prefix='ultron_alias_')
        self.conn = sqlite3.connect(os.path.join(self.dizin, 'test.db'))
        self.conn.execute("""
            CREATE TABLE memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'Genel'
            )""")
        self.conn.commit()
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()


class OgretimTest(_DBTest):
    """KURAL 1 — sadece açık öğretim."""

    def test_demek_kalibi_ogrenilir(self):
        cevap = aliases.takma_ad_ogren("patronum Ahmet Kaya demek",
                                       self.cursor, self.conn)
        self.assertIsNotNone(cevap)
        self.assertEqual(aliases.takma_adi_coz("patronum", self.cursor), "Ahmet Kaya")

    def test_esittir_kalibi_ogrenilir(self):
        aliases.takma_ad_ogren("patronum = Ahmet Kaya", self.cursor, self.conn)
        self.assertEqual(aliases.takma_adi_coz("patronum", self.cursor), "Ahmet Kaya")

    def test_aslinda_kalibi_ogrenilir(self):
        aliases.takma_ad_ogren("hocam aslında Mehmet Yılmaz", self.cursor, self.conn)
        self.assertEqual(aliases.takma_adi_coz("hocam", self.cursor), "Mehmet Yılmaz")

    def test_dir_kalibi_ogrenilir(self):
        aliases.takma_ad_ogren("annem Ayşe Ceylan'dır", self.cursor, self.conn)
        self.assertEqual(aliases.takma_adi_coz("annem", self.cursor), "Ayşe Ceylan")

    # --- ÖĞRENMEMESİ gerekenler ---------------------------------------
    def test_sohbetten_cikarim_yapilmaz(self):
        """
        "Bugün patronla tartıştım, Ahmet çok sinirliydi" cümlesinden
        patron=Ahmet çıkarmak, bir gün yanlış kişiye mesaj göndermektir.
        """
        for cumle in ("bugün patronla tartıştım, Ahmet çok sinirliydi",
                      "patronum bugün izinli",
                      "Ahmet Kaya ile toplantı yaptık",
                      "annemle konuştum"):
            aliases.takma_ad_ogren(cumle, self.cursor, self.conn)
        self.assertEqual(aliases.takma_adlari_getir(self.cursor), {})

    def test_kendini_isaret_eden_kayit_alinmaz(self):
        aliases.takma_ad_ogren("ahmet = ahmet", self.cursor, self.conn)
        self.assertEqual(aliases.takma_adlari_getir(self.cursor), {})

    def test_komut_kelimeleri_takma_ad_olamaz(self):
        """'bana gönder' cümlesindeki 'bana' takma ad sanılmamalı."""
        for yasak in ('bana', 'telegram', 'whatsapp', 'mail'):
            aliases.takma_ad_kaydet(self.cursor, self.conn, yasak, "Ahmet")
        self.assertEqual(aliases.takma_adlari_getir(self.cursor), {})

    def test_dbsiz_cagri_cokmez(self):
        self.assertIsNone(aliases.takma_ad_ogren("patronum = Ahmet", None, None))


class CozumTest(_DBTest):
    """KURAL 2 — bulanık eşleşme yok."""

    def setUp(self):
        super().setUp()
        aliases.takma_ad_kaydet(self.cursor, self.conn, "patronum", "Ahmet Kaya")

    def test_tam_eslesme_cozulur(self):
        self.assertEqual(aliases.takma_adi_coz("patronum", self.cursor), "Ahmet Kaya")

    def test_buyuk_kucuk_harf_farketmez(self):
        self.assertEqual(aliases.takma_adi_coz("PATRONUM", self.cursor), "Ahmet Kaya")

    def test_turkce_yonelme_eki_tolere_edilir(self):
        """'patronuma gönder' → patronum"""
        self.assertEqual(aliases.takma_adi_coz("patronuma", self.cursor), "Ahmet Kaya")

    def test_benzer_isim_cozulmez(self):
        """
        EN KRİTİK TEST. Dosyada bulanık eşleşme yanlış dosya gösterir
        (rahatsız edici); KİŞİDE yanlış insana mesaj gönderir (telafisi yok).
        """
        for yakin in ("patron", "patronumun", "patronlar", "patronumuz",
                      "patronuma-ait", "patrn"):
            self.assertIsNone(aliases.takma_adi_coz(yakin, self.cursor),
                              f"'{yakin}' bulanık eşleşti — yanlış kişiye gidebilir")

    def test_bilinmeyen_ad_none_doner(self):
        self.assertIsNone(aliases.takma_adi_coz("kuzenim", self.cursor))

    def test_bos_ad_cokmez(self):
        self.assertIsNone(aliases.takma_adi_coz("", self.cursor))
        self.assertIsNone(aliases.takma_adi_coz(None, self.cursor))

    def test_silinen_takma_ad_cozulmez(self):
        aliases.takma_ad_sil(self.cursor, self.conn, "patronum")
        self.assertIsNone(aliases.takma_adi_coz("patronum", self.cursor))

    def test_uzerine_yazilabilir(self):
        """Kullanıcı yanlış kaydı düzeltebilmeli."""
        aliases.takma_ad_kaydet(self.cursor, self.conn, "patronum", "Mehmet Demir")
        self.assertEqual(aliases.takma_adi_coz("patronum", self.cursor), "Mehmet Demir")


class RehberOnceligiTest(unittest.TestCase):
    """KURAL 3 — rehberdeki doğrudan kayıt takma addan önce gelir."""

    def test_rehberdeki_dogrudan_kayit_kazanir(self):
        from features.actions import whatsapp_control
        with mock.patch.object(whatsapp_control, 'kisiler_yukle',
                               return_value={'patronum': '+905551112233'}), \
             mock.patch('core.aliases.takma_adi_coz') as takma:
            numara = whatsapp_control.kisi_coz('patronum')
        self.assertEqual(numara, '+905551112233')
        takma.assert_not_called()

    def test_rehberde_yoksa_takma_ada_bakilir(self):
        from features.actions import whatsapp_control
        with mock.patch.object(whatsapp_control, 'kisiler_yukle',
                               return_value={'ahmet kaya': '+905551112233'}), \
             mock.patch('core.aliases.takma_adi_coz', return_value='Ahmet Kaya'):
            self.assertEqual(whatsapp_control.kisi_coz('patronum'), '+905551112233')

    def test_takma_ad_rehberde_yoksa_cozulmez(self):
        """'patronum' → 'Ahmet Kaya' ama Ahmet rehberde yoksa gönderim olmamalı."""
        from features.actions import whatsapp_control
        with mock.patch.object(whatsapp_control, 'kisiler_yukle', return_value={}), \
             mock.patch('core.aliases.takma_adi_coz', return_value='Ahmet Kaya'):
            self.assertIsNone(whatsapp_control.kisi_coz('patronum'))

    def test_eposta_ayni_sirayi_izler(self):
        from features import email_control
        with mock.patch.object(email_control, 'email_kisiler',
                               return_value={'patronum': 'dogru@x.com',
                                             'ahmet kaya': 'yanlis@x.com'}), \
             mock.patch('core.aliases.takma_adi_coz', return_value='Ahmet Kaya') as t:
            self.assertEqual(email_control.email_coz('patronum'), 'dogru@x.com')
        t.assert_not_called()

    def test_takma_ad_cozumu_cokerse_akis_bozulmaz(self):
        from features.actions import whatsapp_control
        with mock.patch.object(whatsapp_control, 'kisiler_yukle', return_value={}), \
             mock.patch('core.aliases.takma_adi_coz',
                        side_effect=RuntimeError("db yok")):
            whatsapp_control.kisi_coz('patronum')   # istisna SIZMAMALI


class GorunurlukTest(_DBTest):
    """KURAL 4 — çözüm onay kartında görünür."""

    def test_takma_ad_zinciri_gosterilir(self):
        aliases.takma_ad_kaydet(self.cursor, self.conn, "patronum", "Ahmet Kaya")
        metin = aliases.kimlik_zinciri("patronuma", self.cursor)
        self.assertIn("patronuma", metin)
        self.assertIn("Ahmet Kaya", metin)

    def test_takma_ad_yoksa_ad_oldugu_gibi_kalir(self):
        self.assertEqual(aliases.kimlik_zinciri("annem", self.cursor), "annem")

    def test_bos_alici_cokmez(self):
        self.assertEqual(aliases.kimlik_zinciri(None, self.cursor), "")

    def test_onay_kartinda_gercek_kisi_yazar(self):
        """
        EN KRİTİK GÖRÜNÜRLÜK TESTİ: "patronuma gönder" onayında kullanıcı
        KİMİN kastedildiğini görmeden onaylamamalı.
        """
        from core.layers.pipeline_layers import SecurityAnalyzerLayer
        from core.context import UltronContext

        ctx = UltronContext(raw_input="patronuma whatsapp'tan yaz: selam")
        ctx.normalized_input = ctx.raw_input
        ctx.intent = "WHATSAPP_MESSAGE"

        with mock.patch('core.layers.pipeline_layers.whatsapp_gonderim_ayristir',
                        return_value=("patronuma", "selam")), \
             mock.patch('core.layers.pipeline_layers.kisi_coz',
                        return_value="+905551112233"), \
             mock.patch('core.layers.pipeline_layers.kimlik_zinciri',
                        return_value="patronuma → **Ahmet Kaya**"):
            sonuc = SecurityAnalyzerLayer().process(ctx)

        self.assertEqual(sonuc.security_level, "CONFIRM")
        self.assertIn("Ahmet Kaya", sonuc.security_message)


if __name__ == '__main__':
    unittest.main()
