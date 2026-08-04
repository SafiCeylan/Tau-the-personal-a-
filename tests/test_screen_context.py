# -*- coding: utf-8 -*-
"""
Ekran bağlamı testleri — features/screen_context.py

AMAÇ: "ekranı oku" komutunun kelime çöplüğü yerine SEÇİLEBİLİR ÖĞE listesi
üretmesi ve "3'ü aç" gibi cümlelerin o listeye bağlanabilmesi.

KİLİTLENEN DAVRANIŞLAR:
  • `test_kartlar_ayri_ogelere_bolunur` — YouTube kartı / Google sonucu /
    liste satırı hepsi aynı geometrik kuralla ayrılmalı. Bozulursa ekran tek
    bir dev bloğa dönüşür ve "3'ü aç" diye bir şey kalmaz.
  • `test_sira_ekrandaki_konuma_gore` — kullanıcı GÖRDÜĞÜ sırayı sayar.
    Numaralandırma OCR'ın döndürme sırasına göre yapılırsa yanlış öğe açılır.
  • `test_tum_ek_bicimleri_cozulur` — "2'yi aç" Türkçede 'yi' ekiyle yazılır;
    ek listesi eksikse en doğal yazım çalışmaz (bu hata gerçekten oldu).
  • `test_bayat_okuma_kullanilmaz` — ekran saniyeler içinde değişir. Eski
    koordinata tıklamak YANLIŞ ŞEYE tıklamaktır.
  • `test_okuma_yoksa_secim_reddedilir` — liste yokken "3'ü aç" demek
    rastgele bir noktaya tıklamak olurdu.
"""

import time
import unittest

from features import screen_context as sc


def satir(metin, x, y, w=300, h=20):
    return {"metin": metin, "x": x, "y": y, "w": w, "h": h}


def okuma(satirlar):
    return {"ok": True, "satir_kutulari": satirlar,
            "metin": "\n".join(s["metin"] for s in satirlar)}


# YouTube arama sonucu düzeni: her kart = başlık + kanal + görüntülenme
YOUTUBE = okuma([
    satir("Tarkan - Kuzu Kuzu (Official Video)", 400, 100),
    satir("Tarkan", 400, 124, 120, 16),
    satir("12 Mn goruntulenme", 400, 142, 160, 16),

    satir("Sezen Aksu - Sarki Soylemek Lazim", 400, 300),
    satir("SezenAksuVEVO", 400, 324, 140, 16),
    satir("8 Mn goruntulenme", 400, 342, 160, 16),

    satir("Baris Manco - Gulpembe", 400, 500),
    satir("Baris Manco Official", 400, 524, 150, 16),
])


class OgeCikarimTest(unittest.TestCase):

    def setUp(self):
        sc.okumayi_unut(sc.VARSAYILAN_KANAL)

    def test_kartlar_ayri_ogelere_bolunur(self):
        ogeler = sc.ogeleri_cikar(YOUTUBE)
        self.assertEqual(len(ogeler), 3, "kartlar tek bloğa yapıştı veya parçalandı")
        self.assertEqual(ogeler[0]['baslik'], "Tarkan - Kuzu Kuzu (Official Video)")
        self.assertEqual(ogeler[1]['baslik'], "Sezen Aksu - Sarki Soylemek Lazim")
        self.assertEqual(ogeler[2]['baslik'], "Baris Manco - Gulpembe")

    def test_detay_satirlari_baslikla_birlikte_kalir(self):
        ogeler = sc.ogeleri_cikar(YOUTUBE)
        self.assertIn("Tarkan", ogeler[0]['detay'])
        self.assertIn("goruntulenme", ogeler[0]['detay'])

    def test_sira_ekrandaki_konuma_gore(self):
        # OCR ters sırada verse bile numaralandırma yukarıdan aşağı olmalı
        ters = okuma(list(reversed(YOUTUBE['satir_kutulari'])))
        ogeler = sc.ogeleri_cikar(ters)
        self.assertEqual([o['sira'] for o in ogeler], [1, 2, 3])
        self.assertEqual(ogeler[0]['baslik'], "Tarkan - Kuzu Kuzu (Official Video)")

    def test_yan_yana_butonlar_ayrilir(self):
        """Yan yana duran düğmeler OCR'da TEK satır gelir. Ayrılmazsa
        "Hatırlatma Ekle Google Git" tek öğe olur ve hiçbirine tıklanamaz."""
        # Tek satır, ama kelimeler arasında geniş boşluklar var
        kelimeler = [
            {"metin": "Hatırlatma", "x": 100, "y": 900, "w": 90, "h": 16},
            {"metin": "Ekle", "x": 195, "y": 900, "w": 35, "h": 16},
            {"metin": "Google", "x": 500, "y": 900, "w": 55, "h": 16},   # büyük boşluk
            {"metin": "Git", "x": 560, "y": 900, "w": 25, "h": 16},
        ]
        veri = {
            "ok": True,
            "satir_kutulari": [satir("Hatırlatma Ekle Google Git", 100, 900, 485, 16)],
            "kelimeler": kelimeler,
        }
        ogeler = sc.ogeleri_cikar(veri)
        basliklar = [o['baslik'] for o in ogeler]
        self.assertEqual(len(ogeler), 2, f"düğmeler ayrılmadı: {basliklar}")
        self.assertIn("Hatırlatma Ekle", basliklar)
        self.assertIn("Google Git", basliklar)

    def test_kelime_verisi_yoksa_satir_bozulmaz(self):
        """`kelimeler` gelmezse (eski çağrılar) satır olduğu gibi kullanılmalı."""
        veri = {"ok": True, "satir_kutulari": [satir("Tek Bir Başlık", 10, 10)]}
        ogeler = sc.ogeleri_cikar(veri)
        self.assertEqual(len(ogeler), 1)
        self.assertEqual(ogeler[0]['baslik'], "Tek Bir Başlık")

    def test_gurultu_oge_sayilmaz(self):
        gurultulu = okuma([
            satir("x", 10, 10, 8, 10),          # tek harf
            satir("14:32", 100, 10, 40, 12),    # saat
            satir("···", 200, 10, 20, 10),      # simge
            satir("Gerçek Bir Başlık", 400, 100),
        ])
        ogeler = sc.ogeleri_cikar(gurultulu)
        self.assertEqual(len(ogeler), 1)
        self.assertEqual(ogeler[0]['baslik'], "Gerçek Bir Başlık")

    def test_ozet_numarali_liste_uretir(self):
        ogeler = sc.ogeleri_cikar(YOUTUBE)
        ozet = sc.ozet_uret(ogeler, "YouTube")
        self.assertIn("**1.**", ozet)
        self.assertIn("**3.**", ozet)
        self.assertIn("Kuzu Kuzu", ozet)
        self.assertIn("Hangisini açayım", ozet)
        # Kelime çöplüğü DEĞİL: makul uzunlukta olmalı
        self.assertLess(len(ozet), 900)


class SecimCozumlemeTest(unittest.TestCase):

    def setUp(self):
        sc.okumayi_kaydet(sc.VARSAYILAN_KANAL,
                          sc.ogeleri_cikar(YOUTUBE), "YouTube")

    def tearDown(self):
        sc.okumayi_unut(sc.VARSAYILAN_KANAL)

    def test_tum_ek_bicimleri_cozulur(self):
        for cumle, sira in [("1'i aç", 1), ("2'yi aç", 2), ("3'ü aç", 3),
                            ("4'ü aç", 4), ("5'i aç", 5), ("6'yı aç", 6),
                            ("3 numaralı olanı aç", 3), ("5. sırayı aç", 5)]:
            with self.subTest(cumle=cumle):
                ref = sc.secim_referansi_coz(cumle)
                self.assertIsNotNone(ref, f"{cumle!r} çözülemedi")
                self.assertEqual(ref, {'tip': 'sira', 'deger': sira})

    def test_sira_kelimeleri_cozulur(self):
        for cumle, sira in [("ikinciyi aç", 2), ("üçüncü videoyu aç", 3),
                            ("sonuncuyu aç", -1)]:
            with self.subTest(cumle=cumle):
                self.assertEqual(sc.secim_referansi_coz(cumle)['deger'], sira)

    def test_metinle_secim(self):
        ref = sc.secim_referansi_coz("kuzu kuzu olanı aç")
        self.assertEqual(ref['tip'], 'metin')
        oge, hata = sc.ogeyi_sec(ref, sc.VARSAYILAN_KANAL)
        self.assertIsNone(hata)
        self.assertIn("Kuzu Kuzu", oge['baslik'])

    def test_numara_dogru_ogeye_baglanir(self):
        oge, hata = sc.ogeyi_sec({'tip': 'sira', 'deger': 2}, sc.VARSAYILAN_KANAL)
        self.assertIsNone(hata)
        self.assertIn("Sezen Aksu", oge['baslik'])

    def test_sonuncu_calisir(self):
        oge, _ = sc.ogeyi_sec({'tip': 'sira', 'deger': -1}, sc.VARSAYILAN_KANAL)
        self.assertIn("Gulpembe", oge['baslik'])

    def test_olmayan_numara_reddedilir(self):
        oge, hata = sc.ogeyi_sec({'tip': 'sira', 'deger': 99}, sc.VARSAYILAN_KANAL)
        self.assertIsNone(oge)
        self.assertIn("99", hata)

    def test_alakasiz_cumle_secim_sayilmaz(self):
        for cumle in ("naber", "spotify aç", "youtube aç", "chrome kapat",
                      "hava nasıl", "3 dakika sonra hatırlat"):
            with self.subTest(cumle=cumle):
                self.assertIsNone(sc.secim_referansi_coz(cumle))

    def test_okuma_yoksa_secim_reddedilir(self):
        sc.okumayi_unut(sc.VARSAYILAN_KANAL)
        oge, hata = sc.ogeyi_sec({'tip': 'sira', 'deger': 1}, sc.VARSAYILAN_KANAL)
        self.assertIsNone(oge)
        self.assertIn("Önce ekranı okumam", hata)

    def test_bayat_okuma_kullanilmaz(self):
        """Ekran saniyeler içinde değişir; eski koordinat yanlış şeye tıklar."""
        kayit = sc._SON_OKUMA[sc.VARSAYILAN_KANAL]
        kayit['zaman'] = time.time() - (sc._OKUMA_OMRU_SN + 5)
        self.assertIsNone(sc.son_okuma(sc.VARSAYILAN_KANAL))


class TelegramButonTest(unittest.TestCase):
    """Menü butonu → düz komut.

    Bu ayrıştırma bilerek `telegram_bridge`'te: `tau_window` içinde `re`
    fonksiyon ORTASINDA import ediliyor ve fonksiyonun başında `re.` kullanmak
    UnboundLocalError veriyor — yani HER Telegram komutu çökerdi.
    """

    def test_numara_butonlari_komuta_cevrilir(self):
        from features.telegram_bridge import menu_butonu_coz as coz
        for buton, komut in [("3️⃣ 3'ü Aç", "3'ü aç"), ("1️⃣ 1'i Aç", "1'i aç"),
                             ("2️⃣ 2'yi Aç", "2'yi aç"), ("6️⃣ 6'yı Aç", "6'yı aç")]:
            with self.subTest(buton=buton):
                self.assertEqual(coz(buton), komut)

    def test_diger_butonlara_dokunmaz(self):
        from features.telegram_bridge import menu_butonu_coz as coz
        for buton in ("👁️ Ekranda Ne Var", "🏠 Ana Menü", "naber",
                      "📸 Ekran Görüntüsü Al", ""):
            with self.subTest(buton=buton):
                self.assertEqual(coz(buton), buton)

    def test_cevrilen_komut_secim_olarak_cozulur(self):
        """Zincirin tamamı: buton → komut → seçim referansı."""
        from features.telegram_bridge import menu_butonu_coz as coz
        ref = sc.secim_referansi_coz(coz("3️⃣ 3'ü Aç"))
        self.assertEqual(ref, {'tip': 'sira', 'deger': 3})

    def test_ekran_menusu_butonlari_niyete_baglaniyor(self):
        """Menüdeki her buton gerçekten bir yeteneğe gitmeli — ölü buton olmasın."""
        from core.context import UltronContext
        from core.layers.pipeline_layers import IntentAnalyzerLayer
        from features.telegram_bridge import ekran_klavyesi

        sc.okumayi_kaydet(sc.VARSAYILAN_KANAL, sc.ogeleri_cikar(YOUTUBE), "Test")
        katman = IntentAnalyzerLayer({})
        beklenen = {
            "👁️ Ekranda Ne Var": "SCREEN_READ",
            "📖 Ekranı Özetle": "SCREEN_READ",
            "🩺 Ekrandaki Hatayı Açıkla": "SCREEN_READ",
            "🌍 Ekranı Çevir": "SCREEN_READ",
            "3️⃣ 3'ü Aç": "SCREEN_SELECT",
        }
        butonlar = [b['text'] for satir in ekran_klavyesi()['keyboard'] for b in satir]
        for buton, niyet in beklenen.items():
            self.assertIn(buton, butonlar, "menüde böyle bir buton yok")
            with self.subTest(buton=buton):
                from features.telegram_bridge import menu_butonu_coz
                komut = menu_butonu_coz(buton)
                ctx = UltronContext(raw_input=komut)
                ctx.normalized_input = komut
                self.assertEqual(katman.process(ctx, hafif=True).intent, niyet)


class NiyetKapisiTest(unittest.TestCase):
    """Seçim kapısı yalnızca TAZE okuma varken açılmalı."""

    def tearDown(self):
        sc.okumayi_unut(sc.VARSAYILAN_KANAL)

    def test_kapi_okuma_yokken_kapali(self):
        from core.context import UltronContext
        from core.layers.pipeline_layers import IntentAnalyzerLayer

        sc.okumayi_unut(sc.VARSAYILAN_KANAL)
        ctx = UltronContext(raw_input="3'ü aç")
        ctx.normalized_input = "3'ü aç"
        self.assertNotEqual(IntentAnalyzerLayer({}).process(ctx, hafif=True).intent,
                            "SCREEN_SELECT")

    def test_kapi_okuma_varken_acilir(self):
        from core.context import UltronContext
        from core.layers.pipeline_layers import IntentAnalyzerLayer

        sc.okumayi_kaydet(sc.VARSAYILAN_KANAL, sc.ogeleri_cikar(YOUTUBE), "YouTube")
        ctx = UltronContext(raw_input="3'ü aç")
        ctx.normalized_input = "3'ü aç"
        self.assertEqual(IntentAnalyzerLayer({}).process(ctx, hafif=True).intent,
                         "SCREEN_SELECT")


if __name__ == '__main__':
    unittest.main()
