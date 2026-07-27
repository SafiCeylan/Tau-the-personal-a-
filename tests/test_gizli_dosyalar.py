# -*- coding: utf-8 -*-
"""
GİZLİ DOSYA FİLTRESİ — projenin en kritik güvenlik sınırı.

Tehdit modeli: `file_index.db` telefondan erişilebilir. Sır taşıyan dosyalar
(`.env`, `id_rsa`, `*.pem`, `config.json`…) indekse GİRERSE Telegram üzerinden
aranabilir ve **gönderilebilir** hale gelir. Yani bu filtre bozulursa şifreler
ve özel anahtarlar dışarı sızar.

Bugüne kadar bu sınırın tek koruması "kodun doğru yazılmış olması"ydı — hiçbir
test yoktu. Bu dosya iki savunma hattını da kilitler:

    1. İNDEKSLEME — gizli dosya indekse hiç girmez
    2. GÖNDERİM   — indekste bir şekilde bulunsa bile (eski/bayat indeks)
                    gönderilmeden önce ikinci kez kontrol edilir

YANLIŞ POZİTİF de bir hatadır: `rapor.pdf` gizli sayılırsa kullanıcı kendi
dosyasını bulamaz. İki yön de test edilir.

⚠️ Bu testler kullanıcının GERÇEK indeksine dokunmaz — `INDEX_DB` geçici
dizine yönlendirilir ve taranan kökler sahtelenir.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from features import file_index, file_send


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class GizliTanimaTest(unittest.TestCase):
    """`gizli_mi` — sınıflandırmanın kendisi."""

    def test_gizli_adlar_yakalanir(self):
        for ad in ('.env', 'config.json', 'user_data.json', 'credentials.json',
                   'token.json', 'secrets.json', 'id_rsa', 'id_ed25519',
                   '.git-credentials', 'wallet.dat', '.netrc'):
            self.assertTrue(file_index.gizli_mi(ad), ad)

    def test_gizli_uzantilar_yakalanir(self):
        for ad in ('sunucu.pem', 'sertifika.key', 'kasa.kdbx', 'anahtar.ppk',
                   'store.jks', 'imza.asc', 'vpn.ovpn', 'yedek.pfx'):
            self.assertTrue(file_index.gizli_mi(ad), ad)

    def test_gizli_kaliplar_yakalanir(self):
        for ad in ('my_secret_notes.txt', 'password_listesi.docx',
                   'parolalar.xlsx', 'private_key_backup.txt',
                   'aws_credentials.csv', 'api_key.txt'):
            self.assertTrue(file_index.gizli_mi(ad), ad)

    def test_buyuk_harf_kacamaz(self):
        """`.ENV` ya da `ID_RSA` filtreyi atlatmamalı."""
        for ad in ('.ENV', 'Config.JSON', 'ID_RSA', 'Sunucu.PEM',
                   'SECRET_notlar.txt', 'Password.txt'):
            self.assertTrue(file_index.gizli_mi(ad), ad)

    def test_normal_dosyalar_gizli_sayilmaz(self):
        """Yanlış pozitif de hatadır — kullanıcı kendi dosyasını bulamaz."""
        for ad in ('staj raporu.pdf', 'sunum.pptx', 'foto.jpg', 'notlar.txt',
                   'kod.py', 'tablo.xlsx', 'ULTRON.spec', 'rapor.docx'):
            self.assertFalse(file_index.gizli_mi(ad), ad)

    def test_bos_ad_cokmez(self):
        self.assertFalse(file_index.gizli_mi(''))


class IndekslemeTest(unittest.TestCase):
    """1. SAVUNMA HATTI — gizli dosya indekse hiç girmez."""

    def setUp(self):
        self.tarama = tempfile.mkdtemp(prefix='ultron_tarama_')
        self.db_dizini = tempfile.mkdtemp(prefix='ultron_idx_')
        self.db = os.path.join(self.db_dizini, 'test_index.db')

        # Gizli + normal dosyalar, alt klasör dahil
        self._yaz('.env', 'SECRET=123')
        self._yaz('id_rsa', 'PRIVATE KEY')
        self._yaz('sunucu.pem', 'CERT')
        self._yaz('passwords.txt', 'gizli')
        self._yaz('staj raporu.pdf', 'normal')
        self._yaz('sunum.pptx', 'normal')
        alt = os.path.join(self.tarama, 'alt')
        os.makedirs(alt)
        self._yaz(os.path.join('alt', 'config.json'), '{"token": "x"}')
        self._yaz(os.path.join('alt', 'notlar.txt'), 'normal')

    def tearDown(self):
        shutil.rmtree(self.tarama, ignore_errors=True)
        shutil.rmtree(self.db_dizini, ignore_errors=True)

    def _yaz(self, ad, icerik):
        with open(os.path.join(self.tarama, ad), 'w', encoding='utf-8') as f:
            f.write(icerik)

    def _indeksle(self):
        with mock.patch.object(file_index, 'INDEX_DB', self.db), \
             mock.patch.object(file_index, '_kokler',
                               return_value=[(self.tarama, 'Test')]):
            sayi, _sure, gizli = file_index.indeksi_yenile()
            conn = file_index._baglanti()
            try:
                adlar = [r[0] for r in conn.execute("SELECT ad FROM dosyalar")]
            finally:
                conn.close()
        return sayi, gizli, adlar

    def test_gizli_dosyalar_indekse_girmez(self):
        _sayi, _gizli, adlar = self._indeksle()
        for yasak in ('.env', 'id_rsa', 'sunucu.pem', 'passwords.txt', 'config.json'):
            self.assertNotIn(yasak, adlar, f"{yasak} İNDEKSE GİRDİ — telefondan sızabilir")

    def test_normal_dosyalar_indekse_girer(self):
        _sayi, _gizli, adlar = self._indeksle()
        for beklenen in ('staj raporu.pdf', 'sunum.pptx', 'notlar.txt'):
            self.assertIn(beklenen, adlar, beklenen)

    def test_alt_klasordeki_gizli_de_atlanir(self):
        """Tarama alt klasörlere iniyor — filtre orada da işlemeli."""
        _sayi, _gizli, adlar = self._indeksle()
        self.assertNotIn('config.json', adlar)

    def test_atlanan_sayisi_raporlanir(self):
        """
        5 sır dosyası koydum ama sayaç 4 diyor — ÇÜNKÜ `.env` sayaca hiç
        ulaşmıyor: tarama döngüsü nokta ile başlayan dosyaları `gizli_mi`
        çağrılmadan ÖNCE eliyor.

        Yani `.env` İKİ bağımsız mekanizmayla korunuyor (dotfile eleme +
        gizli ad listesi). Biri kaldırılsa diğeri tutar — savunma derinliği.
        """
        _sayi, gizli, _adlar = self._indeksle()
        self.assertEqual(gizli, 4)

    def test_dotfile_elemesi_kalksa_bile_gizli_liste_tutar(self):
        """Savunma derinliği: `.env` gizli ad listesinde de olmalı."""
        self.assertTrue(file_index.gizli_mi('.env'))
        self.assertIn('.env', file_index.GIZLI_ADLAR)

    def test_gizli_dosya_aramayla_bulunamaz(self):
        """İndekste yoksa arama da bulamaz — uçtan uca doğrulama."""
        self._indeksle()
        with mock.patch.object(file_index, 'INDEX_DB', self.db):
            for sorgu in ('env', 'id_rsa', 'pem', 'password', 'config'):
                self.assertEqual(file_index.ara(sorgu), [], sorgu)

    def test_normal_dosya_aramayla_bulunur(self):
        self._indeksle()
        with mock.patch.object(file_index, 'INDEX_DB', self.db):
            self.assertTrue(file_index.ara('staj'))


class GonderimSavunmasiTest(unittest.TestCase):
    """
    2. SAVUNMA HATTI — indekste bir şekilde bulunsa bile gönderilmez.

    Neden gerekli: indeks bayat olabilir. Filtreye yeni bir kalıp eklendiğinde
    eski kayıtlar yeniden tarama yapılana kadar indekste kalır.
    """

    def setUp(self):
        self.dizin = tempfile.mkdtemp(prefix='ultron_gonder_')

    def tearDown(self):
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _dosya(self, ad):
        yol = os.path.join(self.dizin, ad)
        with open(yol, 'w', encoding='utf-8') as f:
            f.write('x')
        return yol

    def test_gizli_dosya_gecerli_sayilmaz(self):
        for ad in ('.env', 'id_rsa', 'anahtar.pem', 'secret_notes.txt'):
            self.assertFalse(file_index.dosya_gecerli_mi(self._dosya(ad)), ad)

    def test_normal_dosya_gecerli(self):
        self.assertTrue(file_index.dosya_gecerli_mi(self._dosya('rapor.pdf')))

    def test_olmayan_dosya_gecerli_degil(self):
        self.assertFalse(file_index.dosya_gecerli_mi(
            os.path.join(self.dizin, 'yok.pdf')))

    def test_gonderim_gizli_dosyayi_reddeder(self):
        """EN KRİTİK: sır taşıyan dosya hiçbir kanaldan çıkmamalı."""
        yol = self._dosya('id_rsa')
        for hedef in ('telegram', 'email', 'whatsapp'):
            plan = {'hedef': hedef, 'alici': 'anne', 'islem': 'gonder',
                    'sorgu': None, 'secim': 1, 'tur': None, 'zayif': False}
            cevap = file_send._hedefe_gonder(yol, plan)
            self.assertIn('gönderilemez', cevap, hedef)

    def test_gonderim_reddinde_hicbir_kanal_cagrilmaz(self):
        """Reddedilen dosya için gönderim fonksiyonlarına HİÇ gidilmemeli."""
        yol = self._dosya('.env')
        plan = {'hedef': 'telegram', 'alici': None, 'islem': 'gonder',
                'sorgu': None, 'secim': 1, 'tur': None, 'zayif': False}
        with mock.patch.object(file_send, 'telegrama_gonder') as tg:
            file_send._hedefe_gonder(yol, plan)
        tg.assert_not_called()


class FiltreKapsamiTest(unittest.TestCase):
    """
    Filtre listesi zayıflatılmasın.

    `CLAUDE.md`: "Sır taşıyan dosyalar indekse HİÇ girmez — bu listeyi
    zayıflatma." Bu test listeden madde silinmesini fark ettirir.
    """

    ZORUNLU_ADLAR = {'.env', 'config.json', 'id_rsa', 'credentials.json',
                     'secrets.json', 'token.json', '.git-credentials'}
    ZORUNLU_UZANTILAR = {'.pem', '.key', '.kdbx', '.pfx', '.p12', '.ppk'}
    ZORUNLU_KALIPLAR = {'secret', 'password', 'parola', 'credential', 'api_key'}

    def test_zorunlu_adlar_listede(self):
        eksik = self.ZORUNLU_ADLAR - file_index.GIZLI_ADLAR
        self.assertEqual(eksik, set(), f"gizli ad listesinden düşmüş: {eksik}")

    def test_zorunlu_uzantilar_listede(self):
        eksik = self.ZORUNLU_UZANTILAR - file_index.GIZLI_UZANTILAR
        self.assertEqual(eksik, set(), f"gizli uzantı listesinden düşmüş: {eksik}")

    def test_zorunlu_kaliplar_listede(self):
        eksik = self.ZORUNLU_KALIPLAR - set(file_index.GIZLI_KALIPLAR)
        self.assertEqual(eksik, set(), f"gizli kalıp listesinden düşmüş: {eksik}")


if __name__ == '__main__':
    unittest.main()
