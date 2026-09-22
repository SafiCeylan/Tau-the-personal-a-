# -*- coding: utf-8 -*-
"""
LLM GECİKME KİLİTLERİ — modeli bellekte tutma + niyet önbelleği.

ÖLÇÜLEN (21 Eyl 2026, RTX 3050 4 GB):
  • qwen2.5:7b soğuk yükleme 11,7 sn / qwen2.5:3b 2,8 sn. Ollama varsayılanı
    modeli 5 dakika sonra bellekten atar → arada bir konuşan kullanıcı her
    seferinde bu bedeli öder. `keep_alive` bu yüzden HER çağrıda gider.
  • Niyet çözümü (regex kaçırınca çalışır) 7b ile ~2,2 sn ve cevabın ilk
    harfinden ÖNCE ödenir. Token tavanı ve JSON zorlaması ölçülebilir bir hız
    kazandırmadı (çıktı zaten kısa); kazanç ÖNBELLEKTE — tekrar 0 ms.

Bu dosya ağa çıkmaz: `requests` taklit edilir.
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from features import llm_intent, ollama


class _SahteAkis:
    """requests.post(...) bağlam yöneticisi taklidi (stream=True)."""

    def __init__(self, satirlar):
        self.satirlar = satirlar

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        for s in self.satirlar:
            yield json.dumps(s).encode('utf-8')


def _sahte_cevap(govde):
    c = MagicMock()
    c.json.return_value = govde
    c.raise_for_status.return_value = None
    return c


class KeepAliveTest(unittest.TestCase):

    def test_akis_modeli_bellekte_tutar(self):
        satirlar = [{'message': {'content': 'merhaba'}}, {'done': True}]
        with patch.object(ollama.requests, 'post', return_value=_SahteAkis(satirlar)) as post:
            ollama.ollama_chat_stream('selam', model='qwen2.5:7b')
        self.assertEqual(post.call_args.kwargs['json']['keep_alive'],
                         ollama.VARSAYILAN_KEEP_ALIVE)

    def test_uretim_modeli_bellekte_tutar(self):
        with patch.object(ollama.requests, 'post',
                          return_value=_sahte_cevap({'response': 'ok'})) as post:
            ollama.ollama_generate('selam')
        self.assertEqual(post.call_args.kwargs['json']['keep_alive'],
                         ollama.VARSAYILAN_KEEP_ALIVE)

    def test_planner_json_modeli_bellekte_tutar(self):
        with patch.object(ollama.requests, 'post',
                          return_value=_sahte_cevap({'response': '{}'})) as post:
            ollama.ollama_json('plan', {'type': 'object'})
        self.assertEqual(post.call_args.kwargs['json']['keep_alive'],
                         ollama.VARSAYILAN_KEEP_ALIVE)

    def test_config_ile_kisaltilabilir(self):
        """Belleği sıkışan makine süreyi düşürebilmeli."""
        with patch.object(ollama.requests, 'post',
                          return_value=_sahte_cevap({'response': 'ok'})) as post:
            ollama.ollama_generate('selam', keep_alive='2m')
        self.assertEqual(post.call_args.kwargs['json']['keep_alive'], '2m')

    def test_token_tavani_ve_bicim_gonderilir(self):
        with patch.object(ollama.requests, 'post',
                          return_value=_sahte_cevap({'response': '{}'})) as post:
            ollama.ollama_generate('selam', num_predict=64, bicim='json')
        govde = post.call_args.kwargs['json']
        self.assertEqual(govde['options']['num_predict'], 64)
        self.assertEqual(govde['format'], 'json')


class DusunmeModuTest(unittest.TestCase):
    """`think` alanı istenmedikçe gönderilmez — gerekçe: ollama.dusunme_alani."""

    def test_varsayilan_olarak_ALAN_GONDERILMEZ(self):
        for model in ('qwen3:4b', 'qwen2.5:7b', 'deepseek-r1:7b', ''):
            with self.subTest(model=model):
                self.assertEqual(ollama.dusunme_alani(model), {})

    def test_config_acikca_belirtirse_gonderilir(self):
        self.assertEqual(ollama.dusunme_alani('qwen3:4b', False), {'think': False})
        self.assertEqual(ollama.dusunme_alani('qwen3:4b', True), {'think': True})

    def test_akista_govdeye_girer(self):
        satirlar = [{'message': {'content': 'selam'}}, {'done': True}]
        with patch.object(ollama.requests, 'post', return_value=_SahteAkis(satirlar)) as post:
            ollama.ollama_chat_stream('selam', model='qwen3:4b', dusunme=False)
        self.assertIs(post.call_args.kwargs['json']['think'], False)

    def test_istenmedikce_govdede_yok(self):
        satirlar = [{'message': {'content': 'selam'}}, {'done': True}]
        with patch.object(ollama.requests, 'post', return_value=_SahteAkis(satirlar)) as post:
            ollama.ollama_chat_stream('selam', model='qwen3:4b')
        self.assertNotIn('think', post.call_args.kwargs['json'])


class NiyetOnbellegiTest(unittest.TestCase):

    def setUp(self):
        llm_intent.onbellegi_temizle()
        self.cfg = {'ollama_url': 'http://127.0.0.1:11434', 'ollama_model': 'qwen2.5:7b'}

    def tearDown(self):
        llm_intent.onbellegi_temizle()

    def _yama(self, cevap='{"intent":"PLAY_MUSIC","sarki":"motivasyon"}'):
        return patch.object(ollama, 'ollama_generate', return_value=(cevap, None))

    def test_ayni_cumle_ikinci_kez_LLM_e_GITMEZ(self):
        with self._yama() as uret:
            ilk = llm_intent.llm_intent_coz('motivasyon şarkısı koy', self.cfg)
            ikinci = llm_intent.llm_intent_coz('Motivasyon Şarkısı Koy', self.cfg)
        self.assertEqual(ilk, ikinci)
        self.assertEqual(uret.call_count, 1, 'önbellek çalışmadı')

    def test_sonuc_dogru_cozulur(self):
        with self._yama():
            self.assertEqual(llm_intent.llm_intent_coz('şarkı koy', self.cfg),
                             ('PLAY_MUSIC', {'song_title': 'motivasyon'}))

    def test_model_degisince_yeniden_sorulur(self):
        """Eski modelin sınıflandırması yeni model için geçerli sayılamaz."""
        with self._yama() as uret:
            llm_intent.llm_intent_coz('şarkı koy', self.cfg)
            llm_intent.llm_intent_coz('şarkı koy', dict(self.cfg, ollama_model='qwen3:4b'))
        self.assertEqual(uret.call_count, 2)

    def test_sonucsuz_cevap_da_onbelleklenir(self):
        """Model çöp ürettiyse aynı cümle için tekrar tekrar beklemenin anlamı yok."""
        with self._yama('bu json değil') as uret:
            self.assertIsNone(llm_intent.llm_intent_coz('anlamsız', self.cfg))
            self.assertIsNone(llm_intent.llm_intent_coz('anlamsız', self.cfg))
        self.assertEqual(uret.call_count, 1)

    def test_onbellek_sinirsiz_buyumez(self):
        with self._yama():
            for i in range(llm_intent._ONBELLEK_TAVANI + 5):
                llm_intent.llm_intent_coz(f'cümle {i}', self.cfg)
        self.assertLessEqual(len(llm_intent._ONBELLEK), llm_intent._ONBELLEK_TAVANI)

    def test_cagri_kisa_ve_deterministik(self):
        with self._yama() as uret:
            llm_intent.llm_intent_coz('şarkı koy', self.cfg)
        k = uret.call_args.kwargs
        self.assertEqual(k['temperature'], 0)
        self.assertEqual(k['num_predict'], llm_intent._AZAMI_TOKEN)
        self.assertEqual(k['bicim'], 'json')


if __name__ == '__main__':
    unittest.main()
