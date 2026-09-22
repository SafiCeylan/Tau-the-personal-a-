# -*- coding: utf-8 -*-
"""
MİKROFON SEÇİMİ — hoparlör kaydı mikrofon sayılmaz, aygıt adıyla çözülür.

Aygıt adları bu makinede 16 Eyl 2026'da ÖLÇÜLEN MME listesinden alındı
(adlar Windows tarafından 31 karakterde kesiliyor). O gün config'teki
`mic_device_index: 1` "Stereo Karışımı"nı gösteriyordu ve wake word
kullanıcıyı hiç duymuyordu.
"""
import unittest
from unittest.mock import patch

from features import mic_devices as md

# 16 Eyl ölçümü — sounddevice MME giriş aygıtları
OLCULEN_AYGITLAR = [
    (0, 'Microsoft Ses Eşleştiricisi - Input'),
    (1, 'Stereo Karışımı (Realtek(R) Aud'),
    (2, 'Mikrofon Dizisi (Realtek(R) Aud'),
]


class MikrofonMuTest(unittest.TestCase):

    def test_stereo_karisimi_mikrofon_degil(self):
        self.assertFalse(md.mikrofon_mu('Stereo Karışımı (Realtek(R) Aud'))
        self.assertTrue(md.hoparlor_kaydi_mi('Stereo Karışımı (Realtek(R) Aud'))

    def test_ingilizce_windows_adlari(self):
        self.assertFalse(md.mikrofon_mu('Stereo Mix (Realtek High Definition Audio)'))
        self.assertFalse(md.mikrofon_mu('Speakers (Realtek(R) Audio)'))
        self.assertTrue(md.mikrofon_mu('Microphone Array (Realtek(R) Audio)'))

    def test_buyuk_harfli_turkce_ad(self):
        """'KARIŞIMI'.lower() → 'karişimi' (i noktalı) — sade() bunu da yakalamalı."""
        self.assertTrue(md.hoparlor_kaydi_mi('STEREO KARIŞIMI'))

    def test_gercek_mikrofonlar(self):
        for ad in ('Mikrofon Dizisi (Realtek(R) Aud',
                   'Kulaklık (Philips TAH4205 Hands-Free)',
                   'Mikrofon (Wireless Controller)'):
            with self.subTest(ad=ad):
                self.assertTrue(md.mikrofon_mu(ad))

    def test_ses_eslestiricisi_varsayilanin_takma_adi(self):
        ad = 'Microsoft Ses Eşleştiricisi - Input'
        self.assertFalse(md.mikrofon_mu(ad))       # listede ikinci kez gösterilmez
        self.assertFalse(md.hoparlor_kaydi_mi(ad))  # ama uyarı da gerektirmez

    def test_bos_ad(self):
        self.assertFalse(md.mikrofon_mu(''))
        self.assertFalse(md.mikrofon_mu(None))


class AygitCozTest(unittest.TestCase):

    def test_16_eyl_hatasi_numara_1_hoparlor_kaydi(self):
        """Eski config: yalnız numara, o numara Stereo Karışımı → varsayılan + UYARI."""
        no, uyari = md.aygit_coz(OLCULEN_AYGITLAR, ad=None, indeks=1)
        self.assertIsNone(no)
        self.assertIn('mikrofon değil', uyari)
        self.assertIn('Stereo Karışımı', uyari)

    def test_ad_numaradan_once_gelir(self):
        """Numara kaymış olsa bile ad doğru aygıtı bulur."""
        kaymis = [(0, 'Microsoft Ses Eşleştiricisi - Input'),
                  (1, 'Kulaklık (Philips TAH4205 Hands'),
                  (2, 'Stereo Karışımı (Realtek(R) Aud'),
                  (3, 'Mikrofon Dizisi (Realtek(R) Aud')]
        no, uyari = md.aygit_coz(kaymis, ad='Mikrofon Dizisi (Realtek(R) Aud', indeks=2)
        self.assertEqual(no, 3)
        self.assertIsNone(uyari)

    def test_kayitli_ad_bagli_degilse_varsayilan_ve_bildirim(self):
        no, uyari = md.aygit_coz(OLCULEN_AYGITLAR, ad='Kulaklık (Philips TAH4205 Hands')
        self.assertIsNone(no)
        self.assertIn('bağlı değil', uyari)

    def test_adla_kaydedilmis_hoparlor_kaydi_da_reddedilir(self):
        no, uyari = md.aygit_coz(OLCULEN_AYGITLAR, ad='Stereo Karışımı (Realtek(R) Aud')
        self.assertIsNone(no)
        self.assertIn('mikrofon değil', uyari)

    def test_gecerli_numara(self):
        self.assertEqual(md.aygit_coz(OLCULEN_AYGITLAR, indeks=2), (2, None))

    def test_varsayilan_isaretleri_sessiz(self):
        for indeks in (None, -1, '', 'bozuk'):
            with self.subTest(indeks=indeks):
                self.assertEqual(md.aygit_coz(OLCULEN_AYGITLAR, indeks=indeks), (None, None))

    def test_ses_eslestiricisi_secilmisse_sessizce_varsayilan(self):
        self.assertEqual(md.aygit_coz(OLCULEN_AYGITLAR, indeks=0), (None, None))

    def test_olmayan_numara(self):
        no, uyari = md.aygit_coz(OLCULEN_AYGITLAR, indeks=9)
        self.assertIsNone(no)
        self.assertIn('#9', uyari)


class MikrofonSecTest(unittest.TestCase):

    def test_liste_okunamazsa_eski_davranis(self):
        """Koruma katmanı bozulursa ses tamamen kesilmesin: config numarası kullanılır."""
        with patch.object(md, 'giris_aygitlari', side_effect=OSError('PortAudio yok')):
            self.assertEqual(md.mikrofon_sec({'mic_device_index': 2}), (2, None))
            self.assertEqual(md.mikrofon_sec({'mic_device_index': -1}), (None, None))

    def test_windows_varsayilani_da_hoparlor_kaydiysa_uyarir(self):
        with patch.object(md, 'giris_aygitlari', return_value=OLCULEN_AYGITLAR), \
                patch.object(md, '_varsayilan_giris_adi',
                             return_value='Stereo Karışımı (Realtek(R) Aud'):
            no, uyari = md.mikrofon_sec({'mic_device_index': -1})
        self.assertIsNone(no)
        self.assertIn('varsayılan kayıt aygıtı', uyari)

    def test_bugunku_duzeltilmis_config(self):
        cfg = {'mic_device_index': 2, 'mic_device_name': 'Mikrofon Dizisi (Realtek(R) Aud'}
        with patch.object(md, 'giris_aygitlari', return_value=OLCULEN_AYGITLAR):
            self.assertEqual(md.mikrofon_sec(cfg), (2, None))

    def test_listeleme_hoparlor_kaydini_ve_takma_adi_gizler(self):
        with patch.object(md, 'giris_aygitlari', return_value=OLCULEN_AYGITLAR):
            self.assertEqual(md.mikrofonlari_listele(),
                             [(2, 'Mikrofon Dizisi (Realtek(R) Aud')])


class SeviyeYorumlaTest(unittest.TestCase):

    def test_esikler(self):
        self.assertEqual(md.seviye_yorumla(0.25)[0], 'iyi')
        self.assertEqual(md.seviye_yorumla(0.10)[0], 'iyi')
        self.assertEqual(md.seviye_yorumla(0.05)[0], 'zayif')
        self.assertEqual(md.seviye_yorumla(0.0)[0], 'yok')

    def test_aralik_disi_ve_bozuk_girdi_cokertmez(self):
        self.assertEqual(md.seviye_yorumla(3.0)[0], 'iyi')
        self.assertEqual(md.seviye_yorumla(-1)[0], 'yok')
        self.assertEqual(md.seviye_yorumla(None)[0], 'yok')


if __name__ == '__main__':
    unittest.main()
