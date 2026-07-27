# -*- coding: utf-8 -*-
"""
WORLD STATE (Faz 6) — "Spotify aç" → "zaten açıktı".

⚠️ EN ÖNEMLİ DAVRANIŞ: durum tespiti komutu İPTAL ETMEZ.

"Zaten açık" deyip hiçbir şey yapmamak, kullanıcının komutunu sessizce
yutmaktır. Yanlış tespitte kullanıcı "Spotify aç" der, bir şey olmaz ve
Ultron bozulmuş gibi görünür. Bu yüzden başlatıcı her hâlükârda çağrılır;
world state yalnızca MESAJI değiştirir.

İkinci kural: şüphedeysen False de. Kısa/belirsiz adlar eşleştirilmez.
"""

import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core import world_state


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class _Surec:
    def __init__(self, ad):
        self.info = {'name': ad}


class SurecTespitiTest(unittest.TestCase):

    def setUp(self):
        world_state.onbellegi_temizle()

    def tearDown(self):
        world_state.onbellegi_temizle()

    def _surecler(self, *adlar):
        return mock.patch.object(world_state.psutil, 'process_iter',
                                 return_value=[_Surec(a) for a in adlar])

    def test_calisan_uygulama_bulunur(self):
        with self._surecler('chrome.exe', 'explorer.exe'):
            self.assertTrue(world_state.uygulama_calisiyor_mu('chrome'))

    def test_uzantisiz_ad_da_eslesir(self):
        with self._surecler('spotify.exe'):
            self.assertTrue(world_state.uygulama_calisiyor_mu('spotify'))

    def test_calismayan_uygulama_bulunmaz(self):
        with self._surecler('chrome.exe'):
            self.assertFalse(world_state.uygulama_calisiyor_mu('spotify'))

    def test_kisa_ad_eslestirilmez(self):
        """'not' → notepad eşleşirse 'not al' komutu bozulur."""
        with self._surecler('notepad.exe', 'cmd.exe', 'code.exe'):
            for kisa in ('not', 'cmd', 'vs', 'c'):
                self.assertFalse(world_state.uygulama_calisiyor_mu(kisa), kisa)

    def test_kismi_eslesme_sadece_bastan(self):
        """'chrome' → 'chromedriver.exe' kabul; 'drive' → 'chromedriver' RED."""
        with self._surecler('chromedriver.exe'):
            self.assertTrue(world_state.uygulama_calisiyor_mu('chrome'))
            self.assertFalse(world_state.uygulama_calisiyor_mu('driver'))

    def test_bos_ad_false(self):
        with self._surecler('chrome.exe'):
            self.assertFalse(world_state.uygulama_calisiyor_mu(''))
            self.assertFalse(world_state.uygulama_calisiyor_mu(None))

    def test_psutil_cokerse_false_doner(self):
        """Şüphedeysen işi yap — hata durumunda 'açık değil' denir."""
        with mock.patch.object(world_state.psutil, 'process_iter',
                               side_effect=RuntimeError("erişim yok")):
            self.assertFalse(world_state.uygulama_calisiyor_mu('chrome'))

    def test_onbellek_tekrar_taramayi_onler(self):
        with self._surecler('chrome.exe') as pi:
            world_state.uygulama_calisiyor_mu('chrome')
            world_state.uygulama_calisiyor_mu('spotify')
            world_state.uygulama_calisiyor_mu('code')
        self.assertEqual(pi.call_count, 1)

    def test_onbellek_temizlenince_yeniden_taranir(self):
        with self._surecler('chrome.exe') as pi:
            world_state.uygulama_calisiyor_mu('chrome')
            world_state.onbellegi_temizle()
            world_state.uygulama_calisiyor_mu('chrome')
        self.assertEqual(pi.call_count, 2)


class PilTest(unittest.TestCase):

    def test_pil_okunur(self):
        sahte = mock.Mock(percent=35.7, power_plugged=False)
        with mock.patch.object(world_state.psutil, 'sensors_battery',
                               return_value=sahte):
            self.assertEqual(world_state.pil_durumu(),
                             {'yuzde': 35, 'sarjda': False})

    def test_masaustunde_none(self):
        with mock.patch.object(world_state.psutil, 'sensors_battery',
                               return_value=None):
            self.assertIsNone(world_state.pil_durumu())

    def test_hata_none(self):
        with mock.patch.object(world_state.psutil, 'sensors_battery',
                               side_effect=RuntimeError):
            self.assertIsNone(world_state.pil_durumu())


class AcilisMesajiTest(unittest.TestCase):
    """EN KRİTİK: 'zaten açık' komutu iptal ETMEMELİ."""

    def test_zaten_acikken_baslatici_yine_cagrilir(self):
        from features.actions import system_control
        with mock.patch.object(system_control, '_zaten_acik_mi', return_value=True), \
             mock.patch.object(system_control, '_uyg_bul_ve_ac',
                               return_value=(True, "🚀 **Spotify** başlatılıyor...")) as ac:
            basarili, mesaj = system_control.uyg_bul_ve_ac("spotify")
        ac.assert_called_once()          # komut YUTULMADI
        self.assertTrue(basarili)
        self.assertIn("zaten açıktı", mesaj)

    def test_kapaliyken_normal_mesaj(self):
        from features.actions import system_control
        with mock.patch.object(system_control, '_zaten_acik_mi', return_value=False), \
             mock.patch.object(system_control, '_uyg_bul_ve_ac',
                               return_value=(True, "🚀 **Spotify** başlatılıyor...")):
            _basarili, mesaj = system_control.uyg_bul_ve_ac("spotify")
        self.assertIn("başlatılıyor", mesaj)
        self.assertNotIn("zaten", mesaj)

    def test_basarisiz_acilista_mesaj_degismez(self):
        from features.actions import system_control
        with mock.patch.object(system_control, '_zaten_acik_mi', return_value=True), \
             mock.patch.object(system_control, '_uyg_bul_ve_ac',
                               return_value=(False, "bulunamadı")):
            _basarili, mesaj = system_control.uyg_bul_ve_ac("yokapp")
        self.assertEqual(mesaj, "bulunamadı")

    def test_world_state_cokerse_acilis_bozulmaz(self):
        from features.actions import system_control
        with mock.patch('core.world_state.uygulama_calisiyor_mu',
                        side_effect=RuntimeError("psutil yok")), \
             mock.patch.object(system_control, '_uyg_bul_ve_ac',
                               return_value=(True, "🚀 başlatılıyor...")) as ac:
            basarili, _mesaj = system_control.uyg_bul_ve_ac("spotify")
        ac.assert_called_once()
        self.assertTrue(basarili)


class DurumOzetiTest(unittest.TestCase):

    def setUp(self):
        world_state.onbellegi_temizle()

    def tearDown(self):
        world_state.onbellegi_temizle()

    def test_ozet_acik_uygulamalari_listeler(self):
        with mock.patch.object(world_state.psutil, 'process_iter',
                               return_value=[_Surec('chrome.exe')]), \
             mock.patch.object(world_state, 'pil_durumu', return_value=None), \
             mock.patch.object(world_state, 'internet_var_mi', return_value=True):
            ozet = world_state.durum_ozeti()
        self.assertIn("Chrome", ozet)
        self.assertIn("İnternet: var", ozet)

    def test_ozet_pil_yoksa_satiri_atlar(self):
        with mock.patch.object(world_state.psutil, 'process_iter', return_value=[]), \
             mock.patch.object(world_state, 'pil_durumu', return_value=None), \
             mock.patch.object(world_state, 'internet_var_mi', return_value=False):
            ozet = world_state.durum_ozeti()
        self.assertNotIn("Pil", ozet)
        self.assertIn("İnternet: YOK", ozet)

    def test_ozet_pil_varsa_gosterir(self):
        with mock.patch.object(world_state.psutil, 'process_iter', return_value=[]), \
             mock.patch.object(world_state, 'pil_durumu',
                               return_value={'yuzde': 8, 'sarjda': False}), \
             mock.patch.object(world_state, 'internet_var_mi', return_value=True):
            self.assertIn("%8", world_state.durum_ozeti())


if __name__ == '__main__':
    unittest.main()


class InternetKontrolTest(unittest.TestCase):
    """
    CANLIDA YAKALANAN: ilk sürüm doğrudan 8.8.8.8:53'e bağlanmayı deniyordu ve
    bu makinede "internet YOK" dedi — oysa vardı. Ağ doğrudan IP bağlantılarını
    engelliyor, alan adı üzerinden geçiyor.

    İnternet varken "yok" demek, olmadığını söylemekten daha kötü: Ultron
    çalışan araçları denemekten vazgeçebilir.
    """

    def test_alan_adi_uzerinden_denenir(self):
        with mock.patch('socket.create_connection') as baglan:
            world_state.internet_var_mi()
        hedef = baglan.call_args[0][0][0]
        self.assertFalse(hedef.replace('.', '').isdigit(),
                         f"ham IP deneniyor ({hedef}) — filtreli ağda yanlış sonuç verir")

    def test_baglanti_varsa_true(self):
        with mock.patch('socket.create_connection'):
            self.assertTrue(world_state.internet_var_mi())

    def test_hepsi_basarisizsa_false(self):
        with mock.patch('socket.create_connection', side_effect=OSError):
            self.assertFalse(world_state.internet_var_mi())

    def test_ilki_basarisizsa_ikincisi_denenir(self):
        with mock.patch('socket.create_connection',
                        side_effect=[OSError, mock.MagicMock()]) as baglan:
            self.assertTrue(world_state.internet_var_mi())
        self.assertEqual(baglan.call_count, 2)
