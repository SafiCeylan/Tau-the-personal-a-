# -*- coding: utf-8 -*-
"""
ULTRON — REFLECTION (Faz 8)

Kullanıcının notundan:

    Görev bitti. → Sonra kendi kendine soruyor:
    "Gerçekten tamamlandı mı? Eksik adım kaldı mı?"
    Bu ikinci kontrol katmanı hataları ciddi azaltır.

═══════════════════════════════════════════════════════════════════════
NEDEN LLM'E SORMUYORUZ
═══════════════════════════════════════════════════════════════════════

"Gerçekten oldu mu?" sorusunu modele sormak işe yaramaz: eylemi uydurmuş
bir model, kontrolü de uydurur. Üstelik her komuta bir LLM turu daha
eklemek Ultron'u yavaşlatır.

Bunun yerine iki DETERMİNİSTİK kontrol yapılır:

1. KANIT KONTROLÜ — iddia edilen eylemin izi var mı?
   "Ekran görüntüsü aldım" dedi → dosya diskte var mı, boyutu sıfır mı?
   "Hatırlatma kaydettim" dedi → kayıt veritabanında mı?
   Bunlar tartışmasız kontrollerdir: ya vardır ya yoktur.

2. HALÜSİNASYON FRENİ — LLM yapmadığı işi yapmış gibi anlattı mı?
   `CLAUDE.md`: "qwen2.5:3b eylemi yapmış gibi rol yapar." PromptGenerator'da
   bunu yasaklayan katı kurallar var ama HİÇBİR ŞEY doğrulamıyordu.
   Hiçbir araç çalışmamışken cevapta "açtım / gönderdim / kaydettim" geçiyorsa
   kullanıcı uyarılır.

═══════════════════════════════════════════════════════════════════════
KURAL: YANSIMA BİLGİ EKLER, SONUCU TERSİNE ÇEVİRMEZ
═══════════════════════════════════════════════════════════════════════

Belirsiz kanıtla "aslında olmadı" demek, çalışan bir işi başarısız
göstermektir. Sonuç yalnızca kanıt TARTIŞMASIZ olduğunda (dosya diskte yok)
başarısıza çevrilir; diğer her durumda yalnızca not düşülür.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Dogrulama:
    kontrol_edildi: bool = False     # bu araç için bir kontrol var mıydı
    gecti: bool = True               # kanıt bulundu mu
    kesin: bool = False              # kanıt tartışmasız mı (sonucu çevirebilir)
    mesaj: str = ""


# =========================================================================
# 1. KANIT KONTROLÜ
# =========================================================================
def _ekran_goruntusu_dogrula(ctx) -> Dogrulama:
    yol = (ctx.entities or {}).get('screenshot_path')
    if not yol:
        return Dogrulama()
    try:
        if os.path.isfile(yol) and os.path.getsize(yol) > 0:
            return Dogrulama(kontrol_edildi=True, gecti=True, kesin=True)
    except OSError:
        pass
    # Dosya yoksa bu TARTIŞMASIZ bir başarısızlıktır
    return Dogrulama(
        kontrol_edildi=True, gecti=False, kesin=True,
        mesaj="⚠️ Ekran görüntüsü alındı denildi ama dosya diskte yok.")


def _hatirlatma_dogrula(ctx, db_cursor) -> Dogrulama:
    if db_cursor is None:
        return Dogrulama()
    try:
        satir = db_cursor.execute(
            "SELECT COUNT(*) FROM hatirlatmalar WHERE durum = 'bekliyor'").fetchone()
    except Exception:
        return Dogrulama()          # tablo/şema farklıysa sessizce geç
    if satir and satir[0] > 0:
        return Dogrulama(kontrol_edildi=True, gecti=True, kesin=True)
    return Dogrulama(
        kontrol_edildi=True, gecti=False, kesin=True,
        mesaj="⚠️ Hatırlatma kaydedildi denildi ama kayıtlarda görünmüyor.")


def _not_dogrula(ctx, db_cursor) -> Dogrulama:
    if db_cursor is None:
        return Dogrulama()
    try:
        satir = db_cursor.execute("SELECT COUNT(*) FROM notlar").fetchone()
    except Exception:
        return Dogrulama()
    if satir and satir[0] > 0:
        return Dogrulama(kontrol_edildi=True, gecti=True, kesin=True)
    return Dogrulama(
        kontrol_edildi=True, gecti=False, kesin=True,
        mesaj="⚠️ Not kaydedildi denildi ama notlarda görünmüyor.")


# Hangi araç hangi kanıtla doğrulanır. Buraya YALNIZCA tartışmasız
# kontroller eklenmeli — "belki" niteliğindeki kanıt yanlış alarm üretir.
_DOGRULAYICILAR = {
    'ekran_goruntusu': lambda ctx, cur: _ekran_goruntusu_dogrula(ctx),
    'hatirlatma_kur': _hatirlatma_dogrula,
    'not_yonet': _not_dogrula,
}


def eylemi_dogrula(ctx, db_cursor=None) -> Dogrulama:
    """Çalışan aracın iddiasının kanıtı var mı?"""
    if not ctx.execution_success or not ctx.son_arac:
        return Dogrulama()
    dogrulayici = _DOGRULAYICILAR.get(ctx.son_arac)
    if dogrulayici is None:
        return Dogrulama()
    try:
        return dogrulayici(ctx, db_cursor)
    except Exception as e:
        print(f"[Ultron Yansıma] Doğrulama hatası: {e}")
        return Dogrulama()


# =========================================================================
# 2. HALÜSİNASYON FRENİ
# =========================================================================
# "Yaptım" anlamına gelen bitmiş eylem kalıpları. Sadece 1. tekil şahıs
# geçmiş zaman — "açabilirim", "açmak ister misin" gibi ifadeler SAYILMAZ.
_EYLEM_IDDIASI = re.compile(
    r'\b('
    r'a[çc]t[ıi]m|kapatt[ıi]m|ba[şs]latt[ıi]m|[çc]al[ıi][şs]t[ıi]rd[ıi]m'
    r'|g[öo]nderdim|yollad[ıi]m|ilettim|payla[şs]t[ıi]m'
    r'|kaydettim|olu[şs]turdum|kurdum|ayarlad[ıi]m|sildim|indirdim'
    r'|ekledim|g[üu]ncelledim|ta[şs][ıi]d[ıi]m'
    r')\b', re.IGNORECASE)

# Bu ifadeler varsa iddia "yapılmış" sayılmaz — koşul/teklif/geçmiş anlatım
_MASUM_BAGLAM = re.compile(
    r'\b(ister misin|isterseniz|edebilirim|yapabilirim|a[çc]abilirim'
    r'|[öo]nce|e[ğg]er|yapmam[ıi] ister|onaylarsan)\b', re.IGNORECASE)


def hayali_eylem_var_mi(cevap: str, arac_calisti: bool) -> Optional[str]:
    """
    LLM cevabında yapılmamış bir eylem iddiası var mı?

    `arac_calisti=True` ise kontrol YAPILMAZ: gerçekten bir şey olduysa
    "açtım" demek doğrudur.

    Dönüş: uyarı metni veya None.
    """
    if arac_calisti or not cevap:
        return None
    if _MASUM_BAGLAM.search(cevap):
        return None
    eslesme = _EYLEM_IDDIASI.search(cevap)
    if not eslesme:
        return None
    return (f"\n\n⚠️ **Dikkat:** Yukarıdaki cevapta \"{eslesme.group(0)}\" deniyor "
            f"ama **hiçbir işlem çalıştırılmadı** — bu yalnızca modelin metni. "
            f"Gerçekten yapılmasını istiyorsan komutu net yazar mısın?")


# =========================================================================
# Boru hattı girişi
# =========================================================================
def yansit(ctx, db_cursor=None):
    """
    Yürütmeden sonra çalışır; bağlamı yerinde günceller.

    ⚠️ Sonucu yalnızca KESİN kanıtla tersine çevirir. Belirsizlikte sadece
    not düşer — çalışan bir işi başarısız göstermek, hiç kontrol etmemekten
    kötüdür.
    """
    dogrulama = eylemi_dogrula(ctx, db_cursor)
    if dogrulama.kontrol_edildi and not dogrulama.gecti and dogrulama.kesin:
        ctx.execution_success = False
        ctx.verification_passed = False
        ctx.error_reason = dogrulama.mesaj
        ctx.execution_result = (ctx.execution_result or '') + "\n\n" + dogrulama.mesaj

    uyari = hayali_eylem_var_mi(ctx.llm_response, bool(ctx.execution_success))
    if uyari:
        ctx.llm_response = (ctx.llm_response or '') + uyari
        ctx.verification_passed = False

    return ctx
