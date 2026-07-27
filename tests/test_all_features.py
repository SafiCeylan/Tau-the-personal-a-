"""
Ultron AI System — Massive Exhaustive Integration & Edge-Case Test Suite (30+ Scenarios)
Tests natural language variations, percentages, edge cases, process management, search intents,
file reading, reminders, and security safeguards.
"""

import sys
import os
import unittest
from datetime import datetime

# Add root folder to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from features.actions.system_control import sistem_komutu_algila, sistem_durumu_raporu
from features.reminders import hatirlatma_algila
from features.web_search import canli_web_ara, web_arama_niyeti_algila
from features.file_reader import dosya_oku_ve_analiz_et, dosya_okuma_niyeti_algila


class TestUltronExhaustiveSuite(unittest.TestCase):

    # =========================================================================
    # KATEGORİ 1: Ses Kontrolü & Yüzde Varyasyonları (Volume Edge Cases)
    # =========================================================================

    def test_volume_percent_lowercase_symbol(self):
        """'sesi %50 kadar kıs'"""
        status, resp = sistem_komutu_algila("sesi %50 kadar kıs")
        self.assertTrue(status)

    def test_volume_percent_word_yuzde(self):
        """'sesi yüzde 30 artır'"""
        status, resp = sistem_komutu_algila("sesi yüzde 30 artır")
        self.assertTrue(status)

    def test_volume_percent_trailing(self):
        """'volume 40% düşür'"""
        status, resp = sistem_komutu_algila("volume 40% düşür")
        self.assertTrue(status)

    def test_volume_percent_set(self):
        """'ses seviyesini %80 yap'"""
        status, resp = sistem_komutu_algila("ses seviyesini %80 yap")
        self.assertTrue(status)
        self.assertIn("%80", resp)

    def test_volume_mute_phrasings(self):
        """'sesi tamamen kapat' / 'sessize al'"""
        status1, resp1 = sistem_komutu_algila("sesi tamamen kapat")
        self.assertTrue(status1)
        self.assertTrue("sessiz" in resp1.lower())

        status2, resp2 = sistem_komutu_algila("sessize al")
        self.assertTrue(status2)
        self.assertTrue("sessiz" in resp2.lower())

    def test_volume_increase_phrasings(self):
        """'sesi biraz yükselt'"""
        status, resp = sistem_komutu_algila("sesi biraz yükselt")
        self.assertTrue(status)
        self.assertTrue("yükseltildi" in resp or "artırıldı" in resp)

    def test_youtube_music_song_play(self):
        """'youtube music'ten Barış Manço Dönence çal'"""
        status, resp = sistem_komutu_algila("youtube music'ten Barış Manço Dönence çal")
        self.assertTrue(status)
        self.assertIn("YouTube Music", resp)
        self.assertIn("Barış Manço", resp)

    # =========================================================================
    # KATEGORİ 2: Uygulama & Süreç Yönetimi (App & Process Management)
    # =========================================================================

    def test_app_launch_calculator(self):
        """'hesap makinesi aç'"""
        status, resp = sistem_komutu_algila("hesap makinesi aç")
        self.assertTrue(status)
        self.assertIn("başlatılıyor", resp)

    def test_app_launch_notepad(self):
        """'not defteri çalıştır'"""
        status, resp = sistem_komutu_algila("not defteri çalıştır")
        self.assertTrue(status)
        self.assertIn("başlatılıyor", resp)

    def test_app_launch_chrome(self):
        """'chrome başlat'"""
        status, resp = sistem_komutu_algila("chrome başlat")
        self.assertTrue(status)
        self.assertIn("Chrome", resp)

    def test_app_kill_chrome(self):
        """'chrome kapat'"""
        status, resp = sistem_komutu_algila("chrome kapat")
        self.assertTrue(status)
        self.assertIn("Chrome", resp)

    def test_app_kill_spotify(self):
        """'spotify sonlandır'"""
        status, resp = sistem_komutu_algila("spotify sonlandır")
        self.assertTrue(status)
        self.assertIn("Spotify", resp)

    # =========================================================================
    # KATEGORİ 3: Sistem Telemetrisi & Güvenlik (System Telemetry & Security)
    # =========================================================================

    def test_system_status_full(self):
        """'sistem durumunu göster'"""
        status, resp = sistem_komutu_algila("sistem durumunu göster")
        self.assertTrue(status)
        self.assertIn("CPU Yükü", resp)
        self.assertIn("RAM Kullanımı", resp)
        self.assertIn("Disk Boş Alan", resp)

    def test_system_ram_query(self):
        """'ram kullanımı ve bellek durumu nasıl'"""
        status, resp = sistem_komutu_algila("ram kullanımı ve bellek durumu nasıl")
        self.assertTrue(status)
        self.assertIn("RAM Kullanımı", resp)

    def test_security_shutdown_safeguard(self):
        """'bilgisayarı kapat' -> Güvenlik uyarısı dönmeli"""
        is_action, resp = sistem_komutu_algila("bilgisayarı kapat")
        self.assertFalse(is_action)
        self.assertIn("evet bilgisayarı kapat", resp)

    # =========================================================================
    # KATEGORİ 4: Hatırlatıcı Doğal Dil Varyasyonları (Reminders Phrasing)
    # =========================================================================

    def test_reminder_relative_minutes(self):
        """'15 dakika sonra su içmeyi hatırlat'"""
        res = hatirlatma_algila("15 dakika sonra su içmeyi hatırlat")
        self.assertIsNotNone(res)
        self.assertEqual(res.get('tip'), 'hatirlatma')
        self.assertIn("15 dakika", res.get('detay'))

    def test_reminder_relative_hours(self):
        """'2 saat sonra toplantı var hatırlat'"""
        res = hatirlatma_algila("2 saat sonra toplantı var hatırlat")
        self.assertIsNotNone(res)
        self.assertEqual(res.get('tip'), 'hatirlatma')

    def test_reminder_special_tomorrow(self):
        """'yarın ilaç almayı hatırla'"""
        res = hatirlatma_algila("yarın ilaç almayı hatırla")
        self.assertIsNotNone(res)
        self.assertEqual(res.get('tip'), 'hatirlatma')
        self.assertIn("yarın", res.get('detay'))

    def test_reminder_query_phrasing_1(self):
        """'hatırlatmalarımı göster'"""
        res = hatirlatma_algila("hatırlatmalarımı göster")
        self.assertIsNotNone(res)
        self.assertEqual(res.get('tip'), 'gecmis_takip')

    def test_reminder_query_phrasing_2(self):
        """'hatırlatıcılarımda ne var'"""
        res = hatirlatma_algila("hatırlatıcılarımda ne var")
        self.assertIsNotNone(res)
        self.assertEqual(res.get('tip'), 'gecmis_takip')

    # =========================================================================
    # KATEGORİ 5: Canlı Web Araması Varyasyonları (Web Search Edge Cases)
    # =========================================================================

    def test_search_prefix_ara(self):
        """'ara: yapay zeka haberleri'"""
        is_search, q = web_arama_niyeti_algila("ara: yapay zeka haberleri")
        self.assertTrue(is_search)
        self.assertEqual(q, "yapay zeka haberleri")

    def test_search_prefix_internet(self):
        """'internet: dolar kaç tl'"""
        is_search, q = web_arama_niyeti_algila("internet: dolar kaç tl")
        self.assertTrue(is_search)
        self.assertEqual(q, "dolar kaç tl")

    def test_search_trigger_hava_durumu(self):
        """'bugün istanbul hava durumu'"""
        is_search, q = web_arama_niyeti_algila("bugün istanbul hava durumu")
        self.assertTrue(is_search)

    def test_search_trigger_haberler(self):
        """'en son haberler nelerdir'"""
        is_search, q = web_arama_niyeti_algila("en son haberler nelerdir")
        self.assertTrue(is_search)

    def test_search_execution_wikipedia(self):
        """Wikipedia canlı Türkçe bilgi araması"""
        success, text = canli_web_ara("Atatürk")
        self.assertTrue(success)
        self.assertIn("Wikipedia", text)

    # =========================================================================
    # KATEGORİ 6: Dosya & Kod Okuma Varyasyonları (File Reader Edge Cases)
    # =========================================================================

    def test_file_intent_oku_prefix(self):
        """'oku: README.md'"""
        is_file, path = dosya_okuma_niyeti_algila("oku: README.md")
        self.assertTrue(is_file)
        self.assertEqual(path, "README.md")

    def test_file_intent_dosya_oku_prefix(self):
        """'dosya oku: main.py'"""
        is_file, path = dosya_okuma_niyeti_algila("dosya oku: main.py")
        self.assertTrue(is_file)
        self.assertEqual(path, "main.py")

    def test_file_reader_existing_file(self):
        """Mevcut config.json dosyasını okuma"""
        success, text = dosya_oku_ve_analiz_et("config.json")
        self.assertTrue(success)
        self.assertIn("ai_provider", text)

    def test_file_reader_non_existing_file(self):
        """Olmayan bir dosyayı okuma denemesi (Hata yönetimi)"""
        success, text = dosya_oku_ve_analiz_et("olmayan_hayali_dosya_123.txt")
        self.assertFalse(success)
        self.assertIn("bulunamadı", text)

    # =========================================================================
    # KATEGORİ 7: Routine Engine & Self-Reflection Tests
    # =========================================================================

    def test_routine_engine_calisma_modu(self):
        """'çalışma modunu başlat' (Otonom çoklu adım testi)"""
        from core.engine import UltronCoreEngine
        engine = UltronCoreEngine()
        ctx = engine.process("çalışma modunu başlat")
        self.assertTrue(ctx.execution_success)
        self.assertIn("OTONOM OLARAK BAŞLATILDI", ctx.execution_result)

    def test_security_score_85_double_confirm(self):
        """'tüm süreçleri kapat' (85/100 Yüksek Risk - Çift Onay İste)"""
        from core.engine import UltronCoreEngine
        engine = UltronCoreEngine()
        ctx = engine.process("tüm süreçleri kapat")
        self.assertEqual(ctx.security_score, 85)
        self.assertEqual(ctx.security_level, "DOUBLE_CONFIRM")
        self.assertIn("ÇİFT ONAY GEREKLİ", ctx.security_message)


    def test_custom_dynamic_routine(self):
        """Özel Dinamik Mod & Rutin Oluşturma ve Tetikleme Testi"""
        from database.db_manager import DatabaseManager
        from core.engine import UltronCoreEngine
        import json

        db = DatabaseManager('bilgiler.db')
        conn = db.get_connection()
        cursor = conn.cursor()

        # Insert test mode
        actions = json.dumps(["sesi %30 yap", "sistem durumunu göster"], ensure_ascii=False)
        cursor.execute(
            "INSERT OR REPLACE INTO custom_routines (name, trigger_keyword, description, actions_json) VALUES (?, ?, ?, ?)",
            ("Test Modu", "test modunu başlat", "Test amaçlı özel rutin", actions)
        )
        conn.commit()

        engine = UltronCoreEngine(db_manager=db)
        ctx = engine.process("test modunu başlat")

        self.assertTrue(ctx.execution_success)
        self.assertIn("TEST MODU MODU OTONOM BAŞLATILDI", ctx.execution_result)


class TestMoodAnalysis(unittest.TestCase):
    """Duygu analizi: ekli hâller, olumsuzlama, emoji ve kirlilik önleme."""

    def _analiz(self, metin):
        from features.mood import ruh_hali_analiz
        return ruh_hali_analiz(metin)[0]

    def test_pozitif_ekli(self):
        self.assertEqual(self._analiz("bugün çok mutluyum"), "pozitif")

    def test_negatif_ekli(self):
        self.assertEqual(self._analiz("sürekli üzülüyorum"), "negatif")

    def test_olumsuzlama_pozitifi_cevirir(self):
        # "mutlu değilim" pozitif SAYILMAMALI — eski bugun asıl kaynağı
        self.assertEqual(self._analiz("mutlu değilim açıkçası"), "negatif")

    def test_emoji_pozitif(self):
        self.assertEqual(self._analiz("harika bir gün 😊"), "pozitif")

    def test_notr(self):
        self.assertEqual(self._analiz("bugün normal bir gündü"), "nötr")

    def test_alakasiz_belirsiz(self):
        # Komut/soru metni duygu üretmemeli (geçmişi kirletmesin)
        self.assertEqual(self._analiz("saat kaç"), "belirsiz")


class TestLLMIntent(unittest.TestCase):
    """LLM niyet çözücü: JSON ayrıştırma + doğrulama (Ollama olmadan, mock ile)."""

    def test_json_ayikla_temiz(self):
        from features.llm_intent import _json_ayikla
        self.assertEqual(_json_ayikla('{"intent":"WEATHER"}'), {"intent": "WEATHER"})

    def test_json_ayikla_gurultulu(self):
        # Model açıklama eklerse bile ilk JSON bloğu çıkarılmalı
        from features.llm_intent import _json_ayikla
        d = _json_ayikla('Tabii! İşte: {"intent":"PLAY_MUSIC","sarki":"x"} umarım yardımcı olur')
        self.assertEqual(d["intent"], "PLAY_MUSIC")

    def test_json_ayikla_bozuk(self):
        from features.llm_intent import _json_ayikla
        self.assertIsNone(_json_ayikla("hiç json yok burada"))

    def test_gecersiz_niyet_reddedilir(self):
        # Mock: model geçersiz bir etiket dönerse None dönmeli
        import features.llm_intent as li
        import features.ollama as ol
        orig = ol.ollama_generate
        ol.ollama_generate = lambda *a, **k: ('{"intent":"UÇAK_KAÇIR"}', [])
        try:
            self.assertIsNone(li.llm_intent_coz("selam", {"ollama_model": "x"}))
        finally:
            ol.ollama_generate = orig

    def test_gecerli_niyet_entity_ile(self):
        import features.llm_intent as li
        import features.ollama as ol
        orig = ol.ollama_generate
        ol.ollama_generate = lambda *a, **k: ('{"intent":"WEB_SEARCH","sorgu":"python"}', [])
        try:
            intent, ent = li.llm_intent_coz("python nedir araştır", {"ollama_model": "x"})
            self.assertEqual(intent, "WEB_SEARCH")
            self.assertEqual(ent["search_query"], "python")
        finally:
            ol.ollama_generate = orig


class TestMemoryRAG(unittest.TestCase):
    """Alaka-sıralı hafıza erişimi (RAG) — doğru kaydı yüzeye çıkarır."""

    HAFIZALAR = [
        ('en sevdiğim renk', 'lacivert', 'Genel'),
        ('arabam', 'Volkswagen Golf 2018', 'Genel'),
        ('en sevdiğim yemek', 'mantı', 'Genel'),
        ('evcil hayvan', 'Boncuk adında kedi', 'Genel'),
    ]

    def _ilk(self, soru):
        from features.memory_rag import alakali_hafizalar
        r = alakali_hafizalar(soru, self.HAFIZALAR, {}, k=1)
        return r[0] if r else None

    def test_dogrudan_eslesme(self):
        self.assertIn("Volkswagen", self._ilk("benim arabam ne marka"))

    def test_turkce_cekim_eslesme(self):
        # "kedimin" → "kedi" ön-ek eşleşmesi
        self.assertIn("Boncuk", self._ilk("kedimin adı ne"))

    def test_bos_hafiza(self):
        from features.memory_rag import alakali_hafizalar
        self.assertEqual(alakali_hafizalar("herhangi", [], {}), [])

    def test_alakasizda_geri_dusme(self):
        # Hiç örtüşme yoksa boş değil, en yeni kayıtlara düşmeli (prompt boş kalmasın)
        from features.memory_rag import alakali_hafizalar
        r = alakali_hafizalar("xyzqwer", self.HAFIZALAR, {}, k=2)
        self.assertEqual(len(r), 2)


class TestConfirmedExecutor(unittest.TestCase):
    """Onaylı komut yürütücü doğru executor'a yönlendiriyor mu?"""

    def test_whatsapp_gondericiye_yonlenir(self):
        import features.confirmed_executor as ce
        import features.actions.whatsapp_control as wc
        orig_send, orig_coz = wc.whatsapp_mesaj_gonder, wc.kisi_coz
        wc.whatsapp_mesaj_gonder = lambda a, m: (True, f"WA:{a}:{m}")
        wc.kisi_coz = lambda a: "+905551112233"
        try:
            ok, resp = ce.onayli_komut_yurut("annem'e whatsapp'tan mesaj gönder: selam")
            self.assertTrue(ok)
            self.assertTrue(resp.startswith("WA:"))
        finally:
            wc.whatsapp_mesaj_gonder, wc.kisi_coz = orig_send, orig_coz

    def test_sistem_komutu_sistemcontrole_yonlenir(self):
        # WhatsApp/e-posta olmayan komut sistem yürütücüsüne gitmeli
        import features.confirmed_executor as ce
        ok, resp = ce.onayli_komut_yurut("chrome kapat")
        self.assertTrue(ok)
        self.assertIsInstance(resp, str)


if __name__ == '__main__':
    unittest.main()
