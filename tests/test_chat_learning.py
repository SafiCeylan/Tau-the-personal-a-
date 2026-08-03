# -*- coding: utf-8 -*-
"""
Öğrenme Katmanı testleri (features/chat_learning.py).

    geçmiş konuşmalar → geri çağırma · örüntü · düzeltmeden öğrenme

EN KRİTİK TESTLER:
  • `test_sir_tasiyan_mesaj_arsive_girmez` — arşiv prompt'a, prompt Telegram'a
    dönüyor. Şifre/PIN buraya girerse iki yerde birden sızar.
  • `test_mesaj_gonderen_intentler_ogrenilmez` — yanlış öğrenilmiş bir kalıp
    yanlış kişiye mesaj göndermektir; telafisi yoktur.
  • `test_celiskili_kalip_ogrenilmez` — aynı ifade iki farklı niyete
    bağlanıyorsa öğrenme güvenilmez demektir, kalıp DÜŞÜRÜLÜR.
  • `test_tek_gozlem_kalibi_aktif_etmez` — bir kez olan şey alışkanlık değildir.

İZOLASYON: her test kendi geçici veritabanını kullanır (`_db_yolu` yamalanır),
gerçek `%APPDATA%\\ULTRON\\ogrenme.db` dosyasına HİÇ dokunulmaz.
"""

import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from features import chat_learning as cl


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class OgrenmeTemeli(unittest.TestCase):
    """Her test taze bir veritabanıyla başlar."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ultron_ogrenme_')
        self.db = os.path.join(self.tmp, 'ogrenme.db')
        self.yama = mock.patch.object(cl, '_db_yolu', return_value=self.db)
        self.yama.start()
        cl._SON_TUR.clear()
        cl._onbellegi_dusur()

    def tearDown(self):
        self.yama.stop()
        cl._SON_TUR.clear()
        cl._onbellegi_dusur()
        shutil.rmtree(self.tmp, ignore_errors=True)


# =========================================================================
# SADELEŞTİRME VE FİLTRELER
# =========================================================================
class FiltreTest(OgrenmeTemeli):

    def test_turkce_sadelestirilir(self):
        self.assertEqual(cl.sadelestir("Şarkı ÇAL"), "sarki cal")
        # 'İ'.lower() birleşen nokta bırakır — temizlenmezse eşleşme bozulur
        self.assertEqual(cl.sadelestir("İSTANBUL"), "istanbul")

    def test_sir_tasiyan_mesaj_arsive_girmez(self):
        """Arşiv prompt'a dönüyor: şifre buraya girerse Telegram'a da sızar."""
        for gizli in ("wifi şifrem 12345", "pin: 4021", "api key sk-abc123",
                      "parolam deneme", "kart numarası 4444"):
            self.assertFalse(cl.ogrenilebilir_mi(gizli), gizli)
            self.assertEqual(cl.kaydet(gizli, "tamam"), 0, gizli)
        self.assertEqual(cl.istatistik()['konusma'], 0)

    def test_kontrol_kelimeleri_ogrenilmez(self):
        """'evet' / 'sus' tek başına bir şey öğretmez, arşivi kirletir."""
        for kelime in ("evet", "tamam", "iptal", "sus"):
            self.assertFalse(cl.ogrenilebilir_mi(kelime), kelime)

    def test_normal_cumle_ogrenilir(self):
        self.assertTrue(cl.ogrenilebilir_mi("hava durumu nasıl"))
        self.assertGreater(cl.kaydet("hava durumu nasıl", "24 derece"), 0)


# =========================================================================
# 1. SÜTUN — EPİZODİK GERİ ÇAĞIRMA
# =========================================================================
class GeriCagirmaTest(OgrenmeTemeli):

    def _arsiv_doldur(self):
        cl.kaydet("annemin doğum günü 12 mayıs", "Not aldım.",
                  intent="NOTE_TAKE", basarili=True)
        cl.kaydet("BTC fiyatı ne kadar", "BTC 45 bin dolar.",
                  intent="WEB_SEARCH", basarili=True)
        cl.kaydet("staj raporumu yarın teslim edeceğim", "Hatırlatayım mı?")

    def test_alakali_konusma_bulunur(self):
        self._arsiv_doldur()
        sonuc = cl.alakali_konusmalar("annemin doğum günü ne zamandı", k=3)
        self.assertTrue(sonuc)
        self.assertIn("doğum günü", sonuc[0]['soru'])

    def test_alakasiz_mesaja_bos_doner(self):
        """Alakasız geçmişi prompt'a koymak modeli yanıltır — boş dönmek doğrudur."""
        self._arsiv_doldur()
        self.assertEqual(cl.alakali_konusmalar("kubbeli mimari nedir", k=3), [])

    def test_ayni_soru_tekrar_tekrar_donmez(self):
        for _ in range(4):
            cl.kaydet("dolar kaç TL", "42 TL", intent="CURRENCY", basarili=True)
        sonuc = cl.alakali_konusmalar("dolar kaç TL oldu", k=3)
        self.assertEqual(len(sonuc), 1)

    def test_prompt_blogu_gecmis_uyarisi_tasir(self):
        """Model eski konuşmayı bugün olmuş gibi anlatırsa halüsinasyon olur."""
        self._arsiv_doldur()
        blok = cl.prompt_blogu("annemin doğum günü", k=2)
        self.assertIn("GEÇMİŞ", blok)
        self.assertIn("bugün olmuş gibi anlatma", blok)

    def test_bos_arsivde_blok_uretilmez(self):
        self.assertEqual(cl.prompt_blogu("herhangi bir şey"), "")

    def test_cevap_sonradan_tamamlanir(self):
        """Masaüstünde cevap streaming ile sonra gelir."""
        cl.kaydet("python nedir", "", intent="GENERAL_CONVERSATION")
        cl.cevabi_tamamla("desktop", "python nedir", "Bir programlama dili.")
        sonuc = cl.alakali_konusmalar("python hakkında ne demiştin", k=1)
        self.assertEqual(sonuc[0]['cevap'], "Bir programlama dili.")


# =========================================================================
# 2. SÜTUN — ÖRÜNTÜ ÇIKARIMI
# =========================================================================
class OruntuTest(OgrenmeTemeli):

    def test_tek_kullanim_oruntu_sayilmaz(self):
        cl.kaydet("hava durumu nasıl", "24 derece", intent="WEATHER", basarili=True)
        self.assertEqual(cl.oruntuler(zorla=True)['sik_komut'], [])

    def test_tekrarlanan_komut_oruntu_olur(self):
        for _ in range(cl.MIN_ORUNTU_GOZLEM):
            cl.kaydet("hava durumu nasıl", "24 derece", intent="WEATHER", basarili=True)
        komutlar = cl.oruntuler(zorla=True)['sik_komut']
        self.assertEqual(komutlar[0]['komut'], "hava durumu nasil")
        self.assertEqual(komutlar[0]['sayi'], cl.MIN_ORUNTU_GOZLEM)

    def test_basarisiz_komut_oruntu_olmaz(self):
        """Çalışmamış komut alışkanlık değildir."""
        for _ in range(5):
            cl.kaydet("şunu yap", "", intent="SYSTEM_CONTROL", basarili=False)
        self.assertEqual(cl.oruntuler(zorla=True)['sik_komut'], [])

    def test_etiketler_sayilir(self):
        for _ in range(3):
            cl.kaydet("anneme mesaj at", "gönderildi", intent="WHATSAPP_MESSAGE",
                      basarili=True, etiketler={'kisi': 'annem'})
        etiketler = cl.oruntuler(zorla=True)['etiket']
        self.assertEqual(etiketler[0]['deger'], 'annem')
        self.assertEqual(etiketler[0]['sayi'], 3)

    def test_profil_satirlari_sadece_gozlem_yazar(self):
        for _ in range(4):
            cl.kaydet("dolar kaç", "42 TL", intent="CURRENCY", basarili=True)
        satirlar = cl.profil_satirlari()
        self.assertTrue(any("4 kez" in s for s in satirlar))

    def test_onbellek_yeni_kayitta_duser(self):
        cl.oruntuler(zorla=True)
        for _ in range(3):
            cl.kaydet("saat kaç", "14:00", intent="TIME_DATE", basarili=True)
        # Yeni kayıt önbelleği düşürdüğü için zorlamadan da güncel gelmeli
        self.assertTrue(cl.oruntuler()['sik_komut'])


# =========================================================================
# 3. SÜTUN — DÜZELTMEDEN ÖĞRENME
# =========================================================================
class DuzeltmeTest(OgrenmeTemeli):

    def _duzeltme_turu(self, anlasilmayan="biraz kısar mısın sesi",
                       basarili_komut="sesi kıs", intent="SET_VOLUME"):
        cl.kaydet(anlasilmayan, "", intent="GENERAL_CONVERSATION", basarili=False)
        cl.kaydet(basarili_komut, "Ses %20", intent=intent, basarili=True)

    def test_tek_gozlem_kalibi_aktif_etmez(self):
        """Bir kez olan şey tesadüf olabilir — iki gözlem şart."""
        self._duzeltme_turu()
        self.assertIsNone(cl.ogrenilmis_intent("biraz kısar mısın sesi"))

    def test_iki_gozlemde_kalip_aktiflesir(self):
        self._duzeltme_turu()
        self._duzeltme_turu()
        self.assertEqual(cl.ogrenilmis_intent("biraz kısar mısın sesi")[0], "SET_VOLUME")

    def test_yakin_varyant_da_eslesir(self):
        self._duzeltme_turu()
        self._duzeltme_turu()
        self.assertEqual(cl.ogrenilmis_intent("biraz kısar mısın sesi lütfen")[0],
                         "SET_VOLUME")

    def test_alakasiz_cumle_eslesmez(self):
        self._duzeltme_turu()
        self._duzeltme_turu()
        self.assertIsNone(cl.ogrenilmis_intent("bugün hava çok güzel"))

    def test_mesaj_gonderen_intentler_ogrenilmez(self):
        """
        WhatsApp/mail/dosya niyetleri öğrenilemez.

        Yanlış öğrenilmiş bir kalıp burada YANLIŞ KİŞİYE MESAJ demektir —
        `core/aliases.py`'deki bulanık eşleşme yasağıyla aynı gerekçe.
        """
        for intent in ("WHATSAPP_MESSAGE", "EMAIL_MESSAGE", "FILE_TRANSFER",
                       "KEYBOARD_INPUT", "CREATE_REMINDER"):
            cl._SON_TUR.clear()
            self._duzeltme_turu("anneme selam söyle bir", "anneme selam yaz", intent)
            cl._SON_TUR.clear()
            self._duzeltme_turu("anneme selam söyle bir", "anneme selam yaz", intent)
            self.assertIsNone(cl.ogrenilmis_intent("anneme selam söyle bir"), intent)

    def test_celiskili_kalip_ogrenilmez(self):
        """Aynı ifade iki niyete bağlanıyorsa öğrenme güvenilmez → kalıp düşer."""
        self._duzeltme_turu("şunu yapsana", "şunu yapsana hemen", "WEATHER")
        self._duzeltme_turu("şunu yapsana", "şunu yapsana hemen", "CURRENCY")
        self.assertIsNone(cl.ogrenilmis_intent("şunu yapsana"))

    def test_konu_degisikligi_duzeltme_sayilmaz(self):
        """Alakasız iki mesaj arka arkaya geldiyse bu bir düzeltme değildir."""
        cl.kaydet("bugün canım sıkkın", "", intent="GENERAL_CONVERSATION", basarili=False)
        cl.kaydet("spotify aç", "Açıldı", intent="SYSTEM_CONTROL", basarili=True)
        cl.kaydet("bugün canım sıkkın", "", intent="GENERAL_CONVERSATION", basarili=False)
        cl.kaydet("spotify aç", "Açıldı", intent="SYSTEM_CONTROL", basarili=True)
        self.assertIsNone(cl.ogrenilmis_intent("bugün canım sıkkın"))

    def test_zaman_asimi_duzeltme_sayilmaz(self):
        """
        5 dakika sonra gelen komut bir düzeltme değil, yeni bir istektir.

        İki tur yapılır: zaman kapısı kaldırılırsa kalıp AKTİFLEŞİRDİ — test
        böylece gerçekten kapıyı sınar, tek gözlem kuralına yaslanmaz.
        """
        for _ in range(2):
            cl.kaydet("biraz kısar mısın sesi", "", intent="GENERAL_CONVERSATION",
                      basarili=False)
            cl._SON_TUR['desktop']['zaman'] = time.time() - (cl.DUZELTME_PENCERESI_SN + 10)
            cl.kaydet("sesi kıs", "Ses %20", intent="SET_VOLUME", basarili=True)
        self.assertIsNone(cl.ogrenilmis_intent("biraz kısar mısın sesi"))

    def test_basarili_tur_kalip_uretmez(self):
        """Önceki komut zaten çalıştıysa öğrenilecek bir eksik yok."""
        cl.kaydet("sesi aç", "Ses %60", intent="SET_VOLUME", basarili=True)
        cl.kaydet("sesi kıs", "Ses %20", intent="SET_VOLUME", basarili=True)
        cl.kaydet("sesi aç", "Ses %60", intent="SET_VOLUME", basarili=True)
        cl.kaydet("sesi kıs", "Ses %20", intent="SET_VOLUME", basarili=True)
        self.assertIsNone(cl.ogrenilmis_intent("sesi aç"))

    def test_sirli_mesajdan_kalip_ogrenilmez(self):
        self._duzeltme_turu("pin kodum 1234 gir", "ekranı aç", "SYSTEM_CONTROL")
        self._duzeltme_turu("pin kodum 1234 gir", "ekranı aç", "SYSTEM_CONTROL")
        self.assertIsNone(cl.ogrenilmis_intent("pin kodum 1234 gir"))


# =========================================================================
# KOMUT ALGILAMA VE RAPOR
# =========================================================================
class KomutTest(OgrenmeTemeli):

    def test_rapor_komutlari_taninir(self):
        for cumle in ("ne öğrendin", "neler öğrendin bugüne kadar",
                      "öğrenme raporu", "hakkımda ne biliyorsun"):
            komut = cl.ogrenme_komutu_algila(cumle)
            self.assertIsNotNone(komut, cumle)
            self.assertEqual(komut['islem'], 'rapor', cumle)

    def test_unut_komutu_taninir(self):
        komut = cl.ogrenme_komutu_algila("şunu unut: biraz kısar mısın")
        self.assertEqual(komut['islem'], 'unut')
        self.assertEqual(komut['hedef'], 'biraz kisar misin')

    def test_ciplak_unut_kalip_silmez(self):
        """Sohbetteki 'bu konuyu unut' cümlesi öğrenilmiş kalıbı silmemeli."""
        self.assertIsNone(cl.ogrenme_komutu_algila("bu konuyu unut gitsin"))

    def test_siradan_cumle_komut_sayilmaz(self):
        for cumle in ("hava durumu nasıl", "spotify aç", "anneme mesaj at"):
            self.assertIsNone(cl.ogrenme_komutu_algila(cumle), cumle)

    def test_rapor_bos_arsivde_de_calisir(self):
        self.assertIn("BOŞ", cl.ogrenme_raporu())

    def test_rapor_ogrenilenleri_gosterir(self):
        """
        Rapor kullanıcının KENDİ cümlesini gösterir, ASCII'ye indirgenmişini
        değil: `sade` sütunu karşılaştırma içindir, ekrana basılınca bozuk
        Türkçe olarak görünüyordu ("hava durumu nasil").
        """
        for _ in range(3):
            cl.kaydet("hava durumu nasıl", "24 derece", intent="WEATHER", basarili=True)
        rapor = cl.ogrenme_raporu()
        self.assertIn("hava durumu nasıl", rapor)
        self.assertNotIn("hava durumu nasil", rapor)
        self.assertIn("3 kez", rapor)

    def test_unut_kalibi_siler_arsivi_silmez(self):
        cl.kaydet("biraz kısar mısın sesi", "", intent="GENERAL_CONVERSATION",
                  basarili=False)
        cl.kaydet("sesi kıs", "Ses %20", intent="SET_VOLUME", basarili=True)
        cl.kaydet("biraz kısar mısın sesi", "", intent="GENERAL_CONVERSATION",
                  basarili=False)
        cl.kaydet("sesi kıs", "Ses %20", intent="SET_VOLUME", basarili=True)
        onceki_konusma = cl.istatistik()['konusma']

        mesaj = cl.unut("biraz kısar mısın sesi")

        self.assertIn("Unuttum", mesaj)
        self.assertIsNone(cl.ogrenilmis_intent("biraz kısar mısın sesi"))
        # Kalıp silindi ama konuşma arşivi DURUYOR
        self.assertEqual(cl.istatistik()['konusma'], onceki_konusma)

    def test_olmayan_kalip_unutulmak_istenirse_bilgilendirir(self):
        self.assertIn("bulamadım", cl.unut("hiç olmayan bir ifade"))


# =========================================================================
# GEÇMİŞ GÖÇÜ
# =========================================================================
class GocTest(OgrenmeTemeli):

    def _sahte_ana_db(self, satirlar):
        import sqlite3
        yol = os.path.join(self.tmp, 'bilgiler.db')
        conn = sqlite3.connect(yol)
        conn.execute("CREATE TABLE sohbet_gecmisi (id INTEGER PRIMARY KEY, "
                     "kullanici_girisi TEXT, sistem_cevabi TEXT, tarih TEXT)")
        conn.executemany("INSERT INTO sohbet_gecmisi VALUES (?,?,?,?)", satirlar)
        conn.commit()
        conn.close()
        return yol

    def test_gecmis_iceri_alinir(self):
        yol = self._sahte_ana_db([
            (1, "kedimin adı Pamuk", "Not aldım", "2026-07-01 10:00:00"),
            (2, "dolar kaç", "42 TL", "2026-07-02 11:00:00"),
        ])
        self.assertEqual(cl.gecmisi_iceri_al(yol), 2)
        sonuc = cl.alakali_konusmalar("kedimin adı neydi", k=2)
        self.assertTrue(sonuc)
        self.assertIn("Pamuk", sonuc[0]['soru'])

    def test_goc_artimlidir(self):
        """İkinci çağrı aynı satırları TEKRAR almamalı."""
        yol = self._sahte_ana_db([(1, "dolar kaç", "42 TL", "2026-07-02 11:00:00")])
        cl.gecmisi_iceri_al(yol)
        self.assertEqual(cl.gecmisi_iceri_al(yol), 0)
        self.assertEqual(cl.istatistik()['konusma'], 1)

    def test_gecmisteki_sir_de_filtrelenir(self):
        yol = self._sahte_ana_db([
            (1, "wifi şifrem 12345", "kaydettim", "2026-07-01 10:00:00"),
            (2, "hava nasıl", "güneşli", "2026-07-01 10:05:00"),
        ])
        self.assertEqual(cl.gecmisi_iceri_al(yol), 1)
        self.assertEqual(cl.alakali_konusmalar("wifi şifrem neydi", k=3), [])

    def test_olmayan_db_cokmeye_yol_acmaz(self):
        self.assertEqual(cl.gecmisi_iceri_al(os.path.join(self.tmp, 'yok.db')), 0)

    def test_gecmis_satirlari_niyete_siniflanir(self):
        """
        Eski kayıtlarda niyet tutulmuyordu; bugünkü regex zinciriyle tahmin
        edilmezse "en sık komutların" ilk günlerde boş kalır.
        """
        yol = self._sahte_ana_db([
            (i, "spotify aç", "Spotify başlatılıyor.", f"2026-07-0{i} 09:00:00")
            for i in range(1, 5)
        ])
        cl.gecmisi_iceri_al(yol)
        komutlar = cl.oruntuler(zorla=True)['sik_komut']
        self.assertTrue(komutlar)
        self.assertEqual(komutlar[0]['intent'], "SYSTEM_CONTROL")

    def test_basarisiz_gecmis_komutu_oruntu_olmaz(self):
        """'Bu komutu anlayamadım' ile biten tur alışkanlık sayılmamalı."""
        yol = self._sahte_ana_db([
            (i, "spotify aç", "⚠️ Bu komutu anlayamadım.", f"2026-07-0{i} 09:00:00")
            for i in range(1, 5)
        ])
        cl.gecmisi_iceri_al(yol)
        self.assertEqual(cl.oruntuler(zorla=True)['sik_komut'], [])


# =========================================================================
# KANAL ETİKETİ — "[Telegram] " öneki komutun parçası değildir
# =========================================================================
class KanalOnekiTest(OgrenmeTemeli):

    def test_ayni_komut_iki_kanaldan_tek_sayilir(self):
        cl.kaydet("[Telegram] ekran görüntüsü", "gönderildi",
                  intent="SCREENSHOT", basarili=True, kanal="12345")
        cl.kaydet("ekran görüntüsü", "alındı", intent="SCREENSHOT", basarili=True)
        cl.kaydet("[Telegram] ekran görüntüsü", "gönderildi",
                  intent="SCREENSHOT", basarili=True, kanal="12345")

        komutlar = cl.oruntuler(zorla=True)['sik_komut']

        self.assertEqual(len(komutlar), 1)
        self.assertEqual(komutlar[0]['komut'], "ekran goruntusu")
        self.assertEqual(komutlar[0]['sayi'], 3)

    def test_kanal_etiketi_konu_sayilmaz(self):
        """'telegram' kelimesi en sık konuşulan konu gibi görünüyordu."""
        for i in range(6):
            cl.kaydet(f"[Telegram] bugün hava kapalı mı {i}", "evet")
        konular = [k['kelime'] for k in cl.oruntuler(zorla=True)['konu']]
        self.assertNotIn('telegram', konular)

    def test_telefonda_ogrenilen_kalip_masaustunde_de_eslesir(self):
        for _ in range(cl.MIN_GOZLEM_KALIP):
            cl.kaydet("[Telegram] biraz kısar mısın sesi", "", kanal="12345",
                      intent="GENERAL_CONVERSATION", basarili=False)
            cl.kaydet("[Telegram] sesi kıs", "Ses %20", kanal="12345",
                      intent="SET_VOLUME", basarili=True)
        # Telefonda öğrenildi, masaüstünde (öneksiz) sorulunca da bulunmalı
        self.assertEqual(cl.ogrenilmis_intent("biraz kısar mısın sesi")[0], "SET_VOLUME")


# =========================================================================
# DAYANIKLILIK — öğrenme akışı ASLA kırmamalı
# =========================================================================
class DayaniklilikTest(OgrenmeTemeli):

    def test_db_bozuksa_kayit_sessizce_gecer(self):
        with mock.patch.object(cl, '_acik', side_effect=RuntimeError("disk dolu")):
            self.assertEqual(cl.kaydet("bir mesaj", "cevap"), 0)
            self.assertEqual(cl.alakali_konusmalar("bir mesaj"), [])
            self.assertIsNone(cl.ogrenilmis_intent("bir mesaj"))
            self.assertEqual(cl.profil_satirlari(), [])

    def test_fts_yoksa_like_yoluna_duser(self):
        cl.kaydet("staj raporu nerede", "masaüstünde", intent="FILE_SEARCH",
                  basarili=True)
        with mock.patch.object(cl, '_fts_destegi', False):
            sonuc = cl.alakali_konusmalar("staj raporu", k=2)
        self.assertTrue(sonuc)


# =========================================================================
# BORU HATTI ENTEGRASYONU — asıl regresyon riski kablolamadadır
# =========================================================================
class BoruHattiTest(OgrenmeTemeli):

    def setUp(self):
        super().setUp()
        from core.context import UltronContext
        from core.layers import pipeline_layers as pl
        self.pl = pl
        self.UltronContext = UltronContext
        # Dosya niyeti gerçek indekse gidiyor — testler kullanıcının dosyalarına
        # bağlı olmasın diye kapatılır (bu modülün konusu öğrenme).
        self.dosya_yamasi = mock.patch.object(pl, 'dosya_niyeti_coz', return_value=None)
        self.dosya_yamasi.start()

    def tearDown(self):
        self.dosya_yamasi.stop()
        super().tearDown()

    def _ctx(self, metin):
        return self.UltronContext(raw_input=metin, normalized_input=metin)

    def _aktif_kalip(self, ifade, intent):
        """
        Doğrudan aktif kalıp yazar.

        NOT: Test cümlesi regex'in GERÇEKTEN kaçırdığı bir ifade olmalı —
        "sesi kıs" gibi bir cümleyi zaten `SET_VOLUME` regex'i yakalıyor ve
        test öğrenmeyi değil regex'i ölçmüş oluyordu.
        """
        with cl._acik() as conn:
            for _ in range(cl.MIN_GOZLEM_KALIP):
                cl._kalip_yaz(conn, cl.sadelestir(ifade), intent, ifade)

    def test_rapor_komutu_niyete_baglanir(self):
        ctx = self.pl.IntentAnalyzerLayer().process(self._ctx("ne öğrendin"))
        self.assertEqual(ctx.intent, "LEARNING_REPORT")

    def test_ogrenilmis_kalip_niyeti_belirler(self):
        # Önce regex'in bu cümleyi GERÇEKTEN kaçırdığını doğrula
        ham = self.pl.IntentAnalyzerLayer().process(self._ctx("kulaklarım patlıyor"))
        self.assertEqual(ham.intent, "GENERAL_CONVERSATION")

        self._aktif_kalip("kulaklarım patlıyor", "SET_VOLUME")
        ctx = self.pl.IntentAnalyzerLayer().process(self._ctx("kulaklarım patlıyor"))

        self.assertEqual(ctx.intent, "SET_VOLUME")
        self.assertEqual(ctx.intent_source, "ogrenilmis")

    def test_ogrenilmis_kalip_sessiz_uygulanmaz(self):
        """Kullanıcı hangi kalıbın devreye girdiğini GÖRMELİ — yanlışsa silebilsin."""
        self._aktif_kalip("kulaklarım patlıyor", "SET_VOLUME")

        ctx = self.pl.IntentAnalyzerLayer().process(self._ctx("kulaklarım patlıyor"))

        self.assertIn("öğrenilmiş kalıp", ctx.ogrenme_notu)
        self.assertIn("kulaklarım patlıyor", ctx.ogrenme_notu)

    def test_ogrenilmemis_cumle_sohbette_kalir(self):
        ctx = self.pl.IntentAnalyzerLayer().process(self._ctx("bugün kendimi iyi hissediyorum"))
        self.assertEqual(ctx.intent, "GENERAL_CONVERSATION")
        self.assertEqual(ctx.ogrenme_notu, "")

    def test_sohbette_gecmis_arsivi_prompta_girer(self):
        cl.kaydet("kedimin adı Pamuk", "Not aldım.", intent="NOTE_TAKE", basarili=True)
        ctx = self._ctx("kedimin adı neydi")
        ctx.intent = "GENERAL_CONVERSATION"

        ctx = self.pl.MemoryContextLayer(None, {}).process(ctx)
        ctx = self.pl.PromptGeneratorLayer().process(ctx)

        self.assertIn("Pamuk", ctx.enriched_prompt)
        self.assertIn("GEÇMİŞ KONUŞMA ARŞİVİ", ctx.enriched_prompt)

    def test_deterministik_komut_arsive_sorgu_atmaz(self):
        """'chrome aç' cevabını araç üretir; arşive gitmek boşuna gecikmedir."""
        ctx = self._ctx("chrome aç")
        ctx.intent = "SYSTEM_CONTROL"
        with mock.patch.object(cl, 'prompt_blogu') as sahte:
            self.pl.MemoryContextLayer(None, {}).process(ctx)
        sahte.assert_not_called()

    def test_ogrenme_araci_deftere_kayitli(self):
        from core.tools import DEFTER
        import core.builtin_tools  # noqa: F401
        arac = DEFTER.intent_ile("LEARNING_REPORT")
        self.assertIsNotNone(arac)
        sonuc = arac.calistir(metin="ne öğrendin")
        self.assertTrue(sonuc.islendi and sonuc.basarili)
        self.assertIn("ÖĞREN", sonuc.mesaj.upper())

    def test_arac_unut_komutunu_yurutur(self):
        from core.tools import DEFTER
        import core.builtin_tools  # noqa: F401
        self._aktif_kalip("kulaklarım patlıyor", "SET_VOLUME")

        sonuc = DEFTER.intent_ile("LEARNING_REPORT").calistir(
            metin="şunu unut: kulaklarım patlıyor")

        self.assertIn("Unuttum", sonuc.mesaj)
        self.assertIsNone(cl.ogrenilmis_intent("kulaklarım patlıyor"))


# =========================================================================
# RUH HÂLİ × ARŞİV
# Duygu ayrı bir tabloda dururken "%40 negatif"ten fazlası söylenemiyordu.
# Turun YANINDA durunca "ne zaman" ve "neyden bahsederken" cevaplanabiliyor.
# =========================================================================
class RuhHaliOruntusu(OgrenmeTemeli):

    def _yaz(self, cumle, ruh, saat, sayi=1):
        with cl._acik() as conn:
            for i in range(sayi):
                conn.execute(
                    "INSERT INTO konusma (kanal, kullanici, ultron, sade, intent, "
                    "basarili, kaynak, tarih, saat, gun, ruh_hali) "
                    "VALUES ('desktop', ?, 'peki', ?, 'GENERAL_CONVERSATION', 0, "
                    "'canli', ?, ?, 0, ?)",
                    (cumle, cl.sadelestir(cumle),
                     f"2026-07-{(i % 28) + 1:02d} {saat:02d}:10:00", saat, ruh))
            conn.commit()
        cl._onbellegi_dusur()

    def test_ruh_hali_kayitla_birlikte_yazilir(self):
        cl.kaydet("bugün berbat geçti", "Üzgünüm.", intent="GENERAL_CONVERSATION",
                  ruh_hali='negatif')
        with cl._acik() as conn:
            satir = conn.execute("SELECT ruh_hali FROM konusma").fetchone()
        self.assertEqual(satir[0], 'negatif')

    def test_dagilim_ve_konu_cikarilir(self):
        self._yaz("sınav çok kötü geçti", 'negatif', 20, sayi=4)
        self._yaz("harika bir gündü", 'pozitif', 12, sayi=3)

        ruh = cl.oruntuler(zorla=True)['ruh_hali']
        self.assertEqual(ruh['toplam'], 7)
        self.assertEqual(ruh['dagilim']['negatif'], 4)
        self.assertIn('sinav', [k['kelime'] for k in ruh['konu']])

    def test_yogunlasma_yoksa_dilim_bildirilmez(self):
        """Güne eşit dağılmış duygu bir örüntü değildir; öyle sunmak uydurmaktır."""
        self._yaz("moralim bozuk", 'negatif', 20, sayi=3)
        self._yaz("keyfim yerinde", 'pozitif', 20, sayi=5)
        self.assertIsNone(cl.oruntuler(zorla=True)['ruh_hali']['dilim'])

    def test_yogunlasma_varsa_dilim_bildirilir(self):
        self._yaz("çok yoruldum", 'negatif', 23, sayi=5)
        z = cl.oruntuler(zorla=True)['ruh_hali']['dilim']
        self.assertIsNotNone(z)
        self.assertEqual(z['dilim'], 'gece')

    def test_ruh_hali_prompt_profiline_girmez(self):
        """
        Rapora girer, PROMPT'a girmez. Modele "kullanıcı gergin" demek onu
        terapiste çevirir; küçük model zaten yorum yapmaya hevesli.
        """
        self._yaz("her şey berbat", 'negatif', 22, sayi=6)
        birlesik = " ".join(cl.profil_satirlari(azami=10))
        for kelime in ('negatif', 'pozitif', 'ruh', 'keyif'):
            self.assertNotIn(kelime, birlesik.lower())

    def test_yetersiz_olcum_raporlanmaz(self):
        self._yaz("iyi değilim", 'negatif', 21, sayi=2)
        self.assertEqual(cl.oruntuler(zorla=True)['ruh_hali']['toplam'], 0)


if __name__ == '__main__':
    unittest.main()
