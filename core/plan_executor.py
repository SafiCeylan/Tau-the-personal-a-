# -*- coding: utf-8 -*-
"""
ULTRON — PLAN YÜRÜTÜCÜ (Faz 1)

Planner düşünür, burası yapar. Görev kuyruğunu sırayla işler.

    Plan → [Görev1, Görev2, Görev3] → Yürütücü → Araç Defteri → Sonuç

NEDEN AYRI MODÜL:
  Planner araçların NASIL çalıştığını bilmemeli. Araç adını somut çağrıya
  çeviren tek yer burası. Yarın `dosya_ara` ElasticSearch'e geçerse planner
  değişmez, burası bile değişmez — sadece aracın kendisi değişir.

⚠️ HER ADIMDA LLM'E DÖNÜLMEZ.
  Dosyadaki mimari şeması "Sonuçlar → Planner → devam et?" diyordu. Bu tuzak:
  qwen2.5:7b bir çağrıda ~25 saniye sürüyor, 4 adımlı görev 2 dakikayı bulurdu.
  Plan bir kez üretilir, adımlar deterministik ilerler. Bir adım başarısız
  olursa plandaki KOŞULLAR devreye girer; yeniden planlama Faz 4'ün (Recovery
  Engine) işidir.

⚠️ ONAY: riskli araçlar (WhatsApp/mail/dosya gönderimi) kullanıcı onayı olmadan
  YÜRÜTÜLMEZ. Yürütücü o noktada DURUR ve bekleyen görevi geri verir —
  kullanıcının notundaki `AskConfirmationTask` davranışı budur.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.planner import (
    ATLANDI, BASARISIZ, BEKLIYOR, BITTI, CALISIYOR, ONAY_BEKLIYOR,
    KOSUL_BASARILI, KOSUL_BASARISIZ, Gorev, Plan,
)
from core.tools import DEFTER, RISK_ONAY


@dataclass
class PlanSonucu:
    plan: Plan
    basarili: bool = False
    # Onay bekleyen görev varsa yürütme burada DURDU
    onay_bekleyen: Optional[Gorev] = None
    # Araçların bağlama bıraktığı veri (screenshot_path, focus_action...)
    veri: Dict[str, Any] = field(default_factory=dict)

    def ozet(self) -> str:
        satirlar = []
        for gorev in self.plan.gorevler:
            simge = {
                BITTI: "✅", BASARISIZ: "❌", ATLANDI: "⏭️",
                ONAY_BEKLIYOR: "🔐", BEKLIYOR: "⏳", CALISIYOR: "⏳",
            }.get(gorev.durum, "•")
            satir = f"{simge} {gorev.id}. {gorev.eylem}"
            if gorev.sonuc:
                satir += f"\n   {gorev.sonuc}"
            satirlar.append(satir)

        if self.onay_bekleyen:
            satirlar.append(
                f"\n🔐 **Onay gerekiyor:** `{self.onay_bekleyen.eylem}` adımı için "
                "izin verirsen devam edeceğim."
            )
        for uyari in self.plan.uyarilar:
            satirlar.append(f"⚠️ {uyari}")
        return "\n".join(satirlar)


class PlanYurutucu:
    """
    Görev kuyruğunu işler.

    `onaylanan_gorevler`: kullanıcının onayladığı görev id'leri. Onay akışı
    ikinci turda buraya dolu gelir ve yürütme kaldığı yerden devam eder.
    """

    def __init__(self, db_cursor=None, db_conn=None, kanal="desktop",
                 onaylanan_gorevler=None):
        self.db_cursor = db_cursor
        self.db_conn = db_conn
        self.kanal = kanal
        self.onaylanan = set(onaylanan_gorevler or ())

    # ---------------------------------------------------------------
    def calistir(self, plan: Plan) -> PlanSonucu:
        sonuc = PlanSonucu(plan=plan)
        durumlar: Dict[int, str] = {}

        for gorev in plan.gorevler:
            # Onay sonrası devam: zaten çalışmış adımlar TEKRAR ÇALIŞMAZ.
            # (Aksi halde onaydan önceki her adımın yan etkisi ikinci kez olur.)
            if gorev.durum in (BITTI, BASARISIZ, ATLANDI):
                durumlar[gorev.id] = gorev.durum
                continue

            if not self._kosul_tutuyor(gorev, durumlar):
                gorev.durum = ATLANDI
                durumlar[gorev.id] = ATLANDI
                continue

            arac = DEFTER.getir(gorev.eylem)
            if arac is None:
                # plani_dogrula bunu elemiş olmalı; yine de savunma
                gorev.durum = BASARISIZ
                gorev.sonuc = f"Araç bulunamadı: {gorev.eylem}"
                durumlar[gorev.id] = BASARISIZ
                continue

            if arac.risk == RISK_ONAY and gorev.id not in self.onaylanan:
                gorev.durum = ONAY_BEKLIYOR
                sonuc.onay_bekleyen = gorev
                # Onay alınana kadar SONRAKİ adımlara geçme — sıradaki adım
                # onaylanmamış adımın çıktısına dayanıyor olabilir.
                break

            gorev.durum = CALISIYOR
            arac_sonucu = self._araci_calistir(arac, gorev)

            if arac_sonucu.veri:
                sonuc.veri.update(arac_sonucu.veri)

            if not arac_sonucu.islendi:
                # Araç üstlenmedi → bu adım başarısız sayılır. (Plan bağlamında
                # "LLM'e düş" diye bir seçenek yok; adımın sonucu belirsiz kalamaz.)
                gorev.durum = BASARISIZ
                gorev.sonuc = arac_sonucu.mesaj or "Bu adım yürütülemedi."
            elif arac_sonucu.basarili:
                gorev.durum = BITTI
                gorev.sonuc = arac_sonucu.mesaj
            else:
                gorev.durum = BASARISIZ
                gorev.sonuc = arac_sonucu.mesaj

            durumlar[gorev.id] = gorev.durum

        sonuc.basarili = bool(plan.gorevler) and all(
            g.durum in (BITTI, ATLANDI) for g in plan.gorevler
        )
        return sonuc

    # ---------------------------------------------------------------
    def _kosul_tutuyor(self, gorev: Gorev, durumlar: Dict[int, str]) -> bool:
        if not gorev.kosul:
            return True
        hedef_durum = durumlar.get(gorev.kosul.get("gorev_id"))
        if hedef_durum is None:
            # Referans verilen adım hiç çalışmadıysa koşul tutmaz
            return False
        if gorev.kosul.get("tip") == KOSUL_BASARILI:
            return hedef_durum == BITTI
        if gorev.kosul.get("tip") == KOSUL_BASARISIZ:
            return hedef_durum == BASARISIZ
        return False

    # ---------------------------------------------------------------
    def _araci_calistir(self, arac, gorev: Gorev):
        from core.tools import AracSonuc

        argumanlar = dict(gorev.parametreler)
        # Araçlar ham cümleyi de bekler (regex ayrıştırıcılar onu kullanır).
        argumanlar.setdefault('metin', self._metin_tahmini(gorev))
        if arac.db_ister:
            argumanlar['db_cursor'] = self.db_cursor
            argumanlar['db_conn'] = self.db_conn
        if arac.ad == 'dosya_gonder':
            argumanlar.setdefault('kanal', self.kanal)

        try:
            return arac.calistir(**argumanlar)
        except Exception as e:
            print(f"[Ultron Plan] {arac.ad} çalışırken hata: {e}")
            return AracSonuc.hata(f"{arac.ad} çalıştırılamadı: {e}")

    @staticmethod
    def _metin_tahmini(gorev: Gorev) -> str:
        """
        Araçların regex ayrıştırıcıları ham cümle bekler. Planner parametreleri
        ayırdığı için elimizde cümle yok; parametre değerlerini birleştirip
        makul bir metin kuruyoruz.
        """
        parcalar = [str(d) for d in gorev.parametreler.values() if isinstance(d, (str, int))]
        return " ".join(parcalar).strip()
