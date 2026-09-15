# -*- coding: utf-8 -*-
import unittest
import urllib.request
import urllib.error
import json
import time
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
import features.webhook_api as api

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()

class TestWebhookAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_engine = mock.MagicMock()
        cls.mock_ctx = mock.MagicMock()
        cls.mock_ctx.final_output = "Test cevabi"
        cls.mock_ctx.intent = "TIME_DATE"
        cls.mock_ctx.execution_success = True
        cls.mock_engine.process.return_value = cls.mock_ctx
        
        # Rastgele bosta bir port kullanalim
        cls.port = 8898
        api.start_webhook_server(host='127.0.0.1', port=cls.port, engine=cls.mock_engine)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        api.stop_webhook_server()

    def test_get_status(self):
        url = f"http://127.0.0.1:{self.port}/api/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertEqual(data["status"], "online")

    def test_post_command_success(self):
        url = f"http://127.0.0.1:{self.port}/api/command"
        payload = json.dumps({"command": "saat kaç"}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(data["success"])
            self.assertEqual(data["intent"], "TIME_DATE")
            self.assertEqual(data["response"], "Test cevabi")

    def test_post_command_invalid_json(self):
        url = f"http://127.0.0.1:{self.port}/api/command"
        req = urllib.request.Request(url, data=b"invalid json", headers={'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)

if __name__ == "__main__":
    unittest.main()
