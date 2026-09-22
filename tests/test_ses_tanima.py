# -*- coding: utf-8 -*-
"""
SES TANIMA — Google birincil, internet yoksa Vosk; wake word karar fonksiyonu.

Ağa ÇIKMAZ: Google tanıyıcısı ve edge-tts taklit edilir. Gerçek sesle uçtan uca
ölçüm için: python scripts/ses_testi.py (edge-tts + Google gerekir).

`GercekVoskTest` sınıfı diskteki Vosk modeli ve tests/ses_ornekleri/ altındaki
kayıtlarla ÇEVRİMDIŞI çalışır; model yoksa (git'te değil) atlanır.
"""
import json
import os
import unittest
from unittest.mock import patch

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
from features import speech


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


SES_ORNEKLERI = os.path.join(os.path.dirname(__file__), 'ses_ornekleri')
SESSIZ_PCM = b'\x00\x00' * 16000  # 1 sn sessizlik


class _SahteTanici:
    """sr.Recognizer taklidi: recognize_google önceden belirlenen şeyi yapar."""
    davranis = None

    def recognize_google(self, audio, language=None):
        d = type(self).davranis
        if isinstance(d, BaseException):
            raise d
        return d


class PcmYaziyaCevirTest(unittest.TestCase):

    def setUp(self):
        sr = speech._sr()
        self.sr = sr
        p = patch.object(sr, 'Recognizer', _SahteTanici)
        p.start()
        self.addCleanup(p.stop)

    def test_google_anlarsa_google(self):
        _SahteTanici.davranis = 'hava durumu nasıl'
        with patch.object(speech, 'vosk_yaziya_cevir') as vosk:
            self.assertEqual(speech.pcm_yaziya_cevir(SESSIZ_PCM, 16000),
                             ('hava durumu nasıl', 'google', None))
        vosk.assert_not_called()

    def test_internet_yoksa_vosk(self):
        """Eskiden bu durumda sesli komut SESSİZCE hiçbir şey yapmıyordu."""
        _SahteTanici.davranis = self.sr.RequestError('recognition connection failed')
        with patch.object(speech, 'vosk_yaziya_cevir', return_value='hava durumu nasıl'):
            self.assertEqual(speech.pcm_yaziya_cevir(SESSIZ_PCM, 16000),
                             ('hava durumu nasıl', 'vosk', None))

    def test_google_anlamadiysa_vosk_SORULMAZ(self):
        """Google'ın anlamadığı sesten Vosk'un ürettiği metin çoğunlukla uydurma komuttur."""
        _SahteTanici.davranis = self.sr.UnknownValueError()
        with patch.object(speech, 'vosk_yaziya_cevir') as vosk:
            self.assertEqual(speech.pcm_yaziya_cevir(SESSIZ_PCM, 16000),
                             (None, 'google', None))
        vosk.assert_not_called()

    def test_internet_ve_model_yoksa_sessiz_kalmaz(self):
        _SahteTanici.davranis = self.sr.RequestError('bağlantı yok')
        with patch.object(speech, 'vosk_yaziya_cevir', return_value=None), \
                patch.object(speech, 'vosk_modeli', return_value=None):
            metin, motor, hata = speech.pcm_yaziya_cevir(SESSIZ_PCM, 16000)
        self.assertIsNone(metin)
        self.assertIn('çevrimdışı model', hata)

    def test_internet_yok_model_var_ama_ses_bos(self):
        _SahteTanici.davranis = self.sr.RequestError('bağlantı yok')
        with patch.object(speech, 'vosk_yaziya_cevir', return_value=None), \
                patch.object(speech, 'vosk_modeli', return_value=object()):
            self.assertEqual(speech.pcm_yaziya_cevir(SESSIZ_PCM, 16000),
                             (None, 'vosk', None))

    def test_eski_kisa_yollar_ayni_sozlesmeyi_korur(self):
        with patch.object(speech, 'dinle_ve_yaziya_cevir_ayrintili',
                          return_value=('Chrome Aç', 'google', None)):
            self.assertEqual(speech.dinle_ve_yaziya_cevir(), 'chrome aç')
        with patch.object(speech, 'ogg_sesi_yaziya_cevir_ayrintili',
                          return_value=(None, None, 'bozuk dosya')):
            self.assertIsNone(speech.ogg_sesi_yaziya_cevir('x.ogg'))


class UyandirmaKarariTest(unittest.TestCase):
    """Karar "hey" + "ultra" ART ARDA ister. Gerekçe ve ölçüm: speech.uyandirma_sonucu_mu."""

    def _k(self, metin):
        return speech.uyandirma_sonucu_mu(json.dumps({'text': metin}))

    def test_hey_ultra_uyandirir(self):
        self.assertTrue(self._k('hey ultra'))
        self.assertTrue(self._k('[unk] hey ultra'))
        self.assertTrue(self._k('hey ultra [unk] hey'))

    def test_tek_basina_ultra_ARTIK_uyandirmaz(self):
        """16 Eyl ölçümü: "dolar kaç lira" sesi tek başına "ultra" çıkıyordu."""
        self.assertFalse(self._k('ultra'))
        self.assertFalse(self._k('[unk] ultra'))

    def test_sira_ve_bitisiklik_onemli(self):
        self.assertFalse(self._k('ultra hey'))
        self.assertFalse(self._k('hey [unk] ultra'))
        self.assertFalse(self._k('hey'))

    def test_bozuk_ve_bos_sonuclar(self):
        for sonuc in ('{"text": ""}', '{"text": "[unk] [unk]"}', '{}', '', 'bozuk json'):
            with self.subTest(sonuc=sonuc):
                self.assertFalse(speech.uyandirma_sonucu_mu(sonuc))


class SesliYanitDosyasiTest(unittest.TestCase):

    def test_bos_metin_dosya_uretmez(self):
        self.assertIsNone(speech.sesli_yanit_dosyasi_uret(''))
        self.assertIsNone(speech.sesli_yanit_dosyasi_uret('🎙️ **  **'))

    def test_edge_tts_ulasilamazsa_none(self):
        class _Bozuk:
            def __init__(self, *a, **k):
                pass

            async def save(self, yol):
                raise ConnectionError('edge-tts yok')

        with patch('edge_tts.Communicate', _Bozuk):
            self.assertIsNone(speech.sesli_yanit_dosyasi_uret('Hava 20 derece.'))


def _vosk_hazir_mi():
    return os.path.isdir(speech.VOSK_MODEL_YOLU) and os.path.isdir(SES_ORNEKLERI)


@unittest.skipUnless(_vosk_hazir_mi(), 'Vosk modeli (models/vosk-tr) ya da ses örnekleri yok')
class GercekVoskTest(unittest.TestCase):
    """Gerçek model + gerçek ses — çevrimdışı ve deterministik.

    Kayıtlar scripts/ses_testi.py --ornek-kaydet ile edge-tts'ten üretildi
    (16 kHz mono 16-bit WAV). Beklentiler o gün ÖLÇÜLEN davranıştır.
    """

    @staticmethod
    def _pcm(ad):
        import soundfile as sf
        data, rate = sf.read(os.path.join(SES_ORNEKLERI, ad), dtype='int16')
        return data.tobytes(), rate

    def _uyandirir_mi(self, ad):
        """WakeWordThread'in döngüsünün aynısı: 0,5 sn'lik parçalar + AcceptWaveform."""
        pcm, rate = self._pcm(ad)
        pcm += b'\x00\x00' * rate           # kayıt sonrası sessizlik (canlı akışta hep var)
        rec = speech.uyandirma_tanicisi(speech.vosk_modeli(), rate)
        adim = rate                         # 0,5 sn × 2 bayt
        for i in range(0, len(pcm), adim):
            if rec.AcceptWaveform(pcm[i:i + adim]) and speech.uyandirma_sonucu_mu(rec.Result()):
                return True
        return False

    def test_hey_ultron_uyandirir(self):
        self.assertTrue(self._uyandirir_mi('hey_ultron.wav'))

    def test_siradan_komut_uyandirmaz(self):
        self.assertFalse(self._uyandirir_mi('hava_durumu_nasil.wav'))

    def test_dolar_kac_lira_ARTIK_uyandirmaz(self):
        """Eski kuralla bu kayıt uyandırıyordu (Vosk "ultra" duyuyor) — kilit."""
        pcm, rate = self._pcm('dolar_kac_lira.wav')
        pcm += b'\x00\x00' * rate
        rec = speech.uyandirma_tanicisi(speech.vosk_modeli(), rate)
        duyulanlar = []
        for i in range(0, len(pcm), rate):
            if rec.AcceptWaveform(pcm[i:i + rate]):
                duyulanlar.append(json.loads(rec.Result()).get('text', ''))
        self.assertIn('ultra', ' '.join(duyulanlar),
                      'Kayıt artık "ultra" üretmiyor — test amacını yitirdi, örneği yenile')
        self.assertFalse(self._uyandirir_mi('dolar_kac_lira.wav'))

    def test_cevrimdisi_serbest_tanima(self):
        pcm, rate = self._pcm('hava_durumu_nasil.wav')
        self.assertEqual(speech.vosk_yaziya_cevir(pcm, rate), 'hava durumu nasıl')


if __name__ == '__main__':
    unittest.main()
