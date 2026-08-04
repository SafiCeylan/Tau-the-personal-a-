# -*- coding: utf-8 -*-
"""
DOĞAL DİL YÖNLENDİRME TESTLERİ — "normal konuşunca beni anlasın"

Bu paket, kullanıcının GERÇEKTEN yazdığı gibi cümleleri niyet katmanından
geçirir. Buradaki her satır bir zamanlar YANLIŞ kapıya düşmüş gerçek bir
cümledir; ölçülerek bulundular (denetim: 88 cümle, %75 → %94).

EN KRİTİK OLANLAR — hepsi "sessizce yanlış iş yapma" sınıfı:

  • `test_dosya_kapisi_alakasiz_cumleyi_calmaz` — dosya kapısı "at/ara/bul"
    fiillerini ALT DİZİ olarak arıyordu: "başlat"ta 'at', "araba"da 'ara',
    "bulut"ta 'bul'. Üstelik tür sözlüğü "ses"i "seslen" içinde yakalıyordu.
    Sonuç: "bana 5 dakika sonra seslen" → "telegram'a ses dosyası gönder".
    Kullanıcı bir şey söylüyor, Ultron ona rastgele dosya yolluyordu.

  • `test_gonderim_fiilleri_olu_degil` — sabitler Türkçe harfle yazılmıştı
    ('gönder') ama karşılaştırma sadeleştirilmiş metinde ('gonder') yapılıyor.
    Yani "gönder" ve "paylaş" fiilleri HİÇ eşleşmiyordu.

  • `test_whatsapp_at_fiilini_taniyor` — "anneme whatsapp at" en doğal yazım
    ve kapıdan geçemiyordu; WhatsApp mesaj yerine UYGULAMA olarak açılıyordu.

  • `test_ekranda_tikla_klavyeye_kacmaz` — doğal kısayollar eklenince
    ("kaydet" → Ctrl+S) "ekranda Kaydet'e tıkla" klavye kapısına düşüyordu.

İZOLASYON: `hafif=True` — dosya indeksine sorulmaz, LLM'e danışılmaz, sadece
regex sınıflandırma sınanır. Zırh kurulur; hiçbir OS çağrısı yapılmaz.
"""

import unittest

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

from core.context import UltronContext
from core.layers.pipeline_layers import IntentAnalyzerLayer


def setUpModule():
    guvenlik_zirhi_kur()


def tearDownModule():
    guvenlik_zirhi_kaldir()


class YonlendirmeTestTemeli(unittest.TestCase):
    katman = None

    @classmethod
    def setUpClass(cls):
        cls.katman = IntentAnalyzerLayer({})

    def niyet(self, cumle):
        ctx = UltronContext(raw_input=cumle)
        ctx.normalized_input = cumle
        return self.katman.process(ctx, hafif=True).intent

    def dogrula(self, cumleler_ve_niyetler):
        for cumle, beklenen in cumleler_ve_niyetler:
            with self.subTest(cumle=cumle):
                self.assertEqual(self.niyet(cumle), beklenen)


class KlavyeTest(YonlendirmeTestTemeli):
    """Kimse 'ctrl+c bas' demez, 'kopyala' der."""

    def test_dogal_kisayollar(self):
        self.dogrula([
            ("kopyala", "KEYBOARD_INPUT"),
            ("yapıştır", "KEYBOARD_INPUT"),
            ("geri al", "KEYBOARD_INPUT"),
            ("hepsini seç", "KEYBOARD_INPUT"),
            ("sekmeyi kapat", "KEYBOARD_INPUT"),
            ("yeni sekme", "KEYBOARD_INPUT"),
            ("görev yöneticisi", "KEYBOARD_INPUT"),
            ("masaüstüne dön", "KEYBOARD_INPUT"),
            ("sayfa sonuna git", "KEYBOARD_INPUT"),
            ("tam ekran", "KEYBOARD_INPUT"),
        ])

    def test_arti_isaretsiz_kombinasyon(self):
        self.dogrula([
            ("ctrl c yap", "KEYBOARD_INPUT"),
            ("ctrl v yap", "KEYBOARD_INPUT"),
            ("alt tab yap", "KEYBOARD_INPUT"),
        ])

    def test_ayri_yazilmis_ek(self):
        # "f5'e bas" çalışıyordu ama "f5 e bas" çalışmıyordu
        self.dogrula([("f5 e bas", "KEYBOARD_INPUT"), ("f5'e bas", "KEYBOARD_INPUT")])

    def test_geri_al_medyaya_gitmez(self):
        """Türkçede 'geri al' UNDO demektir; medya listesinde durduğu sürece
        komut klavyeye hiç ulaşmıyordu."""
        self.assertEqual(self.niyet("geri al"), "KEYBOARD_INPUT")
        # Medyanın kendi ifadeleri korunmalı
        self.dogrula([
            ("önceki şarkı", "MEDIA_CONTROL"),
            ("başa sar", "MEDIA_CONTROL"),
        ])

    def test_klavye_komsu_cumleleri_yutmaz(self):
        self.dogrula([
            ("sesi kes", "SET_VOLUME"),          # 'kes' Ctrl+X değil
            ("chrome kapat", "SYSTEM_CONTROL"),
            ("spotify aç", "SYSTEM_CONTROL"),
            ("alt tarafta ne var", "GENERAL_CONVERSATION"),
        ])

    def test_ekranda_tikla_klavyeye_kacmaz(self):
        self.dogrula([
            ("ekranda Kaydet'e tıkla", "SCREEN_CLICK"),
            ("ekranda Tamam butonuna bas", "SCREEN_CLICK"),
            ("enter bas", "KEYBOARD_INPUT"),     # tuş adı tıklama DEĞİL
            ("ctrl+s bas", "KEYBOARD_INPUT"),
        ])


class MesajTest(YonlendirmeTestTemeli):
    """WhatsApp / e-posta — kullanıcının en çok kullandığı iki komut."""

    def test_whatsapp_at_fiilini_taniyor(self):
        self.dogrula([
            ("anneme whatsapp at", "WHATSAPP_MESSAGE"),
            ("safi'ye whatsapp at gelemiyorum de", "WHATSAPP_MESSAGE"),
            ("whatsapp'tan anneme selam yolla", "WHATSAPP_MESSAGE"),
            ("wp'den ahmete yaz", "WHATSAPP_MESSAGE"),
        ])

    def test_eposta_dogal_yazimlar(self):
        self.dogrula([
            ("patronuma mail at", "EMAIL_MESSAGE"),
            ("hocama mail gönder konu: staj raporu", "EMAIL_MESSAGE"),
            ("ahmet'e e-posta yolla toplantı ertelendi", "EMAIL_MESSAGE"),
            ("mail rehberini göster", "EMAIL_MESSAGE"),
        ])

    def test_whatsapp_ac_mesaj_degildir(self):
        self.assertEqual(self.niyet("whatsapp aç"), "SYSTEM_CONTROL")

    def test_rehberde_olmayan_alici_uydurulmaz(self):
        """Kanal adı yoksa karar REHBERE sorulur. Alıcı iki rehberde de yoksa
        niyet ALINMAZ — yanlış kişiye mesaj atmaktansa anlamamak yeğdir."""
        self.assertEqual(self.niyet("zzzyxqq'ye mesaj at"), "GENERAL_CONVERSATION")


class DosyaKapisiTest(YonlendirmeTestTemeli):
    """En zararlı hata: alakasız cümleye el koyup rastgele dosya göndermek."""

    def test_dosya_kapisi_alakasiz_cumleyi_calmaz(self):
        from features.file_send import dosya_niyeti_coz
        for cumle in ("10 dakikalık zamanlayıcı başlat",   # 'başlat' içinde 'at'
                      "bana 5 dakika sonra seslen",        # 'seslen' içinde 'ses'
                      "arabayı yıkattım",                  # 'araba' içinde 'ara'
                      "bulutlu bir gün",                   # 'bulut' içinde 'bul'
                      "iletişim kurmak istiyorum",         # 'iletişim' içinde 'ilet'
                      "saat kaç",                          # 'saat' içinde 'at'
                      "bunu bana anlat"):                  # 'anlat' içinde 'at'
            with self.subTest(cumle=cumle):
                self.assertIsNone(dosya_niyeti_coz(cumle, 'telegram'),
                                  "dosya kapısı alakasız cümleye el koydu")

    def test_gonderim_fiilleri_olu_degil(self):
        """Sabitler ASCII olmalı — sadeleştirilmiş metinle karşılaştırılıyor."""
        from features.file_send import _GONDERIM_RE, _ARAMA_RE
        for fiil in ('gonder', 'gonderir', 'yolla', 'paylas', 'at', 'atar'):
            with self.subTest(fiil=fiil):
                self.assertTrue(_GONDERIM_RE.search(f'dosyayi {fiil}'))
        for fiil in ('bul', 'ara', 'goster', 'listele', 'nerede'):
            with self.subTest(fiil=fiil):
                self.assertTrue(_ARAMA_RE.search(f'dosyayi {fiil}'))

    def test_tur_sozlugu_kelime_icinde_eslesmez(self):
        from features.file_send import _tur_bul
        self.assertIsNone(_tur_bul('bana 5 dakika sonra seslen'))
        self.assertEqual(_tur_bul('bana bir ses dosyasi gonder'), 'ses')


class MesajAyristirmaTest(unittest.TestCase):
    """Niyet doğru kapıya gitti — peki KİME, NE yazılacak doğru çıkarıldı mı?

    En sinsi hata sınıfı: alıcı çıkarımı KESME İŞARETİ şart koşuyordu.
    "annem'e" yazan yok, herkes "anneme" yazıyor. Bu yüzden KOMUTLAR.md'de
    BELGELENMİŞ biçim ("anneme whatsapp gönder: yoldayım") bile
    ayrıştırılamıyordu — komut sessizce LLM'e düşüp uydurma cevap alıyordu.
    """

    def test_whatsapp_kesme_isaretsiz_alici(self):
        from features.actions.whatsapp_control import whatsapp_gonderim_ayristir as ayr
        for cumle, alici in [
            ("anneme whatsapp gönder: yoldayım", "annem"),
            ("annem'e whatsapp gönder: yoldayım", "annem"),
        ]:
            with self.subTest(cumle=cumle):
                self.assertEqual((ayr(cumle) or (None,))[0], alici)

    def test_whatsapp_dogal_yazimlar(self):
        from features.actions.whatsapp_control import whatsapp_gonderim_ayristir as ayr
        beklenen = {
            "anneme whatsapp at yarın gelemeyeceğim": ("annem", "yarın gelemeyeceğim"),
            "seyit'e whatsapp at toplantı ertelendi": ("seyit", "toplantı ertelendi"),
            "whatsapp ile anneme geç kalacağım de": ("annem", "geç kalacağım"),
            "whatsapp'tan anneme selam yolla": ("annem", "selam"),
        }
        for cumle, sonuc in beklenen.items():
            with self.subTest(cumle=cumle):
                self.assertEqual(ayr(cumle), sonuc)

    def test_whatsapp_kanalsiz_ayristirma(self):
        """Kanal adı yoksa niyet katmanı rehberden karar verir; araç da
        cümleyi ayrıştırabilmeli, yoksa niyet gelir ama iş yapılmaz."""
        from features.actions.whatsapp_control import kanalsiz_mesaj_ayristir as ayr
        self.assertEqual(ayr("anneme mesaj at: yoldayım"), ("annem", "yoldayım"))
        self.assertEqual(ayr("anneme yaz geç kalacağım"), ("annem", "geç kalacağım"))

    def test_eposta_iki_noktasiz_calisir(self):
        """E-posta ':' olmadan HİÇ ayrıştırmıyordu — yani pratikte yalnızca
        belgelenmiş biçimle çalışıyordu, doğal cümleyle hiç."""
        from features.email_control import email_gonderim_ayristir as ayr
        for cumle, alici, icerik in [
            ("anneme mail at yarın gelemeyeceğim", "annem", "yarın gelemeyeceğim"),
            ("patronuma mail gönder toplantı ertelendi", "patronum", "toplantı ertelendi"),
            ("kendime eposta at bugün yapılacaklar", "kendim", "bugün yapılacaklar"),
        ]:
            with self.subTest(cumle=cumle):
                sonuc = ayr(cumle)
                self.assertIsNotNone(sonuc, "ayrıştırılamadı")
                self.assertEqual(sonuc[0], alici)
                self.assertEqual(sonuc[2], icerik)

    def test_eposta_konu_alici_sanilmaz(self):
        """'hocama mail at konu: staj raporu' cümlesinde alıcı 'konu' olarak
        okunuyordu — yani mail YANLIŞ KİŞİYE gidiyordu."""
        from features.email_control import email_gonderim_ayristir as ayr
        alici, konu, icerik = ayr("hocama mail at konu: staj raporu")
        self.assertEqual(alici, "hocam")
        self.assertEqual(konu, "staj raporu")

    def test_eposta_konu_icerik_ayraci(self):
        from features.email_control import email_gonderim_ayristir as ayr
        alici, konu, icerik = ayr("kendime mail gönder: Hatırlatma | fatura ödenecek")
        self.assertEqual((alici, konu, icerik), ("kendim", "Hatırlatma", "fatura ödenecek"))

    def test_eposta_adresi_dogrudan_yazilabilir(self):
        from features.email_control import email_gonderim_ayristir as ayr
        self.assertEqual(ayr("ahmet@site.com'a mail yolla merhaba")[0], "ahmet@site.com")


class ZamanAyristirmaTest(unittest.TestCase):
    """Hatırlatma saatleri — yanlış saat = hatırlatma işe yaramaz."""

    def test_gunun_bolumu_saat_verir(self):
        """'yarın sabah hatırlat' saati çözemiyor ve hatırlatmayı İÇİNDE
        BULUNULAN saate kuruyordu: gece 23:00'te 'yarın sabah' dersen
        ertesi gün 23:00'te çalıyordu."""
        from features.reminders import hatirlatma_algila
        for cumle, saat in [("yarın sabah ilaç içmeyi hatırlat", "08:00"),
                            ("yarın öğlen toplantıyı hatırlat", "12:00"),
                            ("yarın akşam annemi aramayı hatırlat", "19:00")]:
            with self.subTest(cumle=cumle):
                self.assertIn(saat, hatirlatma_algila(cumle)['tarih'])

    def test_acik_saat_gunun_bolumunu_yener(self):
        from features.reminders import hatirlatma_algila
        # "akşam 8" → 20:00 (varsayılan 19:00 değil)
        self.assertIn("20:00", hatirlatma_algila("akşam 8'de annemi aramayı hatırlat")['tarih'])

    def test_obur_gun_taniniyor(self):
        from datetime import datetime, timedelta
        from features.reminders import hatirlatma_algila
        sonuc = hatirlatma_algila("öbür gün doktora gitmeyi hatırlat")
        self.assertIsNotNone(sonuc, "'öbür gün' hiç tanınmıyor")
        beklenen = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        self.assertTrue(sonuc['tarih'].startswith(beklenen))


class AltDiziTuzagiTest(unittest.TestCase):
    """Kısa fiillerin kelime İÇİNDE eşleşmesi — kod tabanı taramasıyla bulundu.

        'at'  → başlat · saat · anlat · hayat
        'yaz' → ne yazık · yazılım · yaz tatili
        'kur' → dolar kuru · kurabiye · kurulum
    """

    def test_hatirlatma_metni_parcalanmaz(self):
        """Temizlik düz replace() ile yapılıyordu ve kelime ORTASINDAN kesiyordu:
        "dolar kuru nedir" → "dolar u nedir" · "kurabiye" → "abiye".
        Kullanıcının hatırlatması bozuk metinle kaydediliyordu."""
        from features.reminders import hatirlatma_algila
        for cumle, beklenen_parca in [
            ("bugün dolar kuru nedir", "dolar kuru"),
            ("yarın kurabiye yapacağım", "kurabiye"),
            ("yarın 10'da kurs kaydını hatırlat", "kurs"),
        ]:
            with self.subTest(cumle=cumle):
                sonuc = hatirlatma_algila(cumle)
                if sonuc:
                    self.assertIn(beklenen_parca, sonuc['metin'],
                                  f"metin parçalandı: {sonuc['metin']!r}")

    def test_mesaj_kapilari_alakasiz_cumleye_el_koymaz(self):
        """Kapılar 'islendi=True' dönerse kullanıcı sıradan bir cümleye
        'komutu çözemedim' rehberi alır ve LLM'e hiç ulaşamaz."""
        from features.actions.whatsapp_control import whatsapp_komutu_algila
        from features.email_control import email_komutu_algila

        for cumle in ("whatsapp saati geldi mi", "whatsapp ne yazık ki çalışmıyor",
                      "whatsapp anlat bana"):
            with self.subTest(cumle=cumle):
                self.assertFalse(whatsapp_komutu_algila(cumle)[0])

        for cumle in ("mail saati", "mail yazılımı bozuldu",
                      "mail hayatımı kolaylaştırdı"):
            with self.subTest(cumle=cumle):
                self.assertFalse(email_komutu_algila(cumle)[0])

    def test_gercek_komutlar_hala_calisiyor(self):
        """Kelime sınırı eklemek DOĞRU cümleleri bozmamalı."""
        from features.actions.whatsapp_control import whatsapp_gonderim_ayristir
        from features.email_control import email_gonderim_ayristir

        self.assertIsNotNone(whatsapp_gonderim_ayristir("anneme whatsapp at yoldayım"))
        self.assertIsNotNone(whatsapp_gonderim_ayristir(
            "whatsapp ile anneme geç kalacağım de"))
        self.assertIsNotNone(email_gonderim_ayristir("anneme mail at yoldayım"))


class KapiSirasiTest(YonlendirmeTestTemeli):
    """Komşu kapıların birbirinin cümlesini yutmaması."""

    def test_olculen_hatalar_geri_gelmesin(self):
        self.dogrula([
            ("10 dakikalık zamanlayıcı başlat", "TIMER"),      # 'zamanla' alt dizi
            ("sistem durumu nedir", "SYSTEM_CONTROL"),         # 'nedir' web araması değil
            ("sessize al", "SET_VOLUME"),
            ("yarın yağmur yağacak mı", "WEATHER"),            # 'hava' kelimesi yok
            ("ekran görüntüsü al", "SCREENSHOT"),
            ("ekranda ne yazıyor", "SCREEN_READ"),
            ("panoyu özetle", "CLIPBOARD"),
            ("ne öğrendin", "LEARNING_REPORT"),
        ])

    def test_sohbet_cumleleri_araca_gitmez(self):
        self.dogrula([
            ("naber", "GENERAL_CONVERSATION"),
            ("bugün çok yorgunum", "GENERAL_CONVERSATION"),
            ("teşekkürler", "GENERAL_CONVERSATION"),
        ])


if __name__ == '__main__':
    unittest.main()
