"""
ULTRON — ARAÇ KAYIT DEFTERİ (Tool Registry)

NEDEN VAR:
    Planner'ın ürettiği plan şuna benzeyecek:

        {"action": "dosya_ara", "params": {"sorgu": "staj raporu"}}

    Bu planın bağlanacağı bir arayüz olmalı. Önceden her yetenek
    `ExecutionEngineLayer` içinde regex'e gömülü bir `if` bloğuydu — dışarıdan
    isimle çağrılamıyordu, dolayısıyla plan üretmenin bir anlamı yoktu.
    Artık her yetenek isimli, parametreli, tek tek çağrılabilir bir ARAÇ.

TASARIM KURALLARI:
    • Araç, LLM'i TANIMAZ. Saf fonksiyondur; girdi alır, `AracSonuc` döner.
    • Araç, `UltronContext`i TANIMAZ. Böylece plan dışında da (test, Telegram,
      zamanlanmış görev) çağrılabilir.
    • Planner araca doğrudan ERİŞMEZ; sadece adını üretir. Çözümü Executor yapar.
      (Bugün `dosya_ara` indekse gidiyor, yarın ElasticSearch olur — planner değişmez.)

ÜÇ DURUMLU SONUÇ — dikkat:
    `islendi` ile `basarili` AYNI ŞEY DEĞİLDİR.
        islendi=False           → araç bu isteği üstlenmedi, akış LLM'e düşmeli
        islendi=True, basarili=False → araç denedi ve BAŞARISIZ oldu (hata mesajı var)
    Eski `if handled:` zincirinin davranışı buydu; ikisini birleştirirsek
    "dosya bulunamadı" cevabı LLM'e düşüp uydurma cevaba dönüşür.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# Risk seviyeleri — SecurityAnalyzer'ın skoruyla birlikte kullanılır.
# Planner bir aracı plana koyabilir ama RISK_ONAY olanlar kullanıcı onayı
# olmadan yürütülemez (AskConfirmationTask üretilir).
RISK_GUVENLI = "guvenli"      # Chrome aç, saat söyle — sormadan yapılır
RISK_ONAY = "onay_gerek"      # WhatsApp/mail gönder, dosya sil — onay kartı şart


@dataclass
class AracSonuc:
    """Bir aracın çıktısı."""
    islendi: bool = True
    basarili: bool = False
    mesaj: str = ""
    # Bağlama yazılacak ek veri (örn. {"screenshot_path": "..."}) — Executor
    # bunu ctx.entities'e aktarır.
    veri: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def islenmedi(cls) -> "AracSonuc":
        """Araç bu isteği üstlenmedi — akış LLM'e düşsün."""
        return cls(islendi=False, basarili=False)

    @classmethod
    def ok(cls, mesaj: str, **veri) -> "AracSonuc":
        return cls(islendi=True, basarili=True, mesaj=mesaj, veri=veri)

    @classmethod
    def hata(cls, mesaj: str, **veri) -> "AracSonuc":
        return cls(islendi=True, basarili=False, mesaj=mesaj, veri=veri)


@dataclass
class Arac:
    """Çağrılabilir tek bir yetenek."""
    ad: str
    aciklama: str                       # planner prompt'una girer — kısa ve net olmalı
    calistir: Callable[..., AracSonuc]
    parametreler: Dict[str, str] = field(default_factory=dict)
    risk: str = RISK_GUVENLI
    # Geriye uyum: bu araç hangi eski intent'lere karşılık geliyor. Execution
    # katmanı intent'ten araca bu alanla ulaşır. Planner bu alanı KULLANMAZ.
    # (SYSTEM_CONTROL/SET_VOLUME/PLAY_MUSIC gibi birden fazla intent tek araca
    #  bağlanabilir — bu yüzden demet.)
    intentler: tuple = ()
    # DB erişimi gereken araçlar (hatırlatma, not, sayaç...) cursor/conn alır.
    db_ister: bool = False


class AracDefteri:
    """Araçların tek kayıt noktası."""

    def __init__(self):
        self._araclar: Dict[str, Arac] = {}
        self._intent_haritasi: Dict[str, str] = {}

    def kaydet(self, arac: Arac) -> Arac:
        if arac.ad in self._araclar:
            raise ValueError(f"Araç adı zaten kayıtlı: {arac.ad}")
        self._araclar[arac.ad] = arac
        for intent in arac.intentler:
            # İlk kaydedilen kazanır — kayıt sırası, eski if/elif zincirinin
            # sırasıyla aynı tutulmalı.
            self._intent_haritasi.setdefault(intent, arac.ad)
        return arac

    def getir(self, ad: str) -> Optional[Arac]:
        return self._araclar.get(ad)

    def intent_ile(self, intent: str) -> Optional[Arac]:
        ad = self._intent_haritasi.get(intent)
        return self._araclar.get(ad) if ad else None

    def hepsi(self) -> List[Arac]:
        return list(self._araclar.values())

    def adlar(self) -> List[str]:
        return list(self._araclar.keys())

    def planner_katalogu(self) -> str:
        """Planner prompt'una gömülecek araç listesi (LLM okur)."""
        satirlar = []
        for arac in self._araclar.values():
            if arac.parametreler:
                par = ", ".join(f"{k}: {v}" for k, v in arac.parametreler.items())
            else:
                par = "parametresiz"
            satirlar.append(f"- {arac.ad}({par}) — {arac.aciklama}")
        return "\n".join(satirlar)


# Uygulama genelinde tek defter
DEFTER = AracDefteri()


def arac_kaydet(ad: str, aciklama: str, parametreler: Optional[Dict[str, str]] = None,
                risk: str = RISK_GUVENLI, intent=None, db_ister: bool = False):
    """
    Dekoratör: bir fonksiyonu araç olarak deftere yazar.
    `intent` tek bir metin ya da metin demeti olabilir.
    """
    if intent is None:
        intentler = ()
    elif isinstance(intent, str):
        intentler = (intent,)
    else:
        intentler = tuple(intent)

    def sarmalayici(fn: Callable[..., AracSonuc]) -> Callable[..., AracSonuc]:
        DEFTER.kaydet(Arac(
            ad=ad,
            aciklama=aciklama,
            calistir=fn,
            parametreler=parametreler or {},
            risk=risk,
            intentler=intentler,
            db_ister=db_ister,
        ))
        return fn
    return sarmalayici
