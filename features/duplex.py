# -*- coding: utf-8 -*-
"""
🎙️ CANLI SESLİ SOHBET — oturum durum makinesi.

NEDEN AYRI BİR MODÜL (21 Eyl 2026): Canlı sohbetin kuralları `tau_window.py`
içinde üç ayrı slot'a dağılmıştı ve tek bir bayraktan (`speech._DUPLEX_ACTIVE`)
ibaretti. Sonuçları ölçüldü:

  • Devam tetiği TANIMSIZ bir metoda kuruluydu → sohbet ilk cevaptan sonra
    dinlemeye hiç dönmedi (13 Ağu – 16 Eyl, Qt hatayı yuttu).
  • Kapatma kalıbı `\b(dur|durdur|kapat|...)\b` TÜM cümlede aranıyordu:
    **"müziği durdur" sesli sohbeti kapatıyordu** — komut çalışmıyor, üstelik
    kullanıcı neden kapandığını anlamıyordu.
  • Tek bir sessizlik ya da tek bir ağ hatası oturumu bitiriyordu.
  • Oturumun süresi yoktu: açık unutulan bir sohbet mikrofonu saatlerce açık
    tutabilirdi.

Bu modül SAF mantıktır (Qt yok, ses yok, thread yok) — `tests/test_duplex.py`
her kuralı donanımsız sınar. Arayüz yalnızca olayları bildirir ve dönen kararı
uygular.

KARAR SÖZLEŞMESİ: her olay `(eylem, mesaj)` döner.
    eylem = 'dinle'  → mikrofonu aç, kullanıcıyı bekle
            'isle'   → metni normal komut akışına ver
            'kapat'  → oturum bitti
            'yoksay' → oturum kapalı, yapacak bir şey yok
    mesaj = kullanıcıya gösterilecek metin (yoksa None)
"""

import re
import time

KAPALI = 'kapali'
DINLIYOR = 'dinliyor'
ISLIYOR = 'isliyor'
KONUSUYOR = 'konusuyor'

# Ayarlar (config ile değiştirilebilir)
VARSAYILAN_MAX_SESSIZLIK = 2      # ardışık kaç sessizlikten sonra kapanır
VARSAYILAN_MAX_HATA = 2           # ardışık kaç hatadan sonra kapanır
VARSAYILAN_MAX_DAKIKA = 10        # oturum tavanı

# ⚠️ KAPATMA YALNIZ SOHBETİN KENDİSİ HAKKINDAYSA.
# Eski kural cümlenin HERHANGİ bir yerinde "durdur" görmeyi yeterli sayıyordu;
# "müziği durdur" / "ekran takibini durdur" / "hatırlatmayı iptal et" komutları
# sesli sohbeti kapatıyordu. Artık iki yol var:
#   1) Cümle SADECE kapatma sözünden ibaret ("dur", "yeter", "tamam")
#   2) Cümle açıkça sesli sohbetten bahsediyor ("sesli sohbeti kapat")
_TEK_BASINA_KAPATANLAR = {
    'dur', 'durdur', 'kapat', 'kapan', 'bitir', 'iptal', 'yeter', 'tamam',
    'tamamdir', 'tamamdır', 'sus', 'bitti', 'kapa', 'cik', 'çık', 'iptal et',
    'sessiz ol', 'kes', 'kapatabilirsin', 'sohbeti kapat',
}
_SOHBETTEN_BAHSEDEN = re.compile(
    r'(sesli|canlı|canli)\s+(sohbet\w*|konuşma\w*|konusma\w*|mod\w*)|'
    r'\bsohbeti\s+(kapat|bitir|durdur|sonlandır|sonlandir)',
    re.IGNORECASE)
_KAPATMA_FIILI = re.compile(
    r'\b(kapat\w*|bitir\w*|durdur\w*|iptal|sonlandır\w*|sonlandir\w*|çık\w*|cik\w*)\b',
    re.IGNORECASE)


def kapatma_istegi_mi(metin: str) -> bool:
    """Bu cümle sesli sohbeti KAPATMAK için mi söylendi, yoksa bir komut mu?"""
    m = (metin or '').strip().lower().strip('.!?,;:')
    if not m:
        return False
    if m in _TEK_BASINA_KAPATANLAR:
        return True
    if _SOHBETTEN_BAHSEDEN.search(m) and _KAPATMA_FIILI.search(m):
        return True
    return False


class DuplexOturumu:
    """Canlı sesli sohbetin tek gerçeği. Arayüz bu nesneye olayları bildirir."""

    def __init__(self, config: dict = None, simdi=time.monotonic):
        self._simdi = simdi          # testler saati taklit edebilsin
        self.config = config or {}
        self.durum = KAPALI
        self.baslangic = None
        self.tur = 0
        self._sessizlik = 0
        self._hata = 0

    # ---------------------------------------------------------------- ayarlar
    def _ayar(self, anahtar, varsayilan):
        try:
            deger = int(self.config.get(anahtar, varsayilan))
        except (TypeError, ValueError):
            return varsayilan
        return deger if deger > 0 else varsayilan

    @property
    def max_sessizlik(self):
        return self._ayar('duplex_max_sessizlik', VARSAYILAN_MAX_SESSIZLIK)

    @property
    def max_hata(self):
        return self._ayar('duplex_max_hata', VARSAYILAN_MAX_HATA)

    @property
    def max_dakika(self):
        return self._ayar('duplex_max_dakika', VARSAYILAN_MAX_DAKIKA)

    def config_guncelle(self, config: dict):
        self.config = config or {}

    # ----------------------------------------------------------------- durum
    def aktif_mi(self) -> bool:
        return self.durum != KAPALI

    def sure_sn(self) -> float:
        return 0.0 if self.baslangic is None else self._simdi() - self.baslangic

    # ---------------------------------------------------------------- olaylar
    def baslat(self):
        """Kullanıcı sesli sohbeti açtı → (eylem, mesaj)."""
        if self.aktif_mi():
            return 'dinle', None          # zaten açık, ikinci kez duyurma
        self.durum = DINLIYOR
        self.baslangic = self._simdi()
        self.tur = 0
        self._sessizlik = 0
        self._hata = 0
        return 'dinle', ("🎙️ **Canlı sesli sohbet açık.** Konuş, her cevaptan sonra "
                         "seni dinlemeye devam edeceğim. Bitirmek için \"dur\" de.")

    def kapat(self, sebep: str = None):
        """Oturumu kapatır → (eylem, mesaj). Kapalıyken çağrılırsa sessizdir."""
        if not self.aktif_mi():
            return 'yoksay', None
        tur, sure = self.tur, self.sure_sn()
        self.durum = KAPALI
        self.baslangic = None
        self._sessizlik = 0
        self._hata = 0
        ozet = f" ({tur} konuşma, {int(sure)} sn)" if tur else ""
        mesaj = f"🎙️ **Canlı sesli sohbet kapandı.**{ozet}"
        if sebep:
            mesaj += f" {sebep}"
        return 'kapat', mesaj

    def kullanici_konustu(self, metin: str):
        """Mikrofondan metin geldi → (eylem, mesaj)."""
        if not self.aktif_mi():
            return 'yoksay', None
        metin = (metin or '').strip()
        if not metin:
            return self.sessizlik_oldu()

        self._sessizlik = 0
        self._hata = 0

        if kapatma_istegi_mi(metin):
            return self.kapat()

        bitti, mesaj = self._sure_doldu_mu()
        if bitti:
            return 'kapat', mesaj

        self.tur += 1
        self.durum = ISLIYOR
        return 'isle', None

    def sessizlik_oldu(self):
        """Dinledik ama ses gelmedi → (eylem, mesaj)."""
        if not self.aktif_mi():
            return 'yoksay', None
        self._sessizlik += 1
        if self._sessizlik >= self.max_sessizlik:
            return self.kapat("Ses gelmedi.")
        self.durum = DINLIYOR
        return 'dinle', "🎙️ Seni duyamadım, tekrar dinliyorum…"

    def hata_oldu(self, hata: str = None):
        """Dinleme/tanıma hatası → (eylem, mesaj).

        TEK hata oturumu kapatmaz: geçici bir ağ kesintisi ya da mikrofonu bir
        an başka uygulamanın kapması yüzünden konuşmanın ortasında kapanmak,
        kullanıcıyı komutu baştan söylemeye zorlar.
        """
        if not self.aktif_mi():
            return 'yoksay', None
        self._hata += 1
        if self._hata >= self.max_hata:
            return self.kapat(f"Dinleme sürekli başarısız oldu ({hata}).")
        self.durum = DINLIYOR
        return 'dinle', f"🎙️ Dinleme hatası ({hata}) — tekrar deniyorum…"

    def konusma_basladi(self):
        if self.aktif_mi():
            self.durum = KONUSUYOR

    def konusma_bitti(self):
        """Ultron cevabını bitirdi → tekrar dinlemeye dön."""
        if not self.aktif_mi():
            return 'yoksay', None
        bitti, mesaj = self._sure_doldu_mu()
        if bitti:
            return 'kapat', mesaj
        self.durum = DINLIYOR
        return 'dinle', None

    # -------------------------------------------------------------- yardımcı
    def _sure_doldu_mu(self):
        """Tavan: açık unutulan oturum mikrofonu saatlerce açık tutmasın."""
        if self.sure_sn() >= self.max_dakika * 60:
            _, mesaj = self.kapat(f"{self.max_dakika} dakikalık süre doldu.")
            return True, mesaj
        return False, None


# Uygulama genelinde TEK oturum (mikrofon tek). Arayüz ve araçlar bunu kullanır.
OTURUM = DuplexOturumu()


def aktif_mi() -> bool:
    return OTURUM.aktif_mi()
