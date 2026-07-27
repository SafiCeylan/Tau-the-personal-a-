# -*- coding: utf-8 -*-
"""
ULTRON — PLANNER (Faz 1)

Kullanıcı cümlesini GÖREV LİSTESİNE çevirir. Yürütmez.

    "staj raporunu bul, bulamazsan indeksi güncelle, sonra anneme gönder"
        ↓
    1. dosya_ara(sorgu="staj raporu")
    2. indeks_yonet()            [koşul: 1 başarısızsa]
    3. dosya_ara(sorgu="staj raporu")  [koşul: 2 başarılıysa]
    4. dosya_gonder(...)         [onay ister]

TASARIM KURALLARI (kullanıcının notundan):
  1. Planner ASLA iş yapmaz. `dosya_ara()` çağırmaz, `Gorev(eylem="dosya_ara")` üretir.
  2. Planner aracın NASIL çalıştığını bilmez. Bugün indeks, yarın ElasticSearch —
     planner değişmez. Çözümü `PlanYurutucu` yapar.
  3. Planner LLM'den BAĞIMSIZ veri modeli üretir. Qwen, Gemini, yarın başka bir
     model — hepsi aynı `Plan` nesnesini doldurur, sistemin geri kalanı değişmez.
  4. Planner kısa düşünür: amaç → görevler → bitir. Bir sayfalık reasoning yok
     (sıcaklık 0, şemaya zorlanmış çıktı).

⚠️ GECİKME — mimarinin en önemli kısıtı:
   qwen2.5:7b bir planı ~25 saniyede üretiyor. "Chrome aç" için 25 saniye
   beklemek kabul edilemez. Bu yüzden:
     • Regex bir intent yakaladıysa planner HİÇ çalışmaz (deterministik önce).
     • Plan BİR KEZ üretilir; her adımdan sonra LLM'e geri DÖNÜLMEZ.
       Sadece bir görev başarısız olursa yeniden planlama düşünülür.
   `cok_adimli_olabilir()` bu kapının bekçisidir.

⚠️ LLM olmayan parametre uydurur (test edildi: `dosya_gonder`e "alan" ekledi).
   Bu yüzden `_parametreleri_suz` aracın BEYAN ETTİĞİ parametreler dışındakileri
   atar. Sessizce geçirmek, aracın **kwargs'ında kaybolmalarına yol açardı.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.tools import DEFTER, RISK_ONAY


# --- Görev durumları ------------------------------------------------------
BEKLIYOR = "bekliyor"
CALISIYOR = "calisiyor"
BITTI = "bitti"
BASARISIZ = "basarisiz"
ATLANDI = "atlandi"        # koşulu tutmadı
ONAY_BEKLIYOR = "onay_bekliyor"

# --- Koşul tipleri (kapalı liste — LLM serbest kod üretemez) --------------
KOSUL_YOK = None
KOSUL_BASARILI = "basarili_ise"
KOSUL_BASARISIZ = "basarisiz_ise"
GECERLI_KOSULLAR = (KOSUL_BASARILI, KOSUL_BASARISIZ)

# Aşırı uzun plan = model saçmalamış demektir; yürütmeden kes.
MAKS_GOREV = 8


@dataclass
class Gorev:
    """Tek bir adım. `eylem` bir araç adıdır; parametreler o araca aittir."""
    id: int
    eylem: str
    parametreler: Dict[str, Any] = field(default_factory=dict)
    # {"tip": "basarisiz_ise", "gorev_id": 1} → 1 başarısızsa çalış
    kosul: Optional[Dict[str, Any]] = None
    durum: str = BEKLIYOR
    sonuc: Optional[str] = None

    def sozluge(self) -> Dict[str, Any]:
        return {
            "id": self.id, "eylem": self.eylem, "parametreler": self.parametreler,
            "kosul": self.kosul, "durum": self.durum, "sonuc": self.sonuc,
        }


@dataclass
class Plan:
    hedef: str
    gorevler: List[Gorev] = field(default_factory=list)
    # Planner'ın kullanıcıya söylemek istediği not (araç bulunamadı vb.)
    uyarilar: List[str] = field(default_factory=list)

    def onay_gerektirenler(self) -> List[Gorev]:
        """Riskli araç kullanan görevler — yürütmeden önce onay kartı gerekir."""
        riskli = []
        for gorev in self.gorevler:
            arac = DEFTER.getir(gorev.eylem)
            if arac and arac.risk == RISK_ONAY:
                riskli.append(gorev)
        return riskli

    def ozet(self) -> str:
        """Kullanıcıya gösterilecek okunabilir plan."""
        satirlar = [f"📋 **Plan:** {self.hedef}"]
        for gorev in self.gorevler:
            kosul_notu = ""
            if gorev.kosul:
                tip = "başarısızsa" if gorev.kosul.get("tip") == KOSUL_BASARISIZ else "başarılıysa"
                kosul_notu = f"  _(görev {gorev.kosul.get('gorev_id')} {tip})_"
            satirlar.append(f"{gorev.id}. {gorev.eylem}{kosul_notu}")
        for uyari in self.uyarilar:
            satirlar.append(f"⚠️ {uyari}")
        return "\n".join(satirlar)


# =========================================================================
# LLM'e dayatılan şema — çıktı buna UYMAK ZORUNDA (grammar-constrained)
# =========================================================================
def plan_semasi() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "hedef": {"type": "string"},
            "gorevler": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "eylem": {"type": "string", "enum": DEFTER.adlar()},
                        "parametreler": {"type": "object"},
                        "kosul": {
                            "type": "object",
                            "properties": {
                                "tip": {"type": "string", "enum": list(GECERLI_KOSULLAR)},
                                "gorev_id": {"type": "integer"},
                            },
                        },
                    },
                    "required": ["id", "eylem"],
                },
            },
        },
        "required": ["hedef", "gorevler"],
    }


PLANNER_ISTEMI = """Sen bir görev planlayıcısısın. Kullanıcının cümlesini adımlara böl.

KURALLAR:
- SADECE aşağıdaki araçları kullan. Listede olmayan bir araç ADI UYDURMA.
- Her aracın sadece kendi parametrelerini ver. Olmayan parametre EKLEME.
- En fazla {maks} adım üret. Gereksiz adım ekleme; tek adımlık iş tek adım kalsın.
- Bir adım ancak başka bir adımın sonucuna bağlıysa "kosul" ekle:
    {{"tip": "basarisiz_ise", "gorev_id": 1}}  → 1. adım başarısızsa çalışır
    {{"tip": "basarili_ise", "gorev_id": 1}}   → 1. adım başarılıysa çalışır
  Koşulsuz adımlar sırayla çalışır.
- Kullanıcıya soru sorma, açıklama yazma. Sadece planı üret.

KULLANILABİLİR ARAÇLAR:
{katalog}

KULLANICI KOMUTU:
{komut}"""


def istem_kur(komut: str) -> str:
    return PLANNER_ISTEMI.format(
        maks=MAKS_GOREV, katalog=DEFTER.planner_katalogu(), komut=komut
    )


# =========================================================================
# Doğrulama — LLM çıktısı ASLA doğrudan güvenilmez
# =========================================================================
def _parametreleri_suz(arac_adi: str, ham: Any) -> Tuple[Dict[str, Any], List[str]]:
    """
    Aracın beyan etmediği parametreleri atar.

    Neden: model uydurur. Testte `dosya_gonder`e olmayan bir "alan" parametresi
    ekledi. Araçlar **kwargs yuttuğu için bunlar sessizce kaybolur ve hata
    teşhis edilemez hale gelir.
    """
    if not isinstance(ham, dict):
        return {}, []

    arac = DEFTER.getir(arac_adi)
    if arac is None:
        return {}, []

    izinli = set(arac.parametreler.keys())
    suzulmus, atilan = {}, []
    for anahtar, deger in ham.items():
        if anahtar in izinli:
            suzulmus[anahtar] = deger
        else:
            atilan.append(anahtar)
    return suzulmus, atilan


def _kosul_gecerli_mi(kosul: Any, onceki_idler: set) -> bool:
    if not isinstance(kosul, dict):
        return False
    if kosul.get("tip") not in GECERLI_KOSULLAR:
        return False
    # İleriye referans YASAK — sonsuz/anlamsız bağımlılık oluşturur
    return kosul.get("gorev_id") in onceki_idler


def plani_dogrula(ham: Dict[str, Any]) -> Plan:
    """
    Ham LLM sözlüğünü güvenli bir `Plan`a çevirir.

    Elenen her şey `uyarilar`a yazılır — sessizce yutulmaz, çünkü "planı
    uyguladım" deyip adımı atlamak en kötü hata türüdür.
    """
    plan = Plan(hedef=str(ham.get("hedef") or "").strip() or "isimsiz plan")
    ham_gorevler = ham.get("gorevler")
    if not isinstance(ham_gorevler, list):
        plan.uyarilar.append("Plan görev listesi içermiyor.")
        return plan

    if len(ham_gorevler) > MAKS_GOREV:
        plan.uyarilar.append(
            f"Plan {len(ham_gorevler)} adım içeriyordu, ilk {MAKS_GOREV} adım alındı."
        )
        ham_gorevler = ham_gorevler[:MAKS_GOREV]

    gorulen_idler = set()
    for sira, ham_gorev in enumerate(ham_gorevler, start=1):
        if not isinstance(ham_gorev, dict):
            continue

        eylem = str(ham_gorev.get("eylem") or "").strip()
        if DEFTER.getir(eylem) is None:
            plan.uyarilar.append(f"Bilinmeyen araç atlandı: '{eylem}'")
            continue

        # id'yi modele bırakma: çakışabilir/atlayabilir. Sıra numarası kullan.
        gorev_id = sira
        parametreler, atilan = _parametreleri_suz(eylem, ham_gorev.get("parametreler"))
        if atilan:
            plan.uyarilar.append(
                f"{eylem}: tanınmayan parametre atıldı → {', '.join(atilan)}"
            )

        kosul = ham_gorev.get("kosul")
        if kosul and not _kosul_gecerli_mi(kosul, gorulen_idler):
            plan.uyarilar.append(f"{eylem}: geçersiz koşul yok sayıldı.")
            kosul = None

        plan.gorevler.append(Gorev(
            id=gorev_id, eylem=eylem, parametreler=parametreler, kosul=kosul,
        ))
        gorulen_idler.add(gorev_id)

    if not plan.gorevler:
        plan.uyarilar.append("Uygulanabilir adım kalmadı.")
    return plan


# =========================================================================
# Planner kapısı — planner NE ZAMAN çalışmalı
# =========================================================================
_COK_ADIMLI_ISARETLER = (
    " sonra ", " ardından", " ve sonra", " bulamazsan", " bulursan",
    " olmazsa", " yoksa", " sonrasında", " peşinden", " daha sonra",
    " önce ", " en son", " bittikten sonra",
)


def cok_adimli_olabilir(metin: str) -> bool:
    """
    Planner'ın kapı bekçisi.

    Planner 25 saniye sürüyor; "chrome aç" için çalıştırmak kabul edilemez.
    Sadece cümlede sıralama/koşul işareti varsa planlamaya değer.

    NOT: Bu kapı, regex intent'i KAÇIRDIKTAN sonra bakılır. Deterministik yol
    her zaman önce gelir (projenin 1 numaralı geliştirme kuralı).
    """
    if not metin:
        return False
    kucuk = f" {metin.lower()} "
    # SADECE açık sıralama/koşul ifadesi kapıyı açar. Virgül yeterli DEĞİLDİR:
    # "iyi günler, nasılsın" gibi sıradan cümleler 25 saniyelik planlamaya
    # girerdi.
    return any(isaret in kucuk for isaret in _COK_ADIMLI_ISARETLER)


# =========================================================================
# Üretim
# =========================================================================
def plan_uret(komut: str, config: Dict[str, Any]) -> Tuple[Optional[Plan], Optional[str]]:
    """
    Komuttan plan üretir → (Plan, hata).

    Sağlayıcı `ollama` değilse şema zorlaması yoktur; o durumda plan üretimi
    denenmez (bozuk JSON riskine girmektense planner'ı devre dışı bırakmak
    daha güvenlidir — akış eski tek-adımlı yola düşer).
    """
    saglayici = (config or {}).get('ai_provider', 'ollama')
    if saglayici != 'ollama':
        return None, f"Planner şu an sadece Ollama ile çalışıyor (aktif: {saglayici})."

    from features.ollama import ollama_json

    ham, hata = ollama_json(
        istem_kur(komut),
        plan_semasi(),
        ollama_url=config.get('ollama_url', 'http://127.0.0.1:11434'),
        model=config.get('ollama_model', 'qwen2.5:7b'),
        timeout=int(config.get('planner_timeout', 180)),
    )
    if hata:
        return None, hata

    return plani_dogrula(ham or {}), None
