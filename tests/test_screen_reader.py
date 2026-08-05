# -*- coding: utf-8 -*-
"""
Ekran okuma (OCR) testleri — features/screen_reader.py

EN KRİTİK TESTLER — her biri "sessizce yanlış" bir davranışı kilitler:

  • `test_ekran_goruntusu_komutunu_calmaz` — "ekran görüntüsü al" ve "ekranda ne
    yazıyor" cümlelerinin ikisinde de 'ekran' geçiyor. Kapı yanlış sırada
    sorulursa fotoğraf komutu OCR'a düşer ve kullanıcı fotoğrafını hiç alamaz.
  • `test_kendi_penceremizi_okumaz` — Ultron ön plandayken "ekranda ne yazıyor"
    denince kendi sohbet penceresini okursa cevap kullanıcıya kendi yazdığını
    geri okur; özellik işe yaramaz görünür ama hata da vermez.
  • `test_koordinat_ekran_uzayina_cevrilir` — pencere bölgesi okunduğunda OCR
    koordinatları pencereye GÖRELİ gelir. Ofset eklenmezse "metni bul → tıkla"
    zinciri ekranın yanlış yerine tıklar (AIP seviye 3'ün temeli budur).
  • `test_bulut_saglayiciya_ekran_icerigi_gitmez` — GİZLİLİK SINIRI. Bozulursa
    kullanıcının parola yöneticisi/banka ekranı Gemini'ye gider ve kimse fark
    etmez.
  • `test_ocr_yoksa_uygulama_cokmez` — winsdk kurulu değilse özellik kapanmalı,
    uygulama ayakta kalmalı.

İZOLASYON: gerçek ekran YAKALANMAZ, gerçek OCR ÇALIŞTIRILMAZ — `_ocr_calistir`
ve mss taklit edilir. Ayrıştırma, arama, koordinat ve gizlilik mantığı gerçektir.
"""

import unittest
from unittest import mock

from features import screen_reader as sr


def sahte_ocr(kelimeler, ofset=(0, 0)):
    """(metin, x, y, w, h) demetlerinden gerçek çıktı biçiminde OCR sonucu üretir."""
    ox, oy = ofset
    k = [{"metin": m, "x": x + ox, "y": y + oy, "w": w, "h": h}
         for (m, x, y, w, h) in kelimeler]
    satir = " ".join(d["metin"] for d in k)
    return {"metin": satir, "satirlar": [satir], "kelimeler": k}


class NiyetKapisiTest(unittest.TestCase):
    """Hangi cümle ekran okumadır, hangisi değildir."""

    def test_okuma_cumleleri_yakalanir(self):
        for cumle in ("ekranda ne yazıyor",
                      "ekranı oku",
                      "ekrandaki hatayı açıkla",
                      "ekranı özetle",
                      "ekrandaki metni çevir",
                      "ekranda kaydet var mı"):
            with self.subTest(cumle=cumle):
                self.assertTrue(sr.ekran_niyeti_algila(cumle))

    def test_ekran_goruntusu_komutunu_calmaz(self):
        # Bu cümleler SCREENSHOT'a aittir; boru hattında SCREENSHOT önce sorulur
        # ama kapı yine de bunlara "benim" dememeli.
        for cumle in ("ekran görüntüsü al",
                      "ekranın fotoğrafını çek"):
            with self.subTest(cumle=cumle):
                self.assertFalse(sr.ekran_niyeti_algila(cumle))

    def test_alakasiz_cumleye_el_koymaz(self):
        for cumle in ("spotify aç",
                      "yarın 10:00'da su içmeyi hatırlat",
                      "panodakini özetle",
                      "staj raporunu bul"):
            with self.subTest(cumle=cumle):
                self.assertFalse(sr.ekran_niyeti_algila(cumle))

    def test_komut_ustlenmediginde_none_doner(self):
        self.assertIsNone(sr.ekran_komutu("spotify aç"))


class PencereSecimiTest(unittest.TestCase):
    """Hangi pencere okunacak?"""

    def test_kendi_penceremizi_okumaz(self):
        # Z-sırası: [Ultron (bizim pid), Not Defteri (başka pid)]
        pencereler = [
            (1, "ULTRON NEURAL AI CORE", 4242, (0, 0, 800, 600)),
            (2, "Adsız - Not Defteri", 9999, (100, 50, 900, 650)),
        ]
        with _pencere_taklidi(pencereler):
            bolge, baslik = sr.okunacak_pencere(kendi_pid=4242)
        self.assertEqual(baslik, "Adsız - Not Defteri")
        self.assertEqual(bolge, {"left": 100, "top": 50, "width": 800, "height": 600})

    def test_gorunmez_ve_baslikiz_pencereler_atlanir(self):
        pencereler = [
            (1, "", 9999, (0, 0, 800, 600)),                    # başlıksız
            (2, "Program Manager", 9999, (0, 0, 1920, 1080)),   # masaüstü kabuğu
            (3, "Chrome", 9999, (10, 10, 810, 610)),
        ]
        with _pencere_taklidi(pencereler):
            _, baslik = sr.okunacak_pencere(kendi_pid=4242)
        self.assertEqual(baslik, "Chrome")

    def test_cok_kucuk_pencere_atlanir(self):
        pencereler = [
            (1, "İpucu", 9999, (0, 0, 20, 12)),      # 40x40 altı → OCR alamaz
            (2, "Kod", 9999, (0, 0, 900, 700)),
        ]
        with _pencere_taklidi(pencereler):
            _, baslik = sr.okunacak_pencere(kendi_pid=4242)
        self.assertEqual(baslik, "Kod")


class KoordinatTest(unittest.TestCase):
    """metni_bul → tıklanabilir koordinat (AIP seviye 3'ün temeli)."""

    def test_koordinat_ekran_uzayina_cevrilir(self):
        # Pencere ekranın (300, 200) noktasında; OCR pencereye göreli (10, 5) dedi
        sonuc = sahte_ocr([("Gönder", 10, 5, 60, 20)], ofset=(300, 200))
        sonuc["ok"] = True
        bulunan = sr.metni_bul("gönder", sonuc=sonuc)
        self.assertEqual(len(bulunan), 1)
        self.assertEqual(bulunan[0]["merkez"], (340, 215))

    def test_cok_kelimeli_ifade_birlesik_kutu_verir(self):
        sonuc = sahte_ocr([("Dosyayı", 0, 0, 80, 20), ("Kaydet", 90, 0, 70, 20)])
        sonuc["ok"] = True
        bulunan = sr.metni_bul("dosyayı kaydet", sonuc=sonuc)
        self.assertEqual(len(bulunan), 1)
        self.assertEqual(bulunan[0]["x"], 0)
        self.assertEqual(bulunan[0]["w"], 160)      # iki kelimeyi de kapsar

    def test_turkce_buyuk_i_ile_eslesir(self):
        """EN SİNSİ HATA: 'İptal'.lower() → 'i' + U+0307 + 'ptal' üretir ve
        'iptal' ile EŞLEŞMEZ. Türkçe arayüzlerin en yaygın düğmeleri
        (İptal, İleri, İndir, İzin Ver) bu yüzden hiç bulunamıyordu."""
        for ekran_metni, aranan in (("İptal", "iptal"), ("İleri", "ileri"),
                                    ("İndir", "indir"), ("İzin", "izin"),
                                    ("İptal", "İPTAL")):
            with self.subTest(ekran=ekran_metni, aranan=aranan):
                sonuc = sahte_ocr([(ekran_metni, 0, 0, 60, 20)])
                sonuc["ok"] = True
                self.assertTrue(sr.metni_bul(aranan, sonuc=sonuc),
                                f"{ekran_metni!r} içinde {aranan!r} bulunamadı")

    def test_turkce_karaktersiz_yazilinca_da_eslesir(self):
        # Telefondan hızlı yazarken Türkçe karakter kullanılmaz
        for ekran_metni, aranan in (("Gönder", "gonder"), ("Kaydet ve Çık", "kaydet ve cik"),
                                    ("Değiştir", "degistir"), ("Şifre", "sifre")):
            with self.subTest(ekran=ekran_metni, aranan=aranan):
                sonuc = sahte_ocr([(p, i * 70, 0, 60, 20)
                                   for i, p in enumerate(ekran_metni.split())])
                sonuc["ok"] = True
                self.assertTrue(sr.metni_bul(aranan, sonuc=sonuc),
                                f"{ekran_metni!r} içinde {aranan!r} bulunamadı")

    def test_yakin_metin_onerisi(self):
        sonuc = sahte_ocr([("Dosyalar", 0, 0, 80, 20), ("Belgeler", 90, 0, 80, 20)])
        sonuc["ok"] = True
        oneriler = sr.yakin_metinler("dosyalr", sonuc=sonuc)
        self.assertIn("Dosyalar", oneriler)

    def test_bulunamayinca_bos_liste(self):
        sonuc = sahte_ocr([("Merhaba", 0, 0, 80, 20)])
        sonuc["ok"] = True
        self.assertEqual(sr.metni_bul("iptal", sonuc=sonuc), [])

    def test_okuma_basarisizsa_arama_patlamaz(self):
        self.assertEqual(sr.metni_bul("x", sonuc={"ok": False}), [])

    def test_metni_bul_eki_ve_sayiyi_temizler(self):
        """'1'yi aç' aranırken ekranda '1'e' varsa sayı yedeklemesiyle bulunmalı."""
        sonuc = sahte_ocr([("1'e", 10, 10, 20, 20), ("Aç", 40, 10, 30, 20)])
        sonuc["ok"] = True
        bulunan = sr.metni_bul("1'yi aç", sonuc=sonuc)
        self.assertTrue(bool(bulunan))
        self.assertIn("1'e", bulunan[0]["metin"])


class KomutSonucuTest(unittest.TestCase):
    """direct (kullanıcıya doğrudan) vs ai (LLM'e akmalı) ayrımı."""

    def _oku_taklidi(self, metin="Bağlantı zaman aşımına uğradı", baslik="Chrome"):
        return mock.patch.object(
            sr, 'ekrani_oku',
            return_value={"ok": True, "metin": metin, "satirlar": [metin],
                          "kelimeler": [], "baslik": baslik, "hata": ""})

    def test_duz_okuma_direct_doner(self):
        with self._oku_taklidi():
            sonuc = sr.ekran_komutu("ekranda ne yazıyor")
        self.assertEqual(sonuc['tip'], 'direct')
        self.assertIn("Bağlantı zaman aşımına", sonuc['sonuc'])
        self.assertIn("Chrome", sonuc['sonuc'])       # kaynağı söylüyor

    def test_hata_aciklama_ai_gorevine_doner(self):
        with self._oku_taklidi():
            sonuc = sr.ekran_komutu("ekrandaki hatayı açıkla")
        self.assertEqual(sonuc['tip'], 'ai')
        self.assertIn("Bağlantı zaman aşımına", sonuc['icerik'])
        self.assertTrue(sonuc['gorev'])

    def test_ozetle_ai_gorevine_doner(self):
        with self._oku_taklidi(metin="uzun bir metin"):
            sonuc = sr.ekran_komutu("ekranı özetle")
        self.assertEqual(sonuc['tip'], 'ai')
        self.assertIn("özetle", sonuc['gorev'].lower())

    def test_bos_ekran_uydurmaya_gitmez(self):
        # Metin yoksa LLM'e boş içerik göndermek uydurmaya davetiyedir
        with self._oku_taklidi(metin="   "):
            sonuc = sr.ekran_komutu("ekranı özetle")
        self.assertEqual(sonuc['tip'], 'direct')
        self.assertIn("metin çıkmadı", sonuc['sonuc'])

    def test_ocr_yoksa_uygulama_cokmez(self):
        with mock.patch.object(sr, 'ocr_hazir', return_value=(False, "⚠️ winsdk yok")):
            sonuc = sr.ekran_komutu("ekranda ne yazıyor")
        self.assertEqual(sonuc['tip'], 'direct')
        self.assertIn("winsdk", sonuc['sonuc'])


class GizlilikSiniriTest(unittest.TestCase):
    """Ekran içeriği buluta ÇIKMAMALI (PromptGeneratorLayer)."""

    def _prompt_uret(self, config):
        from core.context import UltronContext
        from core.layers.pipeline_layers import PromptGeneratorLayer

        ctx = UltronContext(raw_input="ekrandaki hatayı açıkla")
        ctx.normalized_input = ctx.raw_input
        ctx.entities = {'ekran_icerik': 'GIZLI-BANKA-BAKIYESI-12345',
                        'ekran_gorev': 'Açıkla.',
                        'ekran_kaynak': 'Banka'}
        return PromptGeneratorLayer(config).process(ctx).enriched_prompt

    def test_yerel_saglayiciya_ekran_icerigi_verilir(self):
        for saglayici in ('ollama', 'kobold'):
            with self.subTest(saglayici=saglayici):
                self.assertIn('GIZLI-BANKA-BAKIYESI-12345',
                              self._prompt_uret({'ai_provider': saglayici}))

    def test_bulut_saglayiciya_ekran_icerigi_gitmez(self):
        for saglayici in ('gemini', 'tau_backend'):
            with self.subTest(saglayici=saglayici):
                prompt = self._prompt_uret({'ai_provider': saglayici})
                self.assertNotIn('GIZLI-BANKA-BAKIYESI-12345', prompt)
                self.assertIn('GÖNDERİLMEDİ', prompt)

    def test_dogru_config_anahtari_okunur(self):
        """Uygulama sağlayıcıyı 'ai_provider'dan okur. Katman 'provider'a bakarsa
        kullanıcının GERÇEK config'inde (provider: None) yerel model bulut sanılır
        ve ekran okuma sessizce çalışmaz."""
        gercek_config = {'provider': None, 'ai_provider': 'ollama'}
        self.assertIn('GIZLI-BANKA-BAKIYESI-12345', self._prompt_uret(gercek_config))

    def test_saglayici_hic_yoksa_yerel_varsayilir(self):
        # AssistantController da anahtar yokken 'ollama' varsayar — aynı olmalı
        self.assertIn('GIZLI-BANKA-BAKIYESI-12345', self._prompt_uret({}))
        self.assertIn('GIZLI-BANKA-BAKIYESI-12345', self._prompt_uret({'provider': None}))


class MotorEntegrasyonTest(unittest.TestCase):
    """Araç deftere doğru intent'le girmiş mi?"""

    def test_arac_screen_read_intentine_bagli(self):
        import core.builtin_tools  # noqa: F401
        from core.tools import DEFTER

        arac = DEFTER.intent_ile("SCREEN_READ")
        self.assertIsNotNone(arac, "SCREEN_READ niyeti hiçbir araca bağlı değil")
        self.assertEqual(arac.ad, 'ekrani_oku')

    def test_screenshot_araci_ayri_kalir(self):
        # Aynı intent haritasında ilk kaydedilen kazanır: ekran okuma aracı
        # SCREENSHOT'ı devralmamalı, fotoğraf komutu bozulmamalı.
        import core.builtin_tools  # noqa: F401
        from core.tools import DEFTER

        self.assertEqual(DEFTER.intent_ile("SCREENSHOT").ad, 'ekran_goruntusu')


# ---------------------------------------------------------------------------
# Yardımcı: EnumWindows + Win32 çağrılarını taklit eder (gerçek OS'a dokunmaz)
# ---------------------------------------------------------------------------
def _pencere_taklidi(pencereler):
    """pencereler: [(hwnd, baslik, pid, (left, top, right, bottom))]"""
    import contextlib
    import ctypes

    kayit = {h: (b, p, r) for (h, b, p, r) in pencereler}
    sira = [h for (h, _, _, _) in pencereler]

    class SahteUser32:
        @staticmethod
        def EnumWindows(geri_cagirim, _lparam):
            for hwnd in sira:
                if not geri_cagirim(hwnd, 0):
                    break
            return True

        @staticmethod
        def IsWindowVisible(_hwnd):
            return 1

        @staticmethod
        def IsIconic(_hwnd):
            return 0

        @staticmethod
        def GetWindowTextLengthW(hwnd):
            return len(kayit[_hwnd_degeri(hwnd)][0])

        @staticmethod
        def GetWindowTextW(hwnd, tampon, _n):
            tampon.value = kayit[_hwnd_degeri(hwnd)][0]
            return len(tampon.value)

        @staticmethod
        def GetWindowThreadProcessId(hwnd, pid_ref):
            pid_ref._obj.value = kayit[_hwnd_degeri(hwnd)][1]
            return 1

        @staticmethod
        def GetWindowRect(hwnd, rect_ref):
            sol, ust, sag, alt = kayit[_hwnd_degeri(hwnd)][2]
            r = rect_ref._obj
            r.left, r.top, r.right, r.bottom = sol, ust, sag, alt
            return 1

    def _hwnd_degeri(h):
        return getattr(h, 'value', h)

    @contextlib.contextmanager
    def _baglam():
        gercek_windll = ctypes.windll
        with mock.patch.object(sr.ctypes, 'windll') as sahte:
            sahte.user32 = SahteUser32
            # DWM: uzatılmış sınır YOK (0 dışı dön) → GetWindowRect'e düşülür,
            #      cloaked sorgusu da başarısız olsun → gizli değil sayılır
            sahte.dwmapi.DwmGetWindowAttribute.return_value = 1
            yield
        assert ctypes.windll is gercek_windll

    return _baglam()


if __name__ == '__main__':
    unittest.main()
