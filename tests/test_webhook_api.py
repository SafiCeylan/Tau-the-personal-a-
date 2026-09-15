# -*- coding: utf-8 -*-
"""
YEREL WEBHOOK API — GÜVENLİK KAPILARI.

Bu sunucu Ultron'a KOMUT ÇALIŞTIRIR. İlk sürümünde hiçbir kimlik doğrulaması
yoktu ve bu yüzden canlıya hiç bağlanmadı. Aşağıdaki testler üç kapının da
gerçekten kapalı olduğunu kilitler:

  • TOKEN            — tokensiz/yanlış tokenli istek 401
  • CONTENT-TYPE     — `application/json` değilse 415 (HTML formu bu türü
                       gönderemez → form tabanlı CSRF buradan geçemez)
  • ORIGIN / REFERER — tarayıcıdan gelen istek 403 (bir web sayfası
                       `fetch(..., {mode:"no-cors"})` ile cevabı OKUYAMAZ ama
                       İSTEĞİ gönderebilir; Origin başlığı onu ele verir)

Ayrıca sunucunun token olmadan HİÇ BAŞLAMADIĞI test ediliyor — "kimlik
doğrulaması olmadan da çalışsın" kaçış yolu bilerek yok.
"""
import json
import unittest
import urllib.error
import urllib.request

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
import features.webhook_api as api


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class SahteMotor:
    """engine.process taklidi — gerçek motoru çalıştırmadan uçları test eder."""

    def __init__(self):
        self.cagrilar = []

    def process(self, komut, allow_llm=False, kanal='webhook'):
        self.cagrilar.append((komut, kanal))

        class Ctx:
            intent = 'TIME_DATE'
            final_output = 'Saat 12:00'
            response = 'Saat 12:00'
            execution_success = True
            security_level = 'SAFE'
        return Ctx()


class SahteRiskliMotor(SahteMotor):
    def process(self, komut, allow_llm=False, kanal='webhook'):
        super().process(komut, allow_llm, kanal)

        class Ctx:
            intent = 'WHATSAPP_MESSAGE'
            final_output = 'Onay bekleniyor'
            response = 'Onay bekleniyor'
            execution_success = False
            security_level = 'CONFIRM'
        return Ctx()


GECERLI_TOKEN = 'test-token-yeterince-uzun-123456'


def _istek(port, yol='/api/status', yontem='GET', govde=None, basliklar=None):
    """(status_code, json) döner. Hata kodlarında da gövdeyi okur."""
    url = f'http://127.0.0.1:{port}{yol}'
    veri = json.dumps(govde).encode('utf-8') if govde is not None else None
    req = urllib.request.Request(url, data=veri, method=yontem)
    for k, v in (basliklar or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {}


class WebhookGuvenlikTest(unittest.TestCase):

    port = 8971

    @classmethod
    def setUpClass(cls):
        cls.motor = SahteMotor()
        basladi = api.start_webhook_server(
            host='127.0.0.1', port=cls.port, engine=cls.motor, token=GECERLI_TOKEN)
        if not basladi:
            raise unittest.SkipTest('webhook sunucusu baslatilamadi (port dolu olabilir)')

    @classmethod
    def tearDownClass(cls):
        api.stop_webhook_server()

    # ---------------- TOKEN ----------------

    def test_tokensiz_istek_reddedilir(self):
        kod, _ = _istek(self.port)
        self.assertEqual(kod, 401)

    def test_yanlis_token_reddedilir(self):
        kod, _ = _istek(self.port, basliklar={'X-Ultron-Token': 'yanlis-token-123456'})
        self.assertEqual(kod, 401)

    def test_dogru_token_gecer(self):
        kod, veri = _istek(self.port, basliklar={'X-Ultron-Token': GECERLI_TOKEN})
        self.assertEqual(kod, 200)
        self.assertEqual(veri.get('status'), 'online')

    def test_bearer_basligi_da_kabul_edilir(self):
        kod, _ = _istek(self.port,
                        basliklar={'Authorization': f'Bearer {GECERLI_TOKEN}'})
        self.assertEqual(kod, 200)

    # ---------------- ORIGIN / REFERER (CSRF) ----------------

    def test_origin_tasiyan_istek_dogru_tokenle_bile_reddedilir(self):
        """Zararlı web sayfası senaryosu: token sızmış olsa BİLE geçmemeli."""
        kod, _ = _istek(self.port, basliklar={
            'X-Ultron-Token': GECERLI_TOKEN,
            'Origin': 'https://zararli-site.example',
        })
        self.assertEqual(kod, 403)

    def test_referer_tasiyan_istek_reddedilir(self):
        kod, _ = _istek(self.port, basliklar={
            'X-Ultron-Token': GECERLI_TOKEN,
            'Referer': 'https://zararli-site.example/sayfa',
        })
        self.assertEqual(kod, 403)

    # ---------------- CONTENT-TYPE (form CSRF) ----------------

    def test_form_content_type_reddedilir(self):
        """HTML formu yalnız bu türleri gönderebilir — kapı burada kapanmalı."""
        for tur in ('application/x-www-form-urlencoded',
                    'multipart/form-data',
                    'text/plain'):
            with self.subTest(tur=tur):
                kod, _ = _istek(self.port, '/api/command', 'POST',
                                govde={'command': 'saat kaç'},
                                basliklar={'X-Ultron-Token': GECERLI_TOKEN,
                                           'Content-Type': tur})
                self.assertEqual(kod, 415, f'{tur} geçti — CSRF kapısı açık!')

    def test_json_content_type_gecer(self):
        kod, veri = _istek(self.port, '/api/command', 'POST',
                           govde={'command': 'saat kaç'},
                           basliklar={'X-Ultron-Token': GECERLI_TOKEN,
                                      'Content-Type': 'application/json'})
        self.assertEqual(kod, 200)
        self.assertEqual(veri.get('intent'), 'TIME_DATE')
        self.assertTrue(veri.get('success'))

    # ---------------- gövde doğrulama ----------------

    def test_bos_komut_reddedilir(self):
        kod, _ = _istek(self.port, '/api/command', 'POST', govde={'command': '   '},
                        basliklar={'X-Ultron-Token': GECERLI_TOKEN,
                                   'Content-Type': 'application/json'})
        self.assertEqual(kod, 400)

    def test_bozuk_json_reddedilir(self):
        req = urllib.request.Request(
            f'http://127.0.0.1:{self.port}/api/command',
            data=b'{bozuk json', method='POST')
        req.add_header('X-Ultron-Token', GECERLI_TOKEN)
        req.add_header('Content-Type', 'application/json')
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail('bozuk JSON kabul edildi')
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_bilinmeyen_uc_404(self):
        kod, _ = _istek(self.port, '/api/herhangi',
                        basliklar={'X-Ultron-Token': GECERLI_TOKEN})
        self.assertEqual(kod, 404)

    def test_yetkisiz_istek_motoru_HIC_calistirmaz(self):
        """En önemlisi: reddedilen istek Ultron'a iş yaptırmamalı."""
        onceki = len(self.motor.cagrilar)
        _istek(self.port, '/api/command', 'POST', govde={'command': 'chrome aç'})
        _istek(self.port, '/api/command', 'POST', govde={'command': 'chrome aç'},
               basliklar={'X-Ultron-Token': 'yanlis', 'Content-Type': 'application/json'})
        _istek(self.port, '/api/command', 'POST', govde={'command': 'chrome aç'},
               basliklar={'X-Ultron-Token': GECERLI_TOKEN,
                          'Content-Type': 'application/json',
                          'Origin': 'https://zararli.example'})
        self.assertEqual(len(self.motor.cagrilar), onceki,
                         'yetkisiz istek motoru çalıştırdı!')


class WebhookOnayKapisiTest(unittest.TestCase):
    """Riskli komut onay kartında durur — çağıran bunu BİLMELİ."""

    port = 8972

    @classmethod
    def setUpClass(cls):
        cls.motor = SahteRiskliMotor()
        if not api.start_webhook_server(host='127.0.0.1', port=cls.port,
                                        engine=cls.motor, token=GECERLI_TOKEN):
            raise unittest.SkipTest('webhook sunucusu baslatilamadi')

    @classmethod
    def tearDownClass(cls):
        api.stop_webhook_server()

    def test_riskli_komut_onay_bekliyor_isaretlenir(self):
        kod, veri = _istek(self.port, '/api/command', 'POST',
                           govde={'command': 'anneme mesaj gönder'},
                           basliklar={'X-Ultron-Token': GECERLI_TOKEN,
                                      'Content-Type': 'application/json'})
        self.assertEqual(kod, 200)
        self.assertTrue(veri.get('onay_bekliyor'),
                        'riskli komut "onay_bekliyor" işareti olmadan döndü — '
                        'çağıran işin yapıldığını sanar')
        self.assertFalse(veri.get('success'))


class WebhookBaslatmaKapisiTest(unittest.TestCase):
    """Token yoksa sunucu HİÇ başlamamalı."""

    def tearDown(self):
        api.stop_webhook_server()

    def test_tokensiz_baslatilmaz(self):
        self.assertFalse(
            api.start_webhook_server(host='127.0.0.1', port=8973, engine=SahteMotor(),
                                     token=''))
        self.assertFalse(api.calisiyor_mu())

    def test_kisa_token_reddedilir(self):
        self.assertFalse(
            api.start_webhook_server(host='127.0.0.1', port=8974, engine=SahteMotor(),
                                     token='kisa'))
        self.assertFalse(api.calisiyor_mu())

    def test_disa_acik_host_reddedilir(self):
        """0.0.0.0'a bağlanmak bu sunucuyu tüm ağa açardı."""
        self.assertFalse(
            api.start_webhook_server(host='0.0.0.0', port=8975, engine=SahteMotor(),
                                     token=GECERLI_TOKEN))
        self.assertFalse(api.calisiyor_mu())

    def test_uretilen_token_yeterince_uzun(self):
        for _ in range(5):
            self.assertGreaterEqual(len(api.token_uret()), api.ASGARI_TOKEN_UZUNLUGU)


if __name__ == '__main__':
    unittest.main()
