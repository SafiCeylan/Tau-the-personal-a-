# -*- coding: utf-8 -*-
"""
Öneri Motoru testleri (features/suggestions.py).

    öğrenilen örüntü → "kurayım mı?" sorusu → kullanıcının kararı

EN KRİTİK TESTLER:
  • `test_belirsiz_secim_hicbir_sey_kurmaz` — çıplak "kabul et" birden fazla
    öneri varken tahmin etmemeli. Tahmin, kullanıcının istemediği görevi
    kurmaktır.
  • `test_numara_gosterilen_siradan_cozulur` — numara ÜRETİM sırasına
    uygulanırsa yanlış öneri sessizce kurulur (`file_send` sayfalama dersi).
  • `test_mesaj_gonderen_komut_onerilmez` — beyaz liste dışı hiçbir niyet
    öneriye dönüşmemeli.
  • `test_zaten_kurulu_gorev_onerilmez` / `test_cursor_yoksa_zamanlama_onerilmez`
    — doğrulanamayan öneri, ikinci bir kopya kurdurur.
  • `test_kisayol_orijinal_metni_kullanir` — sadeleştirilmiş ASCII metin
    ("ekran goruntusu al") hiçbir niyet regex'ine eşleşmez.

İZOLASYON: öğrenme veritabanı, öneri kararları ve kısayol dosyası testin
kendi geçici dizinindedir; kullanıcının gerçek `%APPDATA%\\ULTRON` verisine
dokunulmaz.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from features import chat_learning as cl
from features import custom_shortcuts as cs
from features import suggestions as sg


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class OneriTemeli(unittest.TestCase):
    """Her test taze arşiv + taze karar dosyası + boş görev tablosuyla başlar."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ultron_oneri_')
        self.yamalar = [
            mock.patch.object(cl, '_db_yolu',
                              return_value=os.path.join(self.tmp, 'ogrenme.db')),
            mock.patch.object(sg, '_dosya_yolu',
                              return_value=os.path.join(self.tmp, 'oneriler.json')),
            mock.patch.object(cs, '_dosya_yolu',
                              return_value=os.path.join(self.tmp, 'kisayol.json')),
        ]
        for y in self.yamalar:
            y.start()
        cl._SON_TUR.clear()
        cl._onbellegi_dusur()

        # Zamanlanmış görev tablosu — gerçek şemanın aynısı (database/schema.sql)
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE zamanli_gorevler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                saat TEXT NOT NULL,
                komut TEXT NOT NULL,
                son_calisma TEXT,
                aktif INTEGER DEFAULT 1,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def tearDown(self):
        for y in self.yamalar:
            y.stop()
        self.conn.close()
        cl._SON_TUR.clear()
        cl._onbellegi_dusur()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- yardımcılar --------------------------------------------------------
    def arsive_yaz(self, cumle, intent, sayi=6, saat=8, basarili=True, ruh=None):
        """Arşive doğrudan yazar — saat/gün kontrollü olsun diye `kaydet` değil."""
        with cl._acik() as conn:
            for i in range(sayi):
                conn.execute(
                    "INSERT INTO konusma (kanal, kullanici, ultron, sade, intent, "
                    "basarili, kaynak, tarih, saat, gun, ruh_hali) "
                    "VALUES ('desktop', ?, 'tamam', ?, ?, ?, 'canli', ?, ?, ?, ?)",
                    (cumle, cl.sadelestir(cumle), intent, 1 if basarili else 0,
                     f"2026-07-{(i % 28) + 1:02d} {saat:02d}:30:00", saat, i % 7, ruh))
            conn.commit()
        cl._onbellegi_dusur()

    def gorev_sayisi(self):
        self.cursor.execute("SELECT COUNT(*) FROM zamanli_gorevler")
        return self.cursor.fetchone()[0]


# =========================================================================
# ZAMANLAMA ÖNERİSİ
# =========================================================================
class ZamanlamaOnerisi(OneriTemeli):

    def test_zaman_aliskanligi_oneriye_donusur(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=6, saat=8)
        liste = sg.oneriler(db_cursor=self.cursor)
        zaman = [o for o in liste if o['tip'] == 'zamanlama']
        self.assertEqual(len(zaman), 1)
        self.assertEqual(zaman[0]['eylem']['saat'], '08:00')
        self.assertEqual(zaman[0]['eylem']['komut'], 'hava durumu')

    def test_yetersiz_gozlem_oneri_uretmez(self):
        """3 gözlem örüntüdür ama öneri değildir — her gün çalışacak bir görev
        kurmak, rapora satır yazmaktan daha fazla kanıt ister."""
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=4, saat=8)
        oruntu = cl.oruntuler(zorla=True)['zaman']
        self.assertTrue(oruntu, "önce örüntü çıkmalı ki test anlamlı olsun")
        self.assertEqual(sg.oneriler(db_cursor=self.cursor), [])

    def test_zaten_kurulu_gorev_onerilmez(self):
        self.cursor.execute("INSERT INTO zamanli_gorevler (saat, komut) "
                            "VALUES ('08:00', 'hava durumu')")
        self.conn.commit()
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=9, saat=8)
        self.assertEqual([o for o in sg.oneriler(db_cursor=self.cursor)
                          if o['tip'] == 'zamanlama'], [])

    def test_cursor_yoksa_zamanlama_onerilmez(self):
        """Kurulu görevlerle karşılaştıramıyorsak öneri üretmek, kullanıcıya
        ikinci bir kopya kurdurur."""
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=9, saat=8)
        self.assertEqual([o for o in sg.oneriler(db_cursor=None)
                          if o['tip'] == 'zamanlama'], [])

    def test_zamanlanamaz_niyet_onerilmez(self):
        """Kullanıcı uyanmadan müzik başlatmak istenmeyen bir yan etkidir."""
        self.arsive_yaz("müzik çal", "PLAY_MUSIC", sayi=12, saat=9)
        self.assertEqual([o for o in sg.oneriler(db_cursor=self.cursor)
                          if o['tip'] == 'zamanlama'], [])

    def test_kabul_gorevi_gercekten_kurar(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=6, saat=8)
        sg.oneri_metni(db_cursor=self.cursor)          # listeyi göster
        cevap = sg.kabul_et("1", db_cursor=self.cursor, db_conn=self.conn)

        self.cursor.execute("SELECT saat, komut FROM zamanli_gorevler")
        self.assertEqual(self.cursor.fetchall(), [('08:00', 'hava durumu')])
        self.assertIn('08:00', cevap)


# =========================================================================
# KISAYOL ÖNERİSİ
# =========================================================================
class KisayolOnerisi(OneriTemeli):

    def test_kisayol_orijinal_metni_kullanir(self):
        """`sade` sütunu ASCII'dir ('ekran goruntusu al'); niyet regex'leri
        Türkçe harfle yazılı. Geri oynatılacak metin orijinal olmalı."""
        self.arsive_yaz("ekran görüntüsü al", "SCREENSHOT", sayi=7, saat=14)
        oneri = next(o for o in sg.oneriler(db_cursor=self.cursor)
                     if o['tip'] == 'kisayol')
        self.assertEqual(oneri['eylem']['komut'], "ekran görüntüsü al")
        self.assertIn('ö', oneri['eylem']['komut'])

    def test_mesaj_gonderen_komut_onerilmez(self):
        """Beyaz liste `chat_learning.OGRENILEBILIR_INTENTLER` ile ortak:
        yanlış tetiklenen bir kısayol yanlış kişiye mesaj göndermektir."""
        self.arsive_yaz("anneme mesaj gönder", "WHATSAPP_MESSAGE", sayi=15, saat=10)
        self.arsive_yaz("staj raporunu yolla", "FILE_TRANSFER", sayi=15, saat=11)
        self.arsive_yaz("enter bas", "KEYBOARD_INPUT", sayi=15, saat=12)
        self.assertEqual(sg.oneriler(db_cursor=self.cursor), [])

    def test_var_olan_kisayol_tekrar_onerilmez(self):
        cs.ekle("⚡ Ekran", "ekran görüntüsü al")
        self.arsive_yaz("ekran görüntüsü al", "SCREENSHOT", sayi=7, saat=14)
        self.assertEqual([o for o in sg.oneriler(db_cursor=self.cursor)
                          if o['tip'] == 'kisayol'], [])

    def test_kabul_kisayolu_gercekten_ekler(self):
        self.arsive_yaz("ekran görüntüsü al", "SCREENSHOT", sayi=7, saat=14)
        sg.oneri_metni(db_cursor=self.cursor)
        sg.kabul_et("1", db_cursor=self.cursor, db_conn=self.conn)
        self.assertIn("ekran görüntüsü al", cs.yukle().values())

    def test_kanal_oneki_komuta_sizmaz(self):
        """
        CANLI HATA (3 Ağu): Telegram'dan gelen mesajlar arşive
        "[Telegram] Ekran görüntüsü" olarak yazılıyor. Öneri bu ham metni
        kullanınca "[Telegram] ..." adlı, HİÇBİR niyete eşleşmeyen bir kısayol
        kurulacaktı. Kanal etiketi komutun parçası değildir.
        """
        self.arsive_yaz("[Telegram] Ekran görüntüsü", "SCREENSHOT", sayi=8, saat=15)
        oneri = next(o for o in sg.oneriler(db_cursor=self.cursor)
                     if o['tip'] == 'kisayol')
        self.assertNotIn('[Telegram]', oneri['eylem']['komut'])
        self.assertNotIn('[Telegram]', oneri['eylem']['ad'])
        self.assertNotIn('[Telegram]', oneri['baslik'])
        self.assertEqual(oneri['eylem']['komut'], "Ekran görüntüsü")

    def test_ayni_is_icin_tek_kisayol_onerilir(self):
        """
        CANLI HATA (3 Ağu): "Ekran görüntüsü" (49 kez) ve "ekran görüntüsü al"
        (17 kez) iki ayrı öneri olarak listelendi — aynı şeyin iki söyleyişi.
        En sık kullanılan söyleyiş kazanır.
        """
        self.arsive_yaz("Ekran görüntüsü", "SCREENSHOT", sayi=12, saat=15)
        self.arsive_yaz("ekran görüntüsü al", "SCREENSHOT", sayi=6, saat=15)
        kisayollar = [o for o in sg.oneriler(db_cursor=self.cursor)
                      if o['tip'] == 'kisayol']
        self.assertEqual(len(kisayollar), 1)
        self.assertEqual(kisayollar[0]['eylem']['komut'], "Ekran görüntüsü")

    def test_ayni_komut_icin_iki_oneri_cikmaz(self):
        """Zamanlama daha güçlü çözüm — aynı niyet için kısayol da sormayız."""
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=8, saat=8)
        tipler = [o['tip'] for o in sg.oneriler(db_cursor=self.cursor)]
        self.assertEqual(tipler, ['zamanlama'])


# =========================================================================
# KARAR — kabul / red / seçim çözümü
# =========================================================================
class KararAkisi(OneriTemeli):

    def iki_oneri_kur(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=9, saat=8)        # zamanlama
        self.arsive_yaz("ekran görüntüsü al", "SCREENSHOT", sayi=6, saat=14)  # kısayol

    def test_reddedilen_oneri_geri_gelmez(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=6, saat=8)
        sg.oneri_metni(db_cursor=self.cursor)
        sg.reddet("1", db_cursor=self.cursor)
        self.assertEqual(sg.oneriler(db_cursor=self.cursor), [])

    def test_reddedilen_oneri_hicbir_sey_kurmaz(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=6, saat=8)
        sg.oneri_metni(db_cursor=self.cursor)
        sg.reddet("1", db_cursor=self.cursor)
        self.assertEqual(self.gorev_sayisi(), 0)

    def test_kabul_edilen_oneri_tekrar_sorulmaz(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=6, saat=8)
        sg.oneri_metni(db_cursor=self.cursor)
        sg.kabul_et("1", db_cursor=self.cursor, db_conn=self.conn)
        self.assertEqual(sg.oneriler(db_cursor=self.cursor), [])

    def test_belirsiz_secim_hicbir_sey_kurmaz(self):
        """İki öneri varken çıplak 'kabul et' hangisi olduğunu bilmiyor demektir."""
        self.iki_oneri_kur()
        self.assertEqual(len(sg.oneriler(db_cursor=self.cursor)), 2)
        cevap = sg.kabul_et("", db_cursor=self.cursor, db_conn=self.conn)
        self.assertIn("Hangi", cevap)
        self.assertEqual(self.gorev_sayisi(), 0)
        self.assertNotIn("ekran görüntüsü al", cs.yukle().values())

    def test_tek_oneri_varken_numara_gerekmez(self):
        self.arsive_yaz("hava nasıl", "WEATHER", sayi=6, saat=8)
        sg.kabul_et("", db_cursor=self.cursor, db_conn=self.conn)
        self.assertEqual(self.gorev_sayisi(), 1)

    def test_gecersiz_numara_hicbir_sey_kurmaz(self):
        self.iki_oneri_kur()
        sg.oneri_metni(db_cursor=self.cursor)
        cevap = sg.kabul_et("5", db_cursor=self.cursor, db_conn=self.conn)
        self.assertIn("5", cevap)
        self.assertEqual(self.gorev_sayisi(), 0)

    def test_numara_gosterilen_siradan_cozulur(self):
        """
        Numara, ÜRETİM sırasına değil GÖSTERİLEN sıraya uygulanmalı.

        Liste gösterildikten sonra arşiv değişip sıralama tersine dönerse,
        "2. öneriyi uygula" hâlâ kullanıcının ekranda 2. sırada GÖRDÜĞÜ
        öneriyi kurmalı — aksi hâlde yanlış öneri sessizce kurulur.
        """
        self.iki_oneri_kur()
        gosterilen = sg.oneriler(db_cursor=self.cursor)
        sg.oneri_metni(db_cursor=self.cursor)
        ikinci_id = gosterilen[1]['id']

        # Sıralamayı tersine çevir: 2. sıradaki öneri artık en yüksek sayıda
        self.arsive_yaz("ekran görüntüsü al", "SCREENSHOT", sayi=20, saat=14)
        yeni_sira = sg.oneriler(db_cursor=self.cursor)
        self.assertNotEqual(yeni_sira[0]['id'], gosterilen[0]['id'],
                            "test ancak sıra gerçekten değiştiyse anlamlı")

        sg.kabul_et("2", db_cursor=self.cursor, db_conn=self.conn)
        kararlar = sg._durum_yukle()['karar']
        self.assertIn(ikinci_id, kararlar)
        self.assertEqual(kararlar[ikinci_id]['durum'], 'kabul')

    def test_oneri_yokken_kabul_bir_sey_yapmaz(self):
        cevap = sg.kabul_et("1", db_cursor=self.cursor, db_conn=self.conn)
        self.assertIn("bekleyen", cevap.lower())
        self.assertEqual(self.gorev_sayisi(), 0)


# =========================================================================
# KOMUT ALGILAMA — sohbet cümlesi komuta dönüşmemeli
# =========================================================================
class OneriKomutAlgilama(unittest.TestCase):

    def test_oneri_sorgusu_algilanir(self):
        for cumle in ("önerilerin neler", "önerilerini göster", "öneri listesi",
                      "bekleyen öneri var mı"):
            with self.subTest(cumle=cumle):
                komut = cl.ogrenme_komutu_algila(cumle)
                self.assertIsNotNone(komut, cumle)
                self.assertEqual(komut['islem'], 'oneri')

    def test_bir_sey_hakkinda_oneri_istemek_komut_degil(self):
        """'film önerilerin var mı' sohbettir. Serbest cümleyi komuta çevirmek,
        kullanıcının konuşamaz hâle gelmesi demektir."""
        for cumle in ("film önerilerin var mı", "akşam yemeği için öneri var mı",
                      "bana kitap önerir misin", "dizi önerilerin neler"):
            with self.subTest(cumle=cumle):
                self.assertIsNone(cl.ogrenme_komutu_algila(cumle), cumle)

    def test_kabul_komutu_algilanir(self):
        komut = cl.ogrenme_komutu_algila("1. öneriyi uygula")
        self.assertEqual(komut['islem'], 'oneri_kabul')
        self.assertEqual(komut['hedef'], '1')

        self.assertEqual(cl.ogrenme_komutu_algila("öneriyi kabul et")['islem'],
                         'oneri_kabul')

    def test_red_komutu_algilanir(self):
        komut = cl.ogrenme_komutu_algila("2. öneriyi reddet")
        self.assertEqual(komut['islem'], 'oneri_red')
        self.assertEqual(komut['hedef'], '2')

        self.assertEqual(cl.ogrenme_komutu_algila("öneriyi boşver")['islem'],
                         'oneri_red')

    def test_ogrenme_komutlari_bozulmadi(self):
        """Öneri kalıpları eklendi diye eski komutlar kaybolmamalı."""
        self.assertEqual(cl.ogrenme_komutu_algila("ne öğrendin")['islem'], 'rapor')
        self.assertEqual(cl.ogrenme_komutu_algila("şunu unut: hava")['islem'], 'unut')


if __name__ == '__main__':
    unittest.main()
