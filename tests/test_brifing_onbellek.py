# -*- coding: utf-8 -*-
"""
HAVA / DÖVİZ AĞ ÖNBELLEĞİ.

Ölçüm (15 Eyl 2026): "hava durumu nedir" 955–1134 ms sürüyordu, tamamı ağ
bekleyişi. Sabah brifingi hava + dövizi birlikte çağırdığı için ~2 sn açılıyordu.
Önbellek sonrası ikinci çağrı 0 ms.

İkinci kazanç ÇEVRİMDIŞI davranıştır: servise ulaşılamazsa bölüm tamamen
düşmek yerine bayat değer YAŞIYLA BİRLİKTE dönüyor. Yaşını söylemeden vermek
yasak — kullanıcı eski kuru güncel sanmamalı.
"""
import time
import unittest
from unittest.mock import patch

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from features import briefing


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class OnbellekAltyapisiTest(unittest.TestCase):

    def setUp(self):
        briefing.onbellegi_temizle()

    def tearDown(self):
        briefing.onbellegi_temizle()

    def test_taze_kayit_ureticiyi_hic_cagirmaz(self):
        cagri = []

        def uretici():
            cagri.append(1)
            return 'deger'

        d1, y1 = briefing._onbellekli_cagir('t', uretici, tazelik_sn=60)
        d2, y2 = briefing._onbellekli_cagir('t', uretici, tazelik_sn=60)

        self.assertEqual((d1, d2), ('deger', 'deger'))
        self.assertEqual((y1, y2), (0.0, 0.0))
        self.assertEqual(len(cagri), 1, 'önbellek varken ağa gidildi')

    def test_bayatlayinca_yeniden_uretir(self):
        sayac = {'n': 0}

        def uretici():
            sayac['n'] += 1
            return 'deger%d' % sayac['n']

        d1, _ = briefing._onbellekli_cagir('t', uretici, tazelik_sn=0.01)
        time.sleep(0.02)
        d2, _ = briefing._onbellekli_cagir('t', uretici, tazelik_sn=0.01)

        self.assertEqual(d1, 'deger1')
        self.assertEqual(d2, 'deger2')

    def test_uretici_patlarsa_BAYAT_deger_yasiyla_doner(self):
        """Asıl kazanç: internet yokken bölüm tamamen düşmesin."""
        briefing._onbellekli_cagir('t', lambda: 'eski', tazelik_sn=0.01)
        time.sleep(0.02)

        def patlayan():
            raise OSError('ag yok')

        deger, yas = briefing._onbellekli_cagir('t', patlayan, tazelik_sn=0.01)
        self.assertEqual(deger, 'eski')
        self.assertGreater(yas, 0, 'bayat değer taze gibi döndü — yaşı kaybolmuş')

    def test_uretici_None_donerse_de_bayat_kullanilir(self):
        briefing._onbellekli_cagir('t', lambda: 'eski', tazelik_sn=0.01)
        time.sleep(0.02)
        deger, yas = briefing._onbellekli_cagir('t', lambda: None, tazelik_sn=0.01)
        self.assertEqual(deger, 'eski')
        self.assertGreater(yas, 0)

    def test_hic_kayit_yokken_basarisizlik_None_doner(self):
        deger, yas = briefing._onbellekli_cagir('t', lambda: None, tazelik_sn=60)
        self.assertIsNone(deger)
        self.assertIsNone(yas)

    def test_yas_metni_okunabilir(self):
        self.assertEqual(briefing._yas_metni(5), 'az önce')
        self.assertEqual(briefing._yas_metni(120), '2 dakika önce')
        self.assertEqual(briefing._yas_metni(7200), '2 saat önce')


class RaporlardaBayatUyarisiTest(unittest.TestCase):
    """Bayat veri kullanıldığında kullanıcı BUNU GÖRMELİ."""

    def setUp(self):
        briefing.onbellegi_temizle()

    def tearDown(self):
        briefing.onbellegi_temizle()

    SAHTE_HAVA = {
        'sehir': 'Istanbul',
        'simdi': ('parçalı bulutlu', 20, 19),
        'gunler': [('güneşli', 15, 25)],
    }

    def test_hava_raporu_onbellekten_aga_gitmez(self):
        with patch.object(briefing, '_hava_ozet_veri_ham',
                          return_value=self.SAHTE_HAVA) as sahte:
            briefing.hava_raporu()
            briefing.hava_raporu()
        self.assertEqual(sahte.call_count, 1, 'ikinci çağrıda yine ağa gidildi')

    def test_hava_raporu_bayatsa_uyari_basar(self):
        with patch.object(briefing, '_hava_ozet_veri_ham', return_value=self.SAHTE_HAVA):
            briefing.hava_raporu()
        # Kaydı bayatlat
        with briefing._ONBELLEK_KILIDI:
            _z, d = briefing._ONBELLEK['hava']
            briefing._ONBELLEK['hava'] = (time.time() - 3600, d)

        with patch.object(briefing, '_hava_ozet_veri_ham', side_effect=OSError('ag yok')):
            metin = briefing.hava_raporu()

        self.assertIn('Istanbul', metin, 'bayat veri hiç kullanılmamış')
        self.assertIn('ulaşılamıyor', metin, 'bayat veri UYARISIZ sunuldu')
        self.assertIn('saat önce', metin, 'verinin yaşı söylenmemiş')

    def test_doviz_raporu_bayatsa_uyari_basar(self):
        with patch.object(briefing, '_doviz_ham', return_value='💵 **Döviz:** Dolar **40.00 ₺**'):
            briefing.doviz_raporu()
        with briefing._ONBELLEK_KILIDI:
            _z, d = briefing._ONBELLEK['doviz']
            briefing._ONBELLEK['doviz'] = (time.time() - 1800, d)

        with patch.object(briefing, '_doviz_ham', side_effect=OSError('ag yok')):
            metin = briefing.doviz_raporu()

        self.assertIn('40.00', metin)
        self.assertIn('ulaşılamıyor', metin, 'bayat kur UYARISIZ sunuldu')

    def test_hic_veri_yokken_hava_raporu_duzgun_hata_verir(self):
        with patch.object(briefing, '_hava_ozet_veri_ham', side_effect=OSError('ag yok')):
            metin = briefing.hava_raporu()
        self.assertIn('ulaşılamadı', metin)

    def test_hic_veri_yokken_doviz_raporu_duzgun_hata_verir(self):
        with patch.object(briefing, '_doviz_ham', side_effect=OSError('ag yok')):
            metin = briefing.doviz_raporu()
        self.assertIn('ulaşılamadı', metin)


if __name__ == '__main__':
    unittest.main()
