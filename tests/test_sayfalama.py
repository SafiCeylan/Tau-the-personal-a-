# -*- coding: utf-8 -*-
"""
Arama sonuçlarında sayfalama testleri.

ÇÖZÜLEN SORUN: `sonuclari_bicimle` GÖSTERİLEN sayıyı "toplam sonuç" gibi
yazıyordu. 26 eşleşme varken "10 sonuç" diyor, kalan 16 dosyanın varlığını
kullanıcıdan gizliyordu.

EN KRİTİK TEST: `test_ikinci_sayfada_dogru_dosya_secilir`.
Numaralar GENEL sıradır (2. sayfa 11'den başlar). Saklanan `offset` düşülmezse
"12'yi gönder" YANLIŞ DOSYAYI gönderir — sessiz ve tehlikeli bir hata.
"""

import time
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from features import file_index, file_send


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


def _dosya(ad, degisim=1_700_000_000):
    return {'yol': f'C:/test/{ad}', 'ad': ad, 'boyut': 1024,
            'degisim': degisim, 'kok': 'C:/test'}


class BicimlemeTest(unittest.TestCase):

    def test_toplam_verilmezse_gosterilen_kadar_sanilir(self):
        metin = file_index.sonuclari_bicimle([_dosya('a.pdf')], "Test")
        self.assertIn("1 sonuç", metin)

    def test_daha_fazlasi_varsa_toplam_yazilir(self):
        """26 eşleşme varken '10 sonuç' demek kalan 16'yı gizlemekti."""
        sonuclar = [_dosya(f'{i}.pdf') for i in range(10)]
        metin = file_index.sonuclari_bicimle(sonuclar, "Test", toplam=26)
        self.assertIn("26 dosya bulundu", metin)
        self.assertIn("1-10 arası", metin)

    def test_kalan_sayisi_ve_komut_gosterilir(self):
        sonuclar = [_dosya(f'{i}.pdf') for i in range(10)]
        metin = file_index.sonuclari_bicimle(sonuclar, "Test", toplam=26)
        self.assertIn("Kalan 16", metin)
        self.assertIn("devamını göster", metin)

    def test_ikinci_sayfa_11den_numaralanir(self):
        sonuclar = [_dosya(f'{i}.pdf') for i in range(10)]
        metin = file_index.sonuclari_bicimle(sonuclar, "Devamı", toplam=26,
                                             baslangic=11)
        self.assertIn("**11.**", metin)
        self.assertIn("**20.**", metin)
        self.assertNotIn("**1.**", metin.replace("**11.**", "").replace("**21.**", ""))

    def test_son_sayfada_devam_teklifi_yok(self):
        sonuclar = [_dosya(f'{i}.pdf') for i in range(6)]
        metin = file_index.sonuclari_bicimle(sonuclar, "Devamı", toplam=26,
                                             baslangic=21)
        self.assertNotIn("devamını göster", metin)

    def test_bos_sonuc_cokmez(self):
        self.assertIn("bulunamadı", file_index.sonuclari_bicimle([], "Test"))


class SecimTest(unittest.TestCase):
    """Sayfalar arası seçim — sessiz yanlış dosya gönderme riski burada."""

    def setUp(self):
        file_index._SON_SONUCLAR.clear()

    def tearDown(self):
        file_index._SON_SONUCLAR.clear()

    def test_ilk_sayfada_secim(self):
        sonuclar = [_dosya('a.pdf'), _dosya('b.pdf')]
        file_index.son_sonuclari_kaydet('desktop', sonuclar, sorgu='x',
                                        offset=0, toplam=2)
        self.assertEqual(file_index.sonuctan_sec('desktop', 2), 'C:/test/b.pdf')

    def test_ikinci_sayfada_dogru_dosya_secilir(self):
        """
        EN KRİTİK TEST. 2. sayfa 11-20 arasını gösterir; kullanıcı "12'yi gönder"
        der. Saklanan offset düşülmezse listenin 12. elemanı aranır (yok) ya da
        daha kötüsü YANLIŞ dosya seçilir.
        """
        sayfa2 = [_dosya(f'sayfa2_{i}.pdf') for i in range(10)]   # 11..20
        file_index.son_sonuclari_kaydet('desktop', sayfa2, sorgu='x',
                                        offset=10, toplam=26)
        self.assertEqual(file_index.sonuctan_sec('desktop', 12),
                         'C:/test/sayfa2_1.pdf')

    def test_sayfa_disi_numara_reddedilir(self):
        sayfa2 = [_dosya(f's_{i}.pdf') for i in range(10)]
        file_index.son_sonuclari_kaydet('desktop', sayfa2, sorgu='x',
                                        offset=10, toplam=26)
        self.assertIsNone(file_index.sonuctan_sec('desktop', 3))    # 1. sayfada
        self.assertIsNone(file_index.sonuctan_sec('desktop', 25))   # 3. sayfada

    def test_bayat_kayit_secim_yapmaz(self):
        file_index.son_sonuclari_kaydet('desktop', [_dosya('a.pdf')], sorgu='x')
        with mock.patch("features.file_index.time.time",
                        return_value=time.time() + 10_000):
            self.assertIsNone(file_index.sonuctan_sec('desktop', 1))

    def test_kanallar_karismaz(self):
        file_index.son_sonuclari_kaydet('desktop', [_dosya('masaustu.pdf')], sorgu='x')
        file_index.son_sonuclari_kaydet('12345', [_dosya('telefon.pdf')], sorgu='x')
        self.assertEqual(file_index.sonuctan_sec('desktop', 1), 'C:/test/masaustu.pdf')
        self.assertEqual(file_index.sonuctan_sec('12345', 1), 'C:/test/telefon.pdf')


class SayfaKomutuTest(unittest.TestCase):

    def setUp(self):
        file_index._SON_SONUCLAR.clear()

    def tearDown(self):
        file_index._SON_SONUCLAR.clear()

    def _kaydet(self, offset=0, toplam=26, adet=10):
        file_index.son_sonuclari_kaydet(
            'desktop', [_dosya(f'{i}.pdf') for i in range(adet)],
            sorgu='rapor', offset=offset, toplam=toplam)

    def test_onceki_arama_yoksa_ustlenilmez(self):
        """'devam et' her bağlamda dosya komutu değildir."""
        islendi, _ = file_send.sayfa_komutu_algila("devamını göster", 'desktop')
        self.assertFalse(islendi)

    def test_devam_komutu_sonraki_sayfayi_getirir(self):
        self._kaydet()
        sayfa2 = [_dosya(f'y_{i}.pdf') for i in range(10)]
        with mock.patch.object(file_index, 'ara', return_value=sayfa2) as ara:
            islendi, cevap = file_send.sayfa_komutu_algila("devamını göster", 'desktop')
        self.assertTrue(islendi)
        self.assertEqual(ara.call_args.kwargs['offset'], 10)
        self.assertIn("11-20 arası", cevap)

    def test_hepsi_gosterildiyse_bildirilir(self):
        self._kaydet(offset=0, toplam=10, adet=10)
        islendi, cevap = file_send.sayfa_komutu_algila("devamını göster", 'desktop')
        self.assertTrue(islendi)
        self.assertIn("Hepsi bu kadar", cevap)

    def test_devam_ifadeleri_taninir(self):
        self._kaydet()
        with mock.patch.object(file_index, 'ara', return_value=[_dosya('x.pdf')]):
            for ifade in ("devamını göster", "diğerlerini göster", "gerisini göster",
                          "daha fazla", "sonraki", "kalanları göster"):
                islendi, _ = file_send.sayfa_komutu_algila(ifade, 'desktop')
                self.assertTrue(islendi, ifade)

    def test_alakasiz_cumle_ustlenilmez(self):
        self._kaydet()
        for ifade in ("hava durumu nasıl", "chrome aç", "saat kaç"):
            islendi, _ = file_send.sayfa_komutu_algila(ifade, 'desktop')
            self.assertFalse(islendi, ifade)

    def test_sonraki_sayfa_kaydi_gunceller(self):
        """İkinci 'devamını göster' 21'den başlamalı."""
        self._kaydet()
        sayfa2 = [_dosya(f'y_{i}.pdf') for i in range(10)]
        with mock.patch.object(file_index, 'ara', return_value=sayfa2):
            file_send.sayfa_komutu_algila("devamını göster", 'desktop')
        kayit = file_index.son_arama_bilgisi('desktop')
        self.assertEqual(kayit['offset'], 10)
        self.assertEqual(kayit['toplam'], 26)


class NiyetTest(unittest.TestCase):

    def setUp(self):
        file_index._SON_SONUCLAR.clear()

    def tearDown(self):
        file_index._SON_SONUCLAR.clear()

    def test_devam_niyeti_taze_arama_varken_taninir(self):
        file_index.son_sonuclari_kaydet('desktop', [_dosya('a.pdf')],
                                        sorgu='rapor', toplam=26)
        plan = file_send.dosya_niyeti_coz("devamını göster", 'desktop')
        self.assertEqual((plan or {}).get('islem'), 'devam')

    def test_arama_yokken_devam_dosya_komutu_degildir(self):
        self.assertIsNone(file_send.dosya_niyeti_coz("devam et", 'desktop'))


if __name__ == '__main__':
    unittest.main()


class DaraltmaTest(unittest.TestCase):
    """
    "26 dosya buldum, hangisi?" → kullanıcı `haftalık` yazar → arama daralır.

    EN ÖNEMLİ KURAL: cümle ancak GERÇEKTEN dosya bulunursa sahiplenilir.
    Aksi halde "teşekkürler" gibi masum mesajlar arama sanılır ve kullanıcı
    sohbet edemez hale gelir.
    """

    def setUp(self):
        file_index._SON_SONUCLAR.clear()

    def tearDown(self):
        file_index._SON_SONUCLAR.clear()

    def _bekleyen_arama(self, toplam=26):
        file_index.son_sonuclari_kaydet(
            'desktop', [_dosya(f'{i}.pdf') for i in range(10)],
            sorgu='rapor', offset=0, toplam=toplam, daraltma_bekliyor=True)

    def test_soru_sorulmadiysa_daraltma_yok(self):
        file_index.son_sonuclari_kaydet('desktop', [_dosya('a.pdf')], sorgu='rapor',
                                        toplam=1, daraltma_bekliyor=False)
        islendi, _ = file_send.daraltma_denemesi("haftalık", 'desktop')
        self.assertFalse(islendi)

    def test_terim_sorguya_eklenir(self):
        self._bekleyen_arama()
        with mock.patch.object(file_index, 'sonuc_sayisi', return_value=18) as say, \
             mock.patch.object(file_index, 'ara',
                               return_value=[_dosya('haftalik.pdf')]):
            islendi, cevap = file_send.daraltma_denemesi("haftalık", 'desktop')
        self.assertTrue(islendi)
        self.assertEqual(say.call_args[0][0], "rapor haftalık")
        self.assertIn("daralttım", cevap)

    def test_sonuc_yoksa_cumle_sahiplenilmez(self):
        """'teşekkürler' arama sanılmamalı — LLM cevaplasın."""
        self._bekleyen_arama()
        with mock.patch.object(file_index, 'sonuc_sayisi', return_value=0):
            islendi, cevap = file_send.daraltma_denemesi("teşekkürler", 'desktop')
        self.assertFalse(islendi)
        self.assertIsNone(cevap)

    def test_uzun_cumle_daraltma_sayilmaz(self):
        """Uzun cümle yeni bir konudur, arama terimi değil."""
        self._bekleyen_arama()
        islendi, _ = file_send.daraltma_denemesi(
            "bu arada yarınki hava durumu nasıl olacak acaba", 'desktop')
        self.assertFalse(islendi)

    def test_daraltma_bir_kez_denenir(self):
        """
        Bayrak düşmezse konuşma boyunca her kısa cümle arama terimi sanılır.
        Başarısız deneme de bayrağı düşürmeli.
        """
        self._bekleyen_arama()
        with mock.patch.object(file_index, 'sonuc_sayisi', return_value=0):
            file_send.daraltma_denemesi("alakasız", 'desktop')
        self.assertFalse(file_index.son_arama_bilgisi('desktop')['daraltma_bekliyor'])

    def test_daraltma_sonrasi_hala_coksa_tekrar_sorulur(self):
        self._bekleyen_arama()
        with mock.patch.object(file_index, 'sonuc_sayisi', return_value=18), \
             mock.patch.object(file_index, 'ara',
                               return_value=[_dosya(f'{i}.pdf') for i in range(10)]):
            file_send.daraltma_denemesi("haftalık", 'desktop')
        self.assertTrue(file_index.son_arama_bilgisi('desktop')['daraltma_bekliyor'])

    def test_daraltma_teke_dustuyse_soru_sorulmaz(self):
        self._bekleyen_arama()
        with mock.patch.object(file_index, 'sonuc_sayisi', return_value=1), \
             mock.patch.object(file_index, 'ara', return_value=[_dosya('tek.pdf')]):
            file_send.daraltma_denemesi("haftalık", 'desktop')
        self.assertFalse(file_index.son_arama_bilgisi('desktop')['daraltma_bekliyor'])

    def test_bos_mesaj_cokmez(self):
        self._bekleyen_arama()
        self.assertEqual(file_send.daraltma_denemesi("", 'desktop'), (False, None))

    def test_baska_kanal_daraltmayi_devralmaz(self):
        self._bekleyen_arama()
        islendi, _ = file_send.daraltma_denemesi("haftalık", '12345')
        self.assertFalse(islendi)
