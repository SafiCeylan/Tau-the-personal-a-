# -*- coding: utf-8 -*-
"""
PENCERE DEĞİŞİMİ BEKLEME — sabit uyku yerine yoklama.

Ölçüm (15 Eyl 2026): "chrome aç" komutu 1212 ms sürüyordu ve bunun 1200 ms'i
`uygulama_calistir` içindeki sabit `time.sleep(1.2)` idi. Uygulama 300 ms'de
açılsa da, zaten açık olsa da hep 1,2 sn bekleniyordu.

Bu testler beklemenin OLAYA bağlandığını kilitler:
  • yeni pencere belirdiğinde erken döner
  • uygulama zaten açıksa (odak değişimi) yine erken döner
  • hiçbir şey olmazsa tavanı AŞMAZ (en kötü durum eskisiyle aynı)
"""
import sys
import time
import unittest
from unittest.mock import patch

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from core import world_state


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


@unittest.skipUnless(sys.platform == 'win32', 'pencere yoklaması Windows\'a özel')
class PencereBeklemeTest(unittest.TestCase):

    def test_yeni_pencere_acilinca_erken_doner(self):
        """Yeni bir hwnd belirdiğinde tavanı beklemeden dönmeli."""
        onceki = (frozenset({1, 2}), 100)
        # İlk yoklamada yeni pencere (3) görünüyor
        with patch.object(world_state, 'pencere_durumu_al',
                          return_value=(frozenset({1, 2, 3}), 100)):
            gecen = world_state.pencere_degisimini_bekle(onceki, tavan_sn=1.2)
        self.assertLess(gecen, 0.5, 'yeni pencere göründüğü hâlde bekledi: %.2fs' % gecen)

    def test_zaten_acik_uygulama_one_gelince_erken_doner(self):
        """Uygulama zaten açıksa yeni pencere OLUŞMAZ; odak değişimi yakalanmalı.

        Bu dal olmadan en sık senaryo (zaten açık uygulamayı öne getirme)
        her seferinde tam 1,2 sn beklerdi.
        """
        onceki = (frozenset({1, 2}), 100)
        with patch.object(world_state, 'pencere_durumu_al',
                          return_value=(frozenset({1, 2}), 222)):
            gecen = world_state.pencere_degisimini_bekle(onceki, tavan_sn=1.2)
        self.assertLess(gecen, 0.5, 'odak değiştiği hâlde bekledi: %.2fs' % gecen)

    def test_hicbir_sey_olmazsa_tavani_asmaz(self):
        """En kötü durum eski davranışla aynı olmalı — daha kötü DEĞİL."""
        onceki = (frozenset({1, 2}), 100)
        with patch.object(world_state, 'pencere_durumu_al',
                          return_value=(frozenset({1, 2}), 100)):
            basla = time.perf_counter()
            gecen = world_state.pencere_degisimini_bekle(onceki, tavan_sn=0.3)
            gercek = time.perf_counter() - basla
        self.assertGreaterEqual(gecen, 0.3)
        self.assertLess(gercek, 0.6, 'tavan aşıldı: %.2fs' % gercek)

    def test_yoklama_patlarsa_asili_kalmaz(self):
        """`pencere_durumu_al` hata fırlatırsa bekleme sonsuza kadar sürmemeli."""
        onceki = (frozenset({1}), 100)
        with patch.object(world_state, 'pencere_durumu_al',
                          side_effect=OSError('EnumWindows patladi')):
            gecen = world_state.pencere_degisimini_bekle(onceki, tavan_sn=1.2)
        self.assertLess(gecen, 0.5)

    def test_durum_alma_gercek_sistemde_calisir(self):
        """`pencere_durumu_al` gerçek Windows'ta anlamlı veri dönmeli.

        Sahte veriyle geçen bir test, altındaki ctypes çağrısı bozulduğunda
        yine yeşil kalırdı.
        """
        hwndler, onplan = world_state.pencere_durumu_al()
        self.assertIsInstance(hwndler, frozenset)
        self.assertIsInstance(onplan, int)


class PencereBeklemeTasinabilirlikTest(unittest.TestCase):

    @unittest.skipIf(sys.platform == 'win32', 'Windows dışı davranış')
    def test_windows_disinda_hic_beklemez(self):
        gecen = world_state.pencere_degisimini_bekle((frozenset(), 0), tavan_sn=5)
        self.assertEqual(gecen, 0.0)


if __name__ == '__main__':
    unittest.main()
