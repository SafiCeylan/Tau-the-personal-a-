# -*- coding: utf-8 -*-
"""
ULTRON — CONTEXT MANAGER (Faz 2)

Çözdüğü sorun (kullanıcının notundan):

    > Chrome'u aç.      → Açıldı.
    > ChatGPT'ye git.   → Gitti.
    > Dosyayı yükle.    → HANGİ dosya?

Planner bunu bilemez, çünkü plan tek bir cümleden üretilir. Bilen katman budur:
konuşma boyunca "en son hangi dosya", "en son hangi kişi", "en son hangi
uygulama" geçtiğini takip eder ve eksik referansı doldurur.

ÇALIŞMA BİÇİMİ — metin ikamesi:
    "onu anneme gönder"  →  "staj raporu.pdf anneme gönder"

Neden ikame: bu projedeki araçların tamamı ham cümle üzerinde regex çalıştırıyor.
Referansı `entities`e yazmak, o regex'lerin hepsini değiştirmeyi gerektirirdi.
İkame ile downstream hiç değişmeden çalışır.

⚠️ SESSİZ TAHMİN YAPILMAZ. Her ikame `notlar` listesine yazılır ve kullanıcıya
gösterilir ("'onu' → staj raporu.pdf"). Yanlış tahmin edip sessiz kalmak,
kullanıcının farkında olmadan yanlış dosyayı göndermesine yol açar.

⚠️ TTL: bayat bağlam, bağlam olmamasından KÖTÜDÜR. İki saat önce konuşulan
dosya "dosyayı gönder" komutuna karışmamalı. Süre dolduğunda referans çözülmez,
kullanıcıya sorulur.

⚠️ KANAL AYRIMI: telefondan konuşulan dosya, masaüstündeki "onu gönder"
komutuna karışmamalı (dosya arama sonuçlarındaki ayrımla aynı gerekçe).
"""

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Bağlamın ömrü. Dosya arama sonuçlarıyla aynı mertebede tutuldu.
BAGLAM_OMRU_SN = 15 * 60

MASAUSTU_KANALI = "desktop"


@dataclass
class KanalBaglami:
    """Tek bir kanalın (masaüstü / Telegram sohbeti) anlık durumu."""
    son_dosya: Optional[str] = None
    son_kisi: Optional[str] = None
    son_uygulama: Optional[str] = None
    son_konu: Optional[str] = None
    son_intent: Optional[str] = None
    guncelleme: float = field(default_factory=time.time)

    def bayat_mi(self, simdi: Optional[float] = None) -> bool:
        return (simdi or time.time()) - self.guncelleme > BAGLAM_OMRU_SN

    def sozluge(self) -> Dict[str, Optional[str]]:
        return {
            "son_dosya": self.son_dosya, "son_kisi": self.son_kisi,
            "son_uygulama": self.son_uygulama, "son_konu": self.son_konu,
            "son_intent": self.son_intent,
        }


# =========================================================================
# Referans kalıpları
# =========================================================================
# NESNE referansları → son dosya/konu ile değiştirilir ("onu gönder")
_NESNE_KALIPLARI = (
    r'\bonu\b', r'\bbunu\b', r'\bşunu\b', r'\bsunu\b',
    r'\bo dosyayı\b', r'\bbu dosyayı\b', r'\bşu dosyayı\b',
    r'\bo dosyayi\b', r'\bbu dosyayi\b',
    r'\baynısını\b', r'\baynisini\b',
)

# ALICI referansları → son kişi ile değiştirilir ("ona gönder")
_ALICI_KALIPLARI = (
    r'\bona\b', r'\bkendisine\b', r'\bo kişiye\b', r'\bo kisiye\b',
)

# Çıplak "dosyayı" — isim verilmemiş. "staj raporunu" gibi nitelenmiş
# ifadeler bu kalıba GİRMEZ, çünkü zaten kendi adını taşıyor.
_CIPLAK_DOSYA = r'(?<!\w)dosyay[ıi](?!\w)'


class BaglamYoneticisi:
    """Kanal başına konuşma durumu. Süreç ömrü boyunca bellekte yaşar."""

    def __init__(self, omur_sn: int = BAGLAM_OMRU_SN):
        self._baglamlar: Dict[str, KanalBaglami] = {}
        self.omur_sn = omur_sn

    # ---------------------------------------------------------------
    def getir(self, kanal=MASAUSTU_KANALI) -> Optional[KanalBaglami]:
        """Taze bağlamı döner; bayatsa temizler ve None döner."""
        baglam = self._baglamlar.get(str(kanal))
        if baglam is None:
            return None
        if time.time() - baglam.guncelleme > self.omur_sn:
            self._baglamlar.pop(str(kanal), None)
            return None
        return baglam

    def hatirla(self, kanal=MASAUSTU_KANALI, **alanlar) -> KanalBaglami:
        """
        Bağlamı günceller. SADECE None olmayan değerler yazılır — böylece
        yeni bir uygulama açmak, konuşulan dosyayı unutturmaz.
        """
        baglam = self._baglamlar.get(str(kanal)) or KanalBaglami()
        degisti = False
        for ad, deger in alanlar.items():
            if deger in (None, "") or not hasattr(baglam, ad):
                continue
            if getattr(baglam, ad) != deger:
                setattr(baglam, ad, deger)
            degisti = True
        if degisti:
            baglam.guncelleme = time.time()
        self._baglamlar[str(kanal)] = baglam
        return baglam

    def temizle(self, kanal=MASAUSTU_KANALI):
        self._baglamlar.pop(str(kanal), None)

    def hepsini_temizle(self):
        self._baglamlar.clear()

    # ---------------------------------------------------------------
    def coz(self, metin: str, kanal=MASAUSTU_KANALI) -> Tuple[str, List[str]]:
        """
        Cümledeki eksik referansları bağlamdan doldurur → (yeni_metin, notlar).

        Bağlam yoksa/bayatsa metin AYNEN döner: yanlış tahmin etmektense
        çözmemek yeğdir (kullanıcıya "hangi dosya?" diye sorulur).
        """
        if not metin:
            return metin, []

        baglam = self.getir(kanal)
        if baglam is None:
            return metin, []

        notlar: List[str] = []
        yeni = metin

        # 1) Alıcı referansı ("ona gönder") — kişiden ÖNCE bakılır, çünkü
        #    "ona" kalıbı nesne kalıplarına da benzeyebilir.
        if baglam.son_kisi:
            yeni, not_ = self._degistir(yeni, _ALICI_KALIPLARI, baglam.son_kisi)
            notlar += not_

        # 2) Nesne referansı ("onu gönder") — son dosya, yoksa son konu
        #
        # Dosyaya ikame ederken "dosyasını" eki EKLENİR. Sebep: niyet katmanı
        # çıplak dosya adını tanımıyor — "ULTRON.spec aç" komutu SYSTEM_CONTROL'a
        # düşüp "ULTRON.spec adlı uygulamayı aç" sanılıyordu (canlı testte
        # görüldü). "ULTRON.spec dosyasını aç" ise dosya aracına gidiyor.
        if baglam.son_dosya:
            yeni, not_ = self._degistir(
                yeni, _NESNE_KALIPLARI, f"{baglam.son_dosya} dosyasını",
                not_degeri=baglam.son_dosya,
            )
            notlar += not_
        elif baglam.son_konu:
            yeni, not_ = self._degistir(yeni, _NESNE_KALIPLARI, baglam.son_konu)
            notlar += not_

        # 3) Çıplak "dosyayı" — isim verilmemişse son dosyayla nitelendir
        if baglam.son_dosya and re.search(_CIPLAK_DOSYA, yeni, flags=re.IGNORECASE):
            yeni = re.sub(_CIPLAK_DOSYA, baglam.son_dosya, yeni,
                          count=1, flags=re.IGNORECASE)
            notlar.append(f"'dosyayı' → {baglam.son_dosya}")

        return yeni, notlar

    @staticmethod
    def _degistir(metin: str, kaliplar, deger: str,
                  not_degeri: Optional[str] = None) -> Tuple[str, List[str]]:
        """
        İlk eşleşen referansı `deger` ile değiştirir.

        `not_degeri`: kullanıcıya gösterilecek sade karşılık. Metne teknik ek
        ("dosyasını") ekleniyor olabilir; kullanıcı notunda onu görmesin.
        """
        notlar = []
        for kalip in kaliplar:
            eslesme = re.search(kalip, metin, flags=re.IGNORECASE)
            if eslesme:
                notlar.append(f"'{eslesme.group(0)}' → {not_degeri or deger}")
                return re.sub(kalip, deger, metin, count=1, flags=re.IGNORECASE), notlar
        return metin, notlar


# Uygulama genelinde tek yönetici (engine bunu kullanır)
BAGLAM = BaglamYoneticisi()
