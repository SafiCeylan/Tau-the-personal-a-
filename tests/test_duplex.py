# -*- coding: utf-8 -*-
"""
CANLI SESLİ SOHBET — oturum kuralları (features/duplex.py).

Saf mantık: Qt yok, mikrofon yok, saat taklit edilir. Arayüz bağlantısı
tests/test_duplex_dongusu.py'de sınanır — ikisi ayrı iddiadır.
"""
import unittest

from features import duplex
from features.duplex import DINLIYOR, ISLIYOR, KAPALI, DuplexOturumu, kapatma_istegi_mi


class _Saat:
    """Testin ilerletebildiği saat."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def ilerlet(self, sn):
        self.t += sn


class KapatmaIstegiTest(unittest.TestCase):
    """⚠️ EN ÖNEMLİ KURAL: kapatma yalnız sohbetin KENDİSİ hakkındaysa."""

    def test_tek_basina_soylenen_kapatma_sozleri(self):
        for m in ('dur', 'Dur.', 'durdur', 'kapat', 'yeter', 'tamam', 'iptal', 'sus', 'bitti'):
            with self.subTest(m=m):
                self.assertTrue(kapatma_istegi_mi(m))

    def test_acikca_sesli_sohbeti_kapatan_cumleler(self):
        for m in ('sesli sohbeti kapat', 'canlı sohbeti bitir',
                  'canlı sesli sohbeti sonlandır', 'sesli modu kapat'):
            with self.subTest(m=m):
                self.assertTrue(kapatma_istegi_mi(m))

    def test_KOMUTLAR_sohbeti_kapatmaz(self):
        """16 Eyl öncesi hata: "müziği durdur" sesli sohbeti kapatıyordu."""
        for m in ('müziği durdur', 'ekran takibini durdur', 'hatırlatmayı iptal et',
                  'şarkıyı kapat', 'chrome\'u kapat', 'sayacı durdur',
                  'odaklanmayı iptal et', 'bilgisayarı kapat'):
            with self.subTest(m=m):
                self.assertFalse(kapatma_istegi_mi(m))

    def test_siradan_cumleler(self):
        for m in ('hava durumu nedir', 'durum raporu ver', 'bugün nasılsın', '', None):
            with self.subTest(m=m):
                self.assertFalse(kapatma_istegi_mi(m))


class OturumAkisiTest(unittest.TestCase):

    def setUp(self):
        self.saat = _Saat()
        self.o = DuplexOturumu(simdi=self.saat)

    def test_baslat_dinlemeye_gecer_ve_duyurur(self):
        eylem, mesaj = self.o.baslat()
        self.assertEqual(eylem, 'dinle')
        self.assertIn('açık', mesaj)
        self.assertTrue(self.o.aktif_mi())
        self.assertEqual(self.o.durum, DINLIYOR)

    def test_ikinci_baslat_tekrar_duyurmaz(self):
        self.o.baslat()
        self.assertEqual(self.o.baslat(), ('dinle', None))

    def test_konusma_isle_karari_verir_ve_tur_sayar(self):
        self.o.baslat()
        self.assertEqual(self.o.kullanici_konustu('hava durumu nasıl'), ('isle', None))
        self.assertEqual(self.o.tur, 1)
        self.assertEqual(self.o.durum, ISLIYOR)

    def test_cevap_bitince_tekrar_dinler(self):
        self.o.baslat()
        self.o.kullanici_konustu('saat kaç')
        self.assertEqual(self.o.konusma_bitti(), ('dinle', None))
        self.assertEqual(self.o.durum, DINLIYOR)

    def test_kapatma_sozu_oturumu_bitirir(self):
        self.o.baslat()
        self.o.kullanici_konustu('saat kaç')
        eylem, mesaj = self.o.kullanici_konustu('dur')
        self.assertEqual(eylem, 'kapat')
        self.assertIn('kapandı', mesaj)
        self.assertIn('1 konuşma', mesaj)
        self.assertFalse(self.o.aktif_mi())

    def test_muzigi_durdur_ISLENIR(self):
        self.o.baslat()
        self.assertEqual(self.o.kullanici_konustu('müziği durdur'), ('isle', None))
        self.assertTrue(self.o.aktif_mi())

    def test_kapali_oturum_olaylari_yoksayar(self):
        self.assertEqual(self.o.kullanici_konustu('merhaba'), ('yoksay', None))
        self.assertEqual(self.o.sessizlik_oldu(), ('yoksay', None))
        self.assertEqual(self.o.hata_oldu('x'), ('yoksay', None))
        self.assertEqual(self.o.konusma_bitti(), ('yoksay', None))
        self.assertEqual(self.o.kapat(), ('yoksay', None))


class SessizlikVeHataTest(unittest.TestCase):

    def setUp(self):
        self.saat = _Saat()
        self.o = DuplexOturumu(simdi=self.saat)
        self.o.baslat()

    def test_ilk_sessizlik_kapatmaz(self):
        """Tek sessizlik yüzünden kapanmak, kullanıcıyı sohbeti baştan açmaya zorlar."""
        eylem, mesaj = self.o.sessizlik_oldu()
        self.assertEqual(eylem, 'dinle')
        self.assertIn('duyamadım', mesaj)
        self.assertTrue(self.o.aktif_mi())

    def test_ikinci_sessizlik_kapatir(self):
        self.o.sessizlik_oldu()
        eylem, mesaj = self.o.sessizlik_oldu()
        self.assertEqual(eylem, 'kapat')
        self.assertIn('Ses gelmedi', mesaj)

    def test_bos_metin_sessizlik_sayilir(self):
        self.assertEqual(self.o.kullanici_konustu('')[0], 'dinle')
        self.assertEqual(self.o.kullanici_konustu('   ')[0], 'kapat')

    def test_araya_giren_konusma_sayaci_sifirlar(self):
        self.o.sessizlik_oldu()
        self.o.kullanici_konustu('saat kaç')
        self.assertEqual(self.o.sessizlik_oldu()[0], 'dinle')

    def test_ilk_hata_kapatmaz_ikincisi_kapatir(self):
        self.assertEqual(self.o.hata_oldu('ağ yok')[0], 'dinle')
        eylem, mesaj = self.o.hata_oldu('ağ yok')
        self.assertEqual(eylem, 'kapat')
        self.assertIn('sürekli başarısız', mesaj)

    def test_sayaclar_config_ile_ayarlanir(self):
        o = DuplexOturumu(config={'duplex_max_sessizlik': 3})
        o.baslat()
        self.assertEqual(o.sessizlik_oldu()[0], 'dinle')
        self.assertEqual(o.sessizlik_oldu()[0], 'dinle')
        self.assertEqual(o.sessizlik_oldu()[0], 'kapat')

    def test_bozuk_config_varsayilana_duser(self):
        o = DuplexOturumu(config={'duplex_max_sessizlik': 'iki', 'duplex_max_dakika': 0})
        self.assertEqual(o.max_sessizlik, duplex.VARSAYILAN_MAX_SESSIZLIK)
        self.assertEqual(o.max_dakika, duplex.VARSAYILAN_MAX_DAKIKA)


class SureTavaniTest(unittest.TestCase):
    """Açık unutulan oturum mikrofonu saatlerce açık tutmasın."""

    def setUp(self):
        self.saat = _Saat()
        self.o = DuplexOturumu(config={'duplex_max_dakika': 10}, simdi=self.saat)
        self.o.baslat()

    def test_sure_dolunca_konusmada_kapanir(self):
        self.saat.ilerlet(11 * 60)
        eylem, mesaj = self.o.kullanici_konustu('saat kaç')
        self.assertEqual(eylem, 'kapat')
        self.assertIn('süre doldu', mesaj)

    def test_sure_dolunca_cevap_sonrasi_kapanir(self):
        self.o.kullanici_konustu('saat kaç')
        self.saat.ilerlet(11 * 60)
        self.assertEqual(self.o.konusma_bitti()[0], 'kapat')

    def test_sure_dolmadan_devam_eder(self):
        self.saat.ilerlet(9 * 60)
        self.assertEqual(self.o.kullanici_konustu('saat kaç')[0], 'isle')


class EskiKapiTest(unittest.TestCase):
    """speech.is/set_duplex_voice_active ikinci bir bayrak TUTMAZ, oturuma bakar."""

    def tearDown(self):
        duplex.OTURUM.kapat()

    def test_eski_fonksiyonlar_oturumu_yonetir(self):
        from features import speech
        self.assertFalse(speech.is_duplex_voice_active())
        speech.set_duplex_voice_active(True)
        self.assertTrue(speech.is_duplex_voice_active())
        self.assertTrue(duplex.OTURUM.aktif_mi())
        speech.set_duplex_voice_active(False)
        self.assertFalse(duplex.OTURUM.aktif_mi())

    def test_arac_oturumu_acip_kapatir(self):
        import core.builtin_tools  # noqa: F401
        from core.tools import DEFTER
        arac = DEFTER.intent_ile('DUPLEX_VOICE')
        sonuc = arac.calistir(metin='canlı sesli sohbeti başlat')
        self.assertTrue(duplex.OTURUM.aktif_mi())
        self.assertTrue(sonuc.veri.get('duplex_voice'))
        sonuc = arac.calistir(metin='sesli sohbeti kapat')
        self.assertFalse(duplex.OTURUM.aktif_mi())
        self.assertFalse(sonuc.veri.get('duplex_voice'))


if __name__ == '__main__':
    unittest.main()
