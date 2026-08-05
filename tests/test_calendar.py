# -*- coding: utf-8 -*-
"""
Takvim testleri (features/calendar_tools.py).

EN KRİTİK TESTLER — hepsi "sessizce yanlış" bir davranışı kilitler:

  • `test_senkron_yerel_etkinlige_dokunmaz` — ICS senkronu kullanıcının kendi
    yazdığı etkinliği silerse veri kaybıdır ve fark edilmez.
  • `test_utc_saat_yerele_cevrilir` — 'Z' eki çevrilmezse Türkiye'de HER
    toplantı 3 saat kaymış görünür; özellik işe yaramaz hâle gelir.
  • `test_yineleyen_etkinlik_ayri_uid_alir` — aynı uid ile yazılan tekrarlar
    UNIQUE kısıtında birbirini ezer, haftalık toplantı tek kez görünür.
  • `test_hatirlat_diyen_cumleye_el_koymaz` / `test_zamanlayici_cumlesine_el_koymaz`
    — takvim kapısı niyet zincirinde ÖNCE sorulduğu için, komşu modüllerin
    cümlelerini yutması en olası hatadır.
  • `test_takvimi_goster_dosya_niyetine_kacmaz` — "göster" bir dosya arama
    fiilidir; kapı olmasaydı komut 134 bin dosyalık indekse giderdi.
  • `test_zamansiz_cumle_bugune_yazilmaz` — zamanı anlaşılmayan etkinliği
    bugüne kaydetmek, kullanıcının göremeyeceği bir yanlıştır.
  • `test_dis_kaynakli_etkinlik_silinmez` — "sildim" deyip sonraki senkronda
    geri getirmek yalan söylemektir.

İZOLASYON: tüm testler bellek içi SQLite kullanır; ağ zırhla kapalıdır.
"""

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from features import calendar_tools as tk


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


# 2026-08-05 bir ÇARŞAMBA — gün adı testleri buna dayanır.
SIMDI = datetime(2026, 8, 5, 10, 0, 0)


class TakvimTemeli(unittest.TestCase):
    """Bellek içi DB + gerçek şemanın takvim/hatırlatma tabloları."""

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE hatirlatmalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metin TEXT NOT NULL,
                hedef_tarih TIMESTAMP,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                durum TEXT DEFAULT 'bekliyor'
            )
        """)
        tk.tabloyu_hazirla(self.cursor, self.conn)
        # Kullanıcının gerçek config'i okunmasın (hatırlatma dakikası sabitlensin)
        self.config_yama = mock.patch.object(tk, '_config', return_value={})
        self.config_yama.start()

    def tearDown(self):
        self.config_yama.stop()
        self.conn.close()


# ===========================================================================
# TARİH ÇÖZÜMÜ
# ===========================================================================
class TarihCozumu(unittest.TestCase):

    def test_yarin_saat(self):
        c = tk.tarih_coz("yarın 14:00 toplantı", SIMDI)
        self.assertEqual(c['baslangic'], datetime(2026, 8, 6, 14, 0))
        self.assertFalse(c['tum_gun'])

    def test_gun_adi_gelecek_gune_gider(self):
        # Çarşamba günü "cuma" denince bu haftanın cuması (7 Ağustos)
        c = tk.tarih_coz("cuma saat 9'da doktor", SIMDI)
        self.assertEqual(c['baslangic'], datetime(2026, 8, 7, 9, 0))

    def test_ay_adiyla_tarih_tum_gun_olur(self):
        c = tk.tarih_coz("15 ağustos tatil", SIMDI)
        self.assertEqual(c['baslangic'].date(), datetime(2026, 8, 15).date())
        self.assertTrue(c['tum_gun'])

    def test_gecmis_tarih_gelecek_yila_kayar(self):
        # Ağustos'ta "3 mart" denmişse gelecek yılın martı kastediliyor
        c = tk.tarih_coz("3 mart sınav", SIMDI)
        self.assertEqual(c['baslangic'].year, 2027)

    def test_yilli_tarih_ve_saat(self):
        c = tk.tarih_coz("15.08.2026 10:30 sunum", SIMDI)
        self.assertEqual(c['baslangic'], datetime(2026, 8, 15, 10, 30))

    def test_noktali_sayi_saat_okunur(self):
        """'14.05' saat olarak okunur — tarih sanılıp yanlış güne yazılmamalı."""
        c = tk.tarih_coz("yarın 14.05 toplantı", SIMDI)
        self.assertEqual(c['baslangic'], datetime(2026, 8, 6, 14, 5))

    def test_saat_olamayacak_nokta_tarih_olur(self):
        """'25.12' geçerli bir saat değil → tarih olarak okunur."""
        c = tk.tarih_coz("25.12 yılbaşı programı", SIMDI)
        self.assertEqual(c['baslangic'].month, 12)
        self.assertEqual(c['baslangic'].day, 25)

    def test_aksam_saati_ogleden_sonraya_kayar(self):
        c = tk.tarih_coz("yarın akşam 8 yemek", SIMDI)
        self.assertEqual(c['baslangic'].hour, 20)

    def test_saat_araligi_bitis_uretir(self):
        c = tk.tarih_coz("yarın 14:00-16:00 çalıştay", SIMDI)
        self.assertEqual(c['bitis'], datetime(2026, 8, 6, 16, 0))

    def test_sure_bitis_uretir(self):
        c = tk.tarih_coz("yarın 14:00 2 saatlik toplantı", SIMDI)
        self.assertEqual(c['bitis'], datetime(2026, 8, 6, 16, 0))

    def test_zaman_yoksa_none_doner(self):
        """Zamansız cümle SESSİZCE bugüne yazılmamalı."""
        self.assertIsNone(tk.tarih_coz("toplantı ekle", SIMDI))

    def test_gecmis_saat_yarina_kayar(self):
        # Saat 10:00'da "saat 9'da" denmişse yarın kastediliyor
        c = tk.tarih_coz("saat 9'da spor", SIMDI)
        self.assertEqual(c['baslangic'].date(), datetime(2026, 8, 6).date())

    def test_buyuk_I_harfi_kaliplari_bozmaz(self):
        """'İ'.lower() birleşen nokta üretir — sadeleştirme bunu yutmalı."""
        self.assertEqual(tk._sade("İSTANBUL Toplantısı"), "istanbul toplantisi")


# ===========================================================================
# NİYET KAPISI — komşu modüllerin cümlelerine el koymamalı
# ===========================================================================
class NiyetKapisi(unittest.TestCase):

    def test_takvim_cumleleri_taninir(self):
        for cumle in ["takvimi göster", "takvimimde ne var", "bugün ne var",
                      "yarın ne var", "bu hafta programım ne",
                      "takvime yarın 14:00 toplantı ekle",
                      "sıradaki toplantım ne zaman", "ajandamı listele"]:
            with self.subTest(cumle=cumle):
                self.assertTrue(tk.takvim_niyeti_algila(cumle))

    def test_hatirlat_diyen_cumleye_el_koymaz(self):
        for cumle in ["yarın 14:00 toplantıyı hatırlat",
                      "saat 9'da ilaç almayı hatırlat",
                      "randevumu hatırlat"]:
            with self.subTest(cumle=cumle):
                self.assertFalse(tk.takvim_niyeti_algila(cumle))

    def test_zamanlayici_cumlesine_el_koymaz(self):
        for cumle in ["zamanla: 09:30 hava durumu",
                      "her gün 22:00 akşam raporu",
                      "her sabah 08:00 brifing gönder"]:
            with self.subTest(cumle=cumle):
                self.assertFalse(tk.takvim_niyeti_algila(cumle))

    def test_alakasiz_cumlelere_el_koymaz(self):
        for cumle in ["chrome aç", "5 dakika sayaç kur", "dolar kaç",
                      "notlarımı göster", "ekran görüntüsü al",
                      "staj raporunu anneme gönder", "hava nasıl"]:
            with self.subTest(cumle=cumle):
                self.assertFalse(tk.takvim_niyeti_algila(cumle))


class NiyetZinciri(unittest.TestCase):
    """Kapının GERÇEK zincirde doğru sırada olduğunu doğrular."""

    def _intent(self, cumle):
        from core.context import UltronContext
        from core.layers.pipeline_layers import IntentAnalyzerLayer
        ctx = UltronContext(raw_input=cumle, normalized_input=cumle)
        # hafif=True: gerçek dosya indeksine ve LLM'e gidilmesin
        return IntentAnalyzerLayer({}).process(ctx, hafif=True).intent

    def test_takvimi_goster_dosya_niyetine_kacmaz(self):
        self.assertEqual(self._intent("takvimi göster"), "CALENDAR")

    def test_takvime_ekleme_calendar_olur(self):
        self.assertEqual(self._intent("takvime yarın 14:00 toplantı ekle"), "CALENDAR")

    def test_hatirlatma_intenti_korunur(self):
        self.assertEqual(self._intent("yarın 14:00 toplantıyı hatırlat"),
                         "CREATE_REMINDER")

    def test_zamanlama_intenti_korunur(self):
        # NOT: "her gün 22:00 akşam raporu" bilerek kullanılmadı — zincirde
        # EVENING_REPORT, SCHEDULE_TASK'tan ÖNCE geliyor (takvimden bağımsız,
        # önceden var olan bir sıralama).
        self.assertEqual(self._intent("zamanla: 09:30 hava durumu"), "SCHEDULE_TASK")
        self.assertEqual(self._intent("her gün 21:00 dolar kaç"), "SCHEDULE_TASK")

    def test_sistem_komutu_korunur(self):
        self.assertEqual(self._intent("chrome aç"), "SYSTEM_CONTROL")


# ===========================================================================
# YEREL CRUD
# ===========================================================================
class YerelTakvim(TakvimTemeli):

    def test_ekle_ve_listele(self):
        tk.etkinlik_ekle(self.cursor, self.conn, "Diş randevusu",
                         datetime(2026, 8, 6, 14, 0), hatirlatma_dk=0)
        satirlar = tk.etkinlikleri_getir(self.cursor, datetime(2026, 8, 6),
                                         datetime(2026, 8, 7))
        self.assertEqual(len(satirlar), 1)
        self.assertEqual(satirlar[0][1], "Diş randevusu")

    def test_bitissiz_etkinlik_bir_saat_surer(self):
        tk.etkinlik_ekle(self.cursor, self.conn, "Toplantı",
                         datetime(2026, 8, 6, 14, 0), hatirlatma_dk=0)
        satir = tk.etkinlikleri_getir(self.cursor, datetime(2026, 8, 6),
                                      datetime(2026, 8, 7))[0]
        self.assertEqual(satir[3], "2026-08-06 15:00:00")

    def test_hatirlatma_koprusu_kurulur(self):
        gelecek = datetime.now() + timedelta(days=2)
        _id, kuruldu = tk.etkinlik_ekle(self.cursor, self.conn, "Sunum",
                                        gelecek, hatirlatma_dk=15)
        self.assertTrue(kuruldu)
        self.cursor.execute("SELECT metin FROM hatirlatmalar")
        self.assertIn("Sunum", self.cursor.fetchone()[0])

    def test_gecmis_etkinlige_hatirlatma_kurulmaz(self):
        """Geçmişe kurulan hatırlatma otonom döngüde ANINDA patlar."""
        _id, kuruldu = tk.etkinlik_ekle(self.cursor, self.conn, "Eski",
                                        datetime(2020, 1, 1, 10, 0),
                                        hatirlatma_dk=15)
        self.assertFalse(kuruldu)
        self.cursor.execute("SELECT COUNT(*) FROM hatirlatmalar")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_yerel_etkinlik_silinir(self):
        eid, _ = tk.etkinlik_ekle(self.cursor, self.conn, "Silinecek",
                                  datetime(2026, 8, 6, 14, 0), hatirlatma_dk=0)
        cevap = tk.etkinlik_sil(self.cursor, self.conn, eid)
        self.assertIn("silindi", cevap)
        self.assertEqual(len(tk.etkinlikleri_getir(
            self.cursor, datetime(2026, 8, 1), datetime(2026, 9, 1))), 0)

    def test_dis_kaynakli_etkinlik_silinmez(self):
        """Silip 'sildim' demek yalan olur — sonraki senkron geri getirir."""
        eid, _ = tk.etkinlik_ekle(self.cursor, self.conn, "Google toplantısı",
                                  datetime(2026, 8, 6, 14, 0),
                                  kaynak="ics:google.com", dis_uid="abc",
                                  hatirlatma_dk=0)
        cevap = tk.etkinlik_sil(self.cursor, self.conn, eid)
        self.assertIn("dış takvimden", cevap)
        self.assertEqual(len(tk.etkinlikleri_getir(
            self.cursor, datetime(2026, 8, 1), datetime(2026, 9, 1))), 1)

    def test_olmayan_etkinlik_silinmez(self):
        self.assertIn("bulunamadı", tk.etkinlik_sil(self.cursor, self.conn, 999))

    def test_sonraki_etkinlik(self):
        tk.etkinlik_ekle(self.cursor, self.conn, "Yakın",
                         datetime.now() + timedelta(hours=2), hatirlatma_dk=0)
        tk.etkinlik_ekle(self.cursor, self.conn, "Uzak",
                         datetime.now() + timedelta(days=5), hatirlatma_dk=0)
        self.assertEqual(tk.sonraki_etkinlik(self.cursor)[1], "Yakın")


# ===========================================================================
# KOMUT AKIŞI
# ===========================================================================
class KomutAkisi(TakvimTemeli):

    def test_ekleme_komutu(self):
        islendi, cevap = tk.takvim_komutu_algila(
            "takvime yarın 14:00 diş randevusu ekle", self.cursor, self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("Takvime eklendi", cevap)
        self.assertIn("randevu", cevap.lower())

    def test_zamansiz_cumle_bugune_yazilmaz(self):
        islendi, cevap = tk.takvim_komutu_algila(
            "takvime toplantı ekle", self.cursor, self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("ne zaman", cevap)
        self.cursor.execute("SELECT COUNT(*) FROM takvim_etkinlikleri")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_baslik_temizlenir(self):
        tk.takvim_komutu_algila("takvime yarın 15:00 Ahmet ile toplantı ekle",
                                self.cursor, self.conn, SIMDI)
        self.cursor.execute("SELECT baslik FROM takvim_etkinlikleri")
        baslik = self.cursor.fetchone()[0]
        self.assertIn("Ahmet", baslik)
        self.assertNotIn("takvime", baslik.lower())
        self.assertNotIn("15:00", baslik)

    def test_turkce_zaman_ifadesi_baslikta_kalmaz(self):
        """
        Zaman parçaları SADE metinden ("aksam 8") çıkar, başlık HAM metinden
        üretilir ("akşam 8"). Ters fold olmazsa etkinlik
        "akşam 8 Ahmet ile yemek" adıyla kaydediliyordu.
        """
        tk.takvim_komutu_algila("takvime cuma akşam 8 Ahmet ile yemek ekle",
                                self.cursor, self.conn, SIMDI)
        self.cursor.execute("SELECT baslik, baslangic FROM takvim_etkinlikleri")
        baslik, baslangic = self.cursor.fetchone()
        self.assertEqual(baslik, "Ahmet ile yemek")
        self.assertTrue(baslangic.endswith("20:00:00"))

    def test_ay_adi_baslikta_kalmaz(self):
        tk.takvim_komutu_algila("takvime 15 ağustos tatil ekle",
                                self.cursor, self.conn, SIMDI)
        self.cursor.execute("SELECT baslik FROM takvim_etkinlikleri")
        self.assertEqual(self.cursor.fetchone()[0], "tatil")

    def test_listeleme_komutu(self):
        tk.etkinlik_ekle(self.cursor, self.conn, "Spor",
                         datetime(2026, 8, 5, 18, 0), hatirlatma_dk=0)
        islendi, cevap = tk.takvim_komutu_algila("bugün ne var", self.cursor,
                                                 self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("Spor", cevap)

    def test_bos_gun_bos_der(self):
        islendi, cevap = tk.takvim_komutu_algila("yarın ne var", self.cursor,
                                                 self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("etkinlik yok", cevap)

    def test_listeleme_ekleme_sanilmaz(self):
        """'takvimde ne var' bir SORGUDUR — boş bir etkinlik yaratmamalı."""
        tk.takvim_komutu_algila("takvimde ne var", self.cursor, self.conn, SIMDI)
        self.cursor.execute("SELECT COUNT(*) FROM takvim_etkinlikleri")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_yineleyen_istek_sessizce_tek_sefere_indirgenmez(self):
        islendi, cevap = tk.takvim_komutu_algila(
            "takvime her salı 14:00 toplantı ekle", self.cursor, self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("Yinelenen", cevap)
        self.cursor.execute("SELECT COUNT(*) FROM takvim_etkinlikleri")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_alakasiz_cumle_ustlenilmez(self):
        islendi, _ = tk.takvim_komutu_algila("nasılsın", self.cursor,
                                             self.conn, SIMDI)
        self.assertFalse(islendi)

    def test_silme_komutu(self):
        eid, _ = tk.etkinlik_ekle(self.cursor, self.conn, "Gereksiz",
                                  datetime(2026, 8, 6, 14, 0), hatirlatma_dk=0)
        islendi, cevap = tk.takvim_komutu_algila(
            f"takvimden {eid} numaralı etkinliği sil", self.cursor, self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("silindi", cevap)

    def test_kaynak_yoksa_senkron_yol_gosterir(self):
        islendi, cevap = tk.takvim_komutu_algila("takvimi senkronize et",
                                                 self.cursor, self.conn, SIMDI)
        self.assertTrue(islendi)
        self.assertIn("iCal", cevap)


class AralikCozumu(unittest.TestCase):

    def test_bugun(self):
        bas, son, etiket = tk.aralik_coz("bugün ne var", SIMDI)
        self.assertEqual(bas, datetime(2026, 8, 5))
        self.assertEqual(son, datetime(2026, 8, 6))
        self.assertEqual(etiket, "Bugün")

    def test_yarin(self):
        bas, _son, etiket = tk.aralik_coz("yarın ne var", SIMDI)
        self.assertEqual(bas, datetime(2026, 8, 6))
        self.assertEqual(etiket, "Yarın")

    def test_bu_hafta_pazartesiye_kadar(self):
        bas, son, _e = tk.aralik_coz("bu hafta ne var", SIMDI)
        self.assertEqual(bas, datetime(2026, 8, 5))
        self.assertEqual(son, datetime(2026, 8, 10))   # gelecek pazartesi

    def test_hafta_sonu(self):
        bas, son, _e = tk.aralik_coz("hafta sonu ne var", SIMDI)
        self.assertEqual(bas, datetime(2026, 8, 8))    # cumartesi
        self.assertEqual(son, datetime(2026, 8, 10))

    def test_varsayilan_yedi_gun(self):
        bas, son, etiket = tk.aralik_coz("takvimim", SIMDI)
        self.assertEqual((son - bas).days, 7)
        self.assertIn("7 gün", etiket)


# ===========================================================================
# ICS AYRIŞTIRMA
# ===========================================================================
def _ics(govde: str) -> str:
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + govde + "\r\nEND:VCALENDAR"


class IcsAyristirma(unittest.TestCase):

    PENCERE_BAS = datetime(2026, 1, 1)
    PENCERE_SON = datetime(2027, 1, 1)

    def _coz(self, govde):
        return tk.ics_ayristir(_ics(govde), self.PENCERE_BAS, self.PENCERE_SON)

    def test_basit_etkinlik(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:1\r\nSUMMARY:Toplantı\r\n"
                      "DTSTART:20260815T140000\r\nDTEND:20260815T150000\r\n"
                      "LOCATION:Ofis\r\nEND:VEVENT")
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]['baslik'], "Toplantı")
        self.assertEqual(e[0]['baslangic'], datetime(2026, 8, 15, 14, 0))
        self.assertEqual(e[0]['bitis'], datetime(2026, 8, 15, 15, 0))
        self.assertEqual(e[0]['yer'], "Ofis")

    def test_utc_saat_yerele_cevrilir(self):
        """'Z' çevrilmezse Türkiye'de her toplantı 3 saat kayar."""
        e = self._coz("BEGIN:VEVENT\r\nUID:2\r\nSUMMARY:UTC\r\n"
                      "DTSTART:20260815T110000Z\r\nEND:VEVENT")
        beklenen = datetime(2026, 8, 15, 11, 0, tzinfo=timezone.utc) \
            .astimezone().replace(tzinfo=None)
        self.assertEqual(e[0]['baslangic'], beklenen)

    def test_tum_gun_etkinligi(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:3\r\nSUMMARY:Tatil\r\n"
                      "DTSTART;VALUE=DATE:20260815\r\nEND:VEVENT")
        self.assertTrue(e[0]['tum_gun'])
        self.assertEqual(e[0]['baslangic'], datetime(2026, 8, 15, 0, 0))

    def test_satir_katlamasi_acilir(self):
        # RFC 5545 katlaması CRLF + TEK boşluk ekler ve açılışta ikisi de atılır
        # → kelime ortasından bölünür. Boşluk eklemek metni bozar.
        e = self._coz("BEGIN:VEVENT\r\nUID:4\r\nSUMMARY:Cok uzun bir baslik de\r\n"
                      " vam ediyor\r\nDTSTART:20260815T140000\r\nEND:VEVENT")
        self.assertEqual(e[0]['baslik'], "Cok uzun bir baslik devam ediyor")

    def test_kacislar_cozulur(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:5\r\nSUMMARY:Ali\\, Veli\r\n"
                      "DESCRIPTION:birinci\\nikinci\r\n"
                      "DTSTART:20260815T140000\r\nEND:VEVENT")
        self.assertEqual(e[0]['baslik'], "Ali, Veli")
        self.assertIn("\n", e[0]['aciklama'])

    def test_degerdeki_iki_nokta_bozmaz(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:6\r\nSUMMARY:Görüşme\r\n"
                      "LOCATION:https://meet.google.com/abc\r\n"
                      "DTSTART:20260815T140000\r\nEND:VEVENT")
        self.assertEqual(e[0]['yer'], "https://meet.google.com/abc")

    def test_haftalik_tekrar_acilir(self):
        # 3 Ağustos 2026 pazartesi; MO,WE × 4 tekrar
        e = self._coz("BEGIN:VEVENT\r\nUID:7\r\nSUMMARY:Standup\r\n"
                      "DTSTART:20260803T100000\r\n"
                      "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4\r\nEND:VEVENT")
        tarihler = sorted(x['baslangic'].date() for x in e)
        self.assertEqual(len(e), 4)
        self.assertEqual(tarihler[0], datetime(2026, 8, 3).date())
        self.assertEqual(tarihler[-1], datetime(2026, 8, 12).date())

    def test_yineleyen_etkinlik_ayri_uid_alir(self):
        """Aynı uid ile yazılan tekrarlar UNIQUE kısıtında birbirini ezer."""
        e = self._coz("BEGIN:VEVENT\r\nUID:8\r\nSUMMARY:Günlük\r\n"
                      "DTSTART:20260803T100000\r\n"
                      "RRULE:FREQ=DAILY;COUNT=3\r\nEND:VEVENT")
        self.assertEqual(len({x['uid'] for x in e}), 3)

    def test_until_tekrari_sinirlar(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:9\r\nSUMMARY:Sinirli\r\n"
                      "DTSTART:20260803T100000\r\n"
                      "RRULE:FREQ=DAILY;UNTIL=20260805T235900\r\nEND:VEVENT")
        self.assertEqual(len(e), 3)

    def test_exdate_haric_tutulur(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:10\r\nSUMMARY:Atlamali\r\n"
                      "DTSTART:20260803T100000\r\n"
                      "RRULE:FREQ=DAILY;COUNT=3\r\n"
                      "EXDATE:20260804T100000\r\nEND:VEVENT")
        gunler = {x['baslangic'].day for x in e}
        self.assertNotIn(4, gunler)
        self.assertEqual(len(e), 2)

    def test_desteklenmeyen_rrule_tek_tarih_verir(self):
        """Anlaşılmayan kuralı uydurmaktansa eksik göster."""
        e = self._coz("BEGIN:VEVENT\r\nUID:11\r\nSUMMARY:Garip\r\n"
                      "DTSTART:20260803T100000\r\n"
                      "RRULE:FREQ=SECONDLY;COUNT=5\r\nEND:VEVENT")
        self.assertEqual(len(e), 1)

    def test_bozuk_etkinlik_dosyayi_dusurmez(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:12\r\nSUMMARY:Tarihsiz\r\nEND:VEVENT\r\n"
                      "BEGIN:VEVENT\r\nUID:13\r\nSUMMARY:Saglam\r\n"
                      "DTSTART:20260815T140000\r\nEND:VEVENT")
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]['baslik'], "Saglam")

    def test_pencere_disi_etkinlik_alinmaz(self):
        e = self._coz("BEGIN:VEVENT\r\nUID:14\r\nSUMMARY:Cok eski\r\n"
                      "DTSTART:20100101T100000\r\nEND:VEVENT")
        self.assertEqual(e, [])

    def test_bos_metin_coker_mez(self):
        self.assertEqual(tk.ics_ayristir(""), [])


# ===========================================================================
# SENKRON
# ===========================================================================
class Senkron(TakvimTemeli):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix='ultron_takvim_')
        self.ics_yolu = os.path.join(self.tmp, 'is.ics')
        self._yaz("BEGIN:VEVENT\r\nUID:a1\r\nSUMMARY:Sprint\r\n"
                  "DTSTART:{}T140000\r\nEND:VEVENT".format(
                      (datetime.now() + timedelta(days=3)).strftime('%Y%m%d')))

    def _yaz(self, govde):
        with open(self.ics_yolu, 'w', encoding='utf-8') as f:
            f.write(_ics(govde))

    def test_yerel_dosyadan_senkron(self):
        sayi, hatalar = tk.ics_senkronize(self.cursor, self.conn, [self.ics_yolu])
        self.assertEqual(sayi, 1)
        self.assertEqual(hatalar, [])

    def test_senkron_yerel_etkinlige_dokunmaz(self):
        """EN KRİTİK: senkron kullanıcının kendi kaydını silerse veri kaybıdır."""
        tk.etkinlik_ekle(self.cursor, self.conn, "Benim etkinliğim",
                         datetime.now() + timedelta(days=3), hatirlatma_dk=0)
        tk.ics_senkronize(self.cursor, self.conn, [self.ics_yolu])
        self.cursor.execute("SELECT COUNT(*) FROM takvim_etkinlikleri WHERE kaynak = ?",
                            (tk.KAYNAK_YEREL,))
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_iki_kez_senkron_cogaltmaz(self):
        tk.ics_senkronize(self.cursor, self.conn, [self.ics_yolu])
        tk.ics_senkronize(self.cursor, self.conn, [self.ics_yolu])
        self.cursor.execute("SELECT COUNT(*) FROM takvim_etkinlikleri")
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_kaynaktan_silinen_etkinlik_gider(self):
        tk.ics_senkronize(self.cursor, self.conn, [self.ics_yolu])
        self._yaz("BEGIN:VEVENT\r\nUID:a2\r\nSUMMARY:Yeni\r\n"
                  "DTSTART:{}T140000\r\nEND:VEVENT".format(
                      (datetime.now() + timedelta(days=4)).strftime('%Y%m%d')))
        tk.ics_senkronize(self.cursor, self.conn, [self.ics_yolu])
        self.cursor.execute("SELECT baslik FROM takvim_etkinlikleri")
        basliklar = [r[0] for r in self.cursor.fetchall()]
        self.assertEqual(basliklar, ["Yeni"])

    def test_ulasilamayan_kaynak_hata_olarak_doner(self):
        sayi, hatalar = tk.ics_senkronize(self.cursor, self.conn,
                                          ["https://olmayan.example/takvim.ics"])
        self.assertEqual(sayi, 0)
        self.assertEqual(len(hatalar), 1)

    def test_kaynak_yoksa_sessiz_doner(self):
        self.assertEqual(tk.ics_senkronize(self.cursor, self.conn, []), (0, []))


# ===========================================================================
# DIŞA AKTARIM
# ===========================================================================
class DisaAktarim(TakvimTemeli):

    def test_gidis_donus(self):
        """Dışa aktarılan dosya geri okunabilmeli (round-trip)."""
        tk.etkinlik_ekle(self.cursor, self.conn, "Sunum, önemli",
                         datetime.now() + timedelta(days=2, hours=3),
                         yer="Ofis", hatirlatma_dk=0)
        hedef = os.path.join(tempfile.mkdtemp(prefix='ultron_ics_'), 'c.ics')
        tk.ics_disa_aktar(self.cursor, hedef)

        with open(hedef, encoding='utf-8') as f:
            geri = tk.ics_ayristir(f.read(), datetime.now() - timedelta(days=1),
                                   datetime.now() + timedelta(days=30))
        self.assertEqual(len(geri), 1)
        self.assertEqual(geri[0]['baslik'], "Sunum, önemli")
        self.assertEqual(geri[0]['yer'], "Ofis")

    def test_dis_kaynakli_etkinlik_disa_aktarilmaz(self):
        """Google'dan gelen etkinliği geri Google'a vermek çoğaltma üretir."""
        tk.etkinlik_ekle(self.cursor, self.conn, "Disaridan",
                         datetime.now() + timedelta(days=2),
                         kaynak="ics:google.com", dis_uid="z1", hatirlatma_dk=0)
        hedef = os.path.join(tempfile.mkdtemp(prefix='ultron_ics_'), 'c.ics')
        tk.ics_disa_aktar(self.cursor, hedef)
        with open(hedef, encoding='utf-8') as f:
            self.assertNotIn("Disaridan", f.read())


# ===========================================================================
# BRİFİNG KÖPRÜSÜ
# ===========================================================================
class BrifingKoprusu(TakvimTemeli):

    def test_etkinlik_yoksa_none(self):
        self.assertIsNone(tk.gun_ozeti(self.cursor, 0))

    def test_bugunku_etkinlik_ozeti(self):
        tk.etkinlik_ekle(self.cursor, self.conn, "Doktor",
                         datetime.now().replace(hour=23, minute=0, second=0,
                                                microsecond=0),
                         hatirlatma_dk=0)
        ozet = tk.gun_ozeti(self.cursor, 0)
        self.assertIn("Doktor", ozet)
        self.assertIn("23:00", ozet)

    def test_brifing_bolumu_bos_takvimde_hata_demez(self):
        """'Etkinlik yok' ile 'takvim okunamadı' farklı şeylerdir."""
        from features.briefing import _bugunku_etkinlikler
        cevap = _bugunku_etkinlikler(self.cursor)
        self.assertNotIn("okunamadı", cevap)

    def test_cuma_gunu_saat_araligi_baslik_temizleme(self):
        """'cuma günü saat 15:00-16:00 projenin sunumu var takvime ekle' başlıkta 'günü' bırakmamalı."""
        ok, cevap = tk.takvim_komutu_algila(
            "cuma günü saat 15:00-16:00 projenin sunumu var takvime ekle",
            self.cursor, self.conn, SIMDI
        )
        self.assertTrue(ok)
        self.assertIn("projenin sunumu", cevap)
        self.assertNotIn("günü projenin sunumu", cevap)


if __name__ == '__main__':
    unittest.main()
