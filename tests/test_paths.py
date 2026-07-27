"""
core/paths.py testleri — TEK veri dizini ve tek seferlik göç.

Bu modül gerçek %APPDATA%\\ULTRON dizinine ASLA dokunmaz: her test
ULTRON_DATA_DIR ile geçici bir dizine yönlendirilir ve modül önbelleği
(_dizin_cache) her testte sıfırlanır.
"""

import os
import shutil
import tempfile
import unittest

from core import paths


class VeriDiziniTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ultron_paths_')
        self._eski_env = os.environ.get('ULTRON_DATA_DIR')
        paths._dizin_cache = None

    def tearDown(self):
        paths._dizin_cache = None
        if self._eski_env is None:
            os.environ.pop('ULTRON_DATA_DIR', None)
        else:
            os.environ['ULTRON_DATA_DIR'] = self._eski_env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_env_degiskeni_dizini_ezer(self):
        os.environ['ULTRON_DATA_DIR'] = self.tmp
        self.assertEqual(paths.veri_dizini(), self.tmp)

    def test_dizin_yoksa_olusturulur(self):
        hedef = os.path.join(self.tmp, 'olmayan', 'derin')
        os.environ['ULTRON_DATA_DIR'] = hedef
        paths.veri_dizini()
        self.assertTrue(os.path.isdir(hedef))

    def test_veri_yolu_dizin_altina_baglar(self):
        os.environ['ULTRON_DATA_DIR'] = self.tmp
        self.assertEqual(
            paths.veri_yolu('bilgiler.db'),
            os.path.join(self.tmp, 'bilgiler.db'),
        )

    def test_env_verilince_goc_calismaz(self):
        """Test/izolasyon dizinine gerçek veri sızmamalı."""
        os.environ['ULTRON_DATA_DIR'] = self.tmp
        paths.veri_dizini()
        self.assertEqual(os.listdir(self.tmp), [])


class GocTest(unittest.TestCase):
    """_goc_et: eski konumdan bir kez kopyalar, var olanı EZMEZ."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ultron_goc_')
        self.eski = os.path.join(self.tmp, 'eski')
        self.yeni = os.path.join(self.tmp, 'yeni')
        os.makedirs(self.eski)
        os.makedirs(self.yeni)
        self._gercek_eski_konumlar = paths._eski_konumlar
        paths._eski_konumlar = lambda: [self.eski]

    def tearDown(self):
        paths._eski_konumlar = self._gercek_eski_konumlar
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _yaz(self, dizin, ad, icerik):
        with open(os.path.join(dizin, ad), 'w', encoding='utf-8') as f:
            f.write(icerik)

    def _oku(self, dizin, ad):
        with open(os.path.join(dizin, ad), 'r', encoding='utf-8') as f:
            return f.read()

    def test_eski_dosya_yeni_dizine_kopyalanir(self):
        self._yaz(self.eski, 'user_data.json', '{"sehir": "Istanbul"}')
        paths._goc_et(self.yeni)
        self.assertEqual(self._oku(self.yeni, 'user_data.json'), '{"sehir": "Istanbul"}')

    def test_mevcut_dosya_ezilmez(self):
        """İkinci açılışta göç, kullanıcının yeni verisini geri almamalı."""
        self._yaz(self.eski, 'config.json', 'ESKI')
        self._yaz(self.yeni, 'config.json', 'YENI')
        paths._goc_et(self.yeni)
        self.assertEqual(self._oku(self.yeni, 'config.json'), 'YENI')

    def test_eski_dosya_silinmez(self):
        """Geri dönüş mümkün kalsın diye kaynak yerinde durmalı."""
        self._yaz(self.eski, 'bilgiler.db', 'veri')
        paths._goc_et(self.yeni)
        self.assertTrue(os.path.exists(os.path.join(self.eski, 'bilgiler.db')))

    def test_bilinmeyen_dosya_tasinmaz(self):
        """Sadece VERI_DOSYALARI listesindekiler taşınır."""
        self._yaz(self.eski, 'rastgele.txt', 'x')
        paths._goc_et(self.yeni)
        self.assertFalse(os.path.exists(os.path.join(self.yeni, 'rastgele.txt')))

    def test_tum_veri_dosyalari_tasinir(self):
        for ad in paths.VERI_DOSYALARI:
            self._yaz(self.eski, ad, ad)
        paths._goc_et(self.yeni)
        for ad in paths.VERI_DOSYALARI:
            self.assertTrue(
                os.path.exists(os.path.join(self.yeni, ad)),
                f"{ad} göç etmedi — VERI_DOSYALARI listesiyle uyumsuzluk",
            )


if __name__ == '__main__':
    unittest.main()
