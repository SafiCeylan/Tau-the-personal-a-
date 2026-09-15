# -*- coding: utf-8 -*-
"""
ULTRON — NİYET YÖNLENDİRME KİLİDİ (Intent Routing Lock)

NEDEN VAR:
    12 Ağustos 2026'da eklenen 8 özelliğin (arka plan yönetimi, pencere geçişi,
    derin medya, ekran takibi, canlı sesli sohbet, avatar barı, donanım klavyesi)
    yeni birim testleri YEŞİLDİ ama özelliklerin yarısı çalışmıyordu — çünkü
    testlerin hepsi fonksiyonu DOĞRUDAN çağırıyordu. Hata fonksiyonda değil,
    cümlenin o fonksiyona ULAŞMASINDAydı:

      • medya listesine çıplak "başlat" eklenmişti → "chrome başlat",
        "ekran takibini başlat", "canlı sesli sohbeti başlat" MEDIA_CONTROL'e
        kaçıyordu (MEDIA_CONTROL zincirde onlardan önce bakılıyor).
      • `pencereye_gec` aracı `intent=` olmadan kaydedilmişti → defterden
        ASLA bulunamıyordu; "Zen penceresine geç" GENERAL_CONVERSATION'a,
        "Telegram'a geç" FILE_TRANSFER'a düşüyordu.
      • `.*\byaz\b.*\b(...|gönder)\b` klavye kalıbı çok genişti → "bana bir
        şiir yaz ve gönder" cümlesi aktif pencereye TUŞLANIYORDU.

    Bu dosya cümle → niyet tablosunu kilitler. Yeni bir kalıp eklerken bir
    başkasının cümlesini çalıyorsan burada anlarsın.
"""

import unittest

from core.context import UltronContext
from core.layers.pipeline_layers import IntentAnalyzerLayer, NormalizationLayer


def niyet(cumle: str) -> str:
    ctx = UltronContext(raw_input=cumle)
    ctx.normalized_input = cumle.lower()
    NormalizationLayer().process(ctx)
    IntentAnalyzerLayer().process(ctx)
    return ctx.intent


def _dosya_durumunu_temizle():
    """Bu tablo NİYET ZİNCİRİNİ ölçer, diskteki dosyaları değil.

    `dosya_niyeti_coz` zayıf sinyalli cümlelerde karar için indekse ve kanalın
    SON ARAMA sonuçlarına bakar. Önceki bir test (ya da gerçek kullanımda
    önceki bir dosya araması) o durumu doldurmuş olursa "sonraki şarkı" cümlesi
    "sonraki sayfa" sanılıp FILE_TRANSFER'a düşer. Test makineden bağımsız
    olsun diye kanal durumu her ölçümden önce sıfırlanır.
    """
    try:
        from features import file_index
        file_index._SON_SONUCLAR.clear()
    except Exception:
        pass


# (cümle, beklenen niyet) — sıralama önemli değil, her satır bağımsız.
YONLENDIRME_TABLOSU = [
    # 🎙️ Canlı sesli sohbet — avatar barındaki 🎙️ butonu da bu cümleyi yollar
    ("canlı sesli sohbeti başlat", "DUPLEX_VOICE"),
    ("sesli sohbeti kapat", "DUPLEX_VOICE"),

    # 👁️ Ekran takibi
    ("ekranda Claude açılınca haber ver", "SCREEN_WATCH"),
    ("ekranda Notepad çıkınca uyar", "SCREEN_WATCH"),
    ("ekran takibini başlat", "SCREEN_WATCH"),
    ("ekran takibini durdur", "SCREEN_WATCH"),

    # 🖥️ Uygulama açma — "başlat" medyaya kaçmamalı
    ("chrome başlat", "SYSTEM_CONTROL"),
    ("spotify başlat", "SYSTEM_CONTROL"),
    ("chrome aç", "SYSTEM_CONTROL"),
    ("arka planda ne çalışıyor", "SYSTEM_CONTROL"),
    ("3'ü kapat", "SYSTEM_CONTROL"),

    # 🎵 Yeni oynatma vs. çalanın kontrolü
    ("Gülpembe oynat", "PLAY_MUSIC"),
    ("spotify'da Barış Manço çal", "PLAY_MUSIC"),
    ("şu an ne çalıyor", "PLAY_MUSIC"),
    ("şarkı sözlerini bul: Gülpembe", "PLAY_MUSIC"),
    ("sonraki şarkı", "MEDIA_CONTROL"),
    ("şarkıyı geç", "MEDIA_CONTROL"),
    ("müziği duraklat", "MEDIA_CONTROL"),

    # 🪟 Pencere odaklama/listeleme
    ("Zen penceresine geç", "WINDOW_FOCUS"),
    ("Zen'e geç", "WINDOW_FOCUS"),
    ("VS Code'a geç", "WINDOW_FOCUS"),
    ("Telegram'a geç", "WINDOW_FOCUS"),
    ("Notepad penceresini öne getir", "WINDOW_FOCUS"),
    ("açık pencereleri göster", "WINDOW_FOCUS"),
    ("hangi pencereler açık", "WINDOW_FOCUS"),

    # ⌨️ Klavye — pencere kısayolları buraya, sohbet BURAYA DEĞİL
    ("pencereyi kapat", "KEYBOARD_INPUT"),
    ("diğer pencereye geç", "KEYBOARD_INPUT"),
    ("deneme Ultron tarafından yaz enter bas", "KEYBOARD_INPUT"),
    ("bana bir şiir yaz ve gönder", "GENERAL_CONVERSATION"),
    ("rapor yaz ve bana gönder", "GENERAL_CONVERSATION"),

    # 💬 Mesajlaşma yolu bozulmadı mı
    ("anneme mesaj yaz ve gönder", "WHATSAPP_MESSAGE"),
    # 💰 Finans — Türkçe binlik ayraçlı tutarlar da tanınmalı
    ("bugün markete 350 TL harcadım", "FINANCE_TRACK"),
    ("harcama özetim nerede", "FINANCE_TRACK"),
    ("kiraya 12.500 TL ödedim", "FINANCE_TRACK"),
    ("💰 Harcama Özeti", "FINANCE_TRACK"),          # Telegram butonu
    ("/harcama", "FINANCE_TRACK"),                  # Telegram slash komutu
    # ⚠️ Finans kapısı "içinde sayı geçen her cümleyi" yutmamalı. `_SAYI`
    # gruplamasız yazıldığında bu cümleler FINANCE_TRACK'e düşüyordu.
    ("3'ü kapat", "SYSTEM_CONTROL"),
    ("sesi %50 yap", "SET_VOLUME"),
    ("saat 3'te hatırlat", "CREATE_REMINDER"),
]



class TestNiyetYonlendirme(unittest.TestCase):

    def setUp(self):
        _dosya_durumunu_temizle()

    def test_yonlendirme_tablosu(self):
        for cumle, beklenen in YONLENDIRME_TABLOSU:
            with self.subTest(cumle=cumle):
                _dosya_durumunu_temizle()
                self.assertEqual(niyet(cumle), beklenen)

    def test_ciplak_baslat_medyaya_kacmaz(self):
        """MEDIA_CONTROL zincirde erken; çıplak fiil oraya EKLENMEMELİ."""
        from features.actions.system_control import medya_komutu_algila
        for cumle in ["chrome başlat", "ekran takibini başlat",
                      "canlı sesli sohbeti başlat", "pomodoro başlat", "Gülpembe oynat"]:
            with self.subTest(cumle=cumle):
                self.assertIsNone(medya_komutu_algila(cumle))

    def test_medya_kontrolu_hala_calisiyor(self):
        from features.actions.system_control import medya_komutu_algila
        self.assertEqual(medya_komutu_algila("sonraki şarkı"), "next")
        self.assertEqual(medya_komutu_algila("müziği duraklat"), "pause")
        self.assertEqual(medya_komutu_algila("müziği başlat"), "play")
        # Avatar barındaki ⏯️ butonu: tek tuş = değiştir
        self.assertEqual(medya_komutu_algila("oynat/duraklat"), "playpause")

    def test_pencere_araci_deftere_intentle_yazili(self):
        """intent'siz kaydedilen araca hiçbir cümle ulaşamaz."""
        import core.builtin_tools  # noqa: F401  (kayıt yan etkisi)
        from core.tools import DEFTER
        arac = DEFTER.intent_ile("WINDOW_FOCUS")
        self.assertIsNotNone(arac)
        self.assertEqual(arac.ad, "pencereye_gec")


if __name__ == "__main__":
    unittest.main()
