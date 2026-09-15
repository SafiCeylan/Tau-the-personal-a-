# -*- coding: utf-8 -*-
import os
import unittest
import tempfile
import shutil
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
import features.proactive_events as pe


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class TestProactiveEvents(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.orig_veri_dizini = pe.veri_dizini
        pe.veri_dizini = lambda: self.tmp_dir
        pe._durumu_sifirla()

        # ⚠️ `with sqlite3.connect(...)` bağlantıyı kapatmaz; Windows'ta açık
        #    tanıtıcı tempdir silinmesini ve dosya kaldırmayı engeller.
        conn = sqlite3.connect(os.path.join(self.tmp_dir, "bilgiler.db"))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS takvim_etkinlikleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    baslik TEXT NOT NULL,
                    baslangic TIMESTAMP NOT NULL,
                    tum_gun INTEGER DEFAULT 0,
                    yer TEXT,
                    aciklama TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        pe.veri_dizini = self.orig_veri_dizini
        pe._durumu_sifirla()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _etkinlik_ekle(self, baslik, dakika_sonra, yer=None, tum_gun=0):
        zaman = (datetime.now() + timedelta(minutes=dakika_sonra)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(os.path.join(self.tmp_dir, "bilgiler.db"))
        try:
            conn.execute(
                "INSERT INTO takvim_etkinlikleri (baslik, baslangic, yer, tum_gun) VALUES (?,?,?,?)",
                (baslik, zaman, yer, tum_gun))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Takvim
    # ------------------------------------------------------------------
    def test_yaklasan_etkinlik_tespiti(self):
        self._etkinlik_ekle("Proje Toplantısı", 10, "Ofis B3")

        # Mola yolunu devre dışı bırak: bu test yalnız takvimi ölçüyor.
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=None):
            bildirimler = pe.proaktif_olaylari_kontrol_et()
            self.assertEqual(len(bildirimler), 1)
            self.assertIn("Proje Toplantısı", bildirimler[0])
            self.assertIn("Ofis B3", bildirimler[0])

            # Aynı etkinlik İKİNCİ kez duyurulmamalı
            self.assertEqual(pe.proaktif_olaylari_kontrol_et(), [])

    def test_uzak_etkinlik_duyurulmaz(self):
        self._etkinlik_ekle("Yarınki Sunum", 120)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=None):
            self.assertEqual(pe.proaktif_olaylari_kontrol_et(), [])

    def test_tum_gun_etkinligi_duyurulmaz(self):
        """Tüm gün etkinliğinin başlangıcı 00:00'dır; '15 dk kaldı' anlamsız."""
        self._etkinlik_ekle("Doğum günü", 5, tum_gun=1)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=None):
            self.assertEqual(pe.proaktif_olaylari_kontrol_et(), [])

    def test_takvim_tablosu_yoksa_patlamaz(self):
        conn = sqlite3.connect(os.path.join(self.tmp_dir, "bilgiler.db"))
        try:
            conn.execute("DROP TABLE takvim_etkinlikleri")
            conn.commit()
        finally:
            conn.close()
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=None):
            self.assertEqual(pe.proaktif_olaylari_kontrol_et(), [])

    # ------------------------------------------------------------------
    # Mola — gerçek hareketsizliğe bakar, uygulamanın açık kalma süresine DEĞİL
    # ------------------------------------------------------------------
    def test_kesintisiz_calismada_mola_uyarisi(self):
        pe._SON_MOLA_ZAMANI = datetime.now() - timedelta(hours=3)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=5.0):   # aktif
            bildirimler = pe.proaktif_olaylari_kontrol_et()
        self.assertTrue(any("Mola Zamanı" in b for b in bildirimler), bildirimler)

    def test_kullanici_zaten_ara_verdiyse_uyarilmaz(self):
        """Asıl hata buydu: sayaç import anında başlıyordu, bilgisayarın başında
        olmayan kullanıcıya 2 saat sonra 'kesintisiz çalışıyorsun' deniyordu."""
        pe._SON_MOLA_ZAMANI = datetime.now() - timedelta(hours=3)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=20 * 60):  # 20 dk boşta
            bildirimler = pe.proaktif_olaylari_kontrol_et()
        self.assertEqual(bildirimler, [])
        # Mola verildiği için sayaç sıfırlanmış olmalı
        self.assertLess((datetime.now() - pe._SON_MOLA_ZAMANI).total_seconds(), 5)

    def test_bosta_suresi_olculemezse_uyari_yok(self):
        pe._SON_MOLA_ZAMANI = datetime.now() - timedelta(hours=3)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=None):
            self.assertEqual(pe.proaktif_olaylari_kontrol_et(), [])

    def test_mola_uyarisi_her_tikta_tekrarlamaz(self):
        pe._SON_MOLA_ZAMANI = datetime.now() - timedelta(hours=3)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=5.0):
            ilk = pe.proaktif_olaylari_kontrol_et()
            ikinci = pe.proaktif_olaylari_kontrol_et()
        self.assertEqual(len(ilk), 1)
        self.assertEqual(ikinci, [])

    def test_uyari_hafizasi_budanir(self):
        pe._UYARILAN_ETKINLIKLER[999] = datetime.now() - timedelta(hours=12)
        with patch.object(pe, 'bosta_gecen_sure_sn', return_value=None):
            pe.proaktif_olaylari_kontrol_et()
        self.assertNotIn(999, pe._UYARILAN_ETKINLIKLER)


if __name__ == "__main__":
    unittest.main()
