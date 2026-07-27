# -*- coding: utf-8 -*-
"""
ULTRON — RECOVERY ENGINE (Faz 4)

Kullanıcının notundan:

    Dosya bulunamadı.
      ↓ İsim yanlış olabilir → yakın isim ara.
      ↓ Olmazsa indeksi güncelle.
      ↓ Olmazsa kullanıcıya sor.

"Çoğu AI burada duruyor. İyi ajan alternatif plan üretir."

═══════════════════════════════════════════════════════════════════════
TASARIMIN İKİ PAZARLIKSIZ KURALI
═══════════════════════════════════════════════════════════════════════

1. KURTARMA ASLA RİSKLİ ARAÇ ÇALIŞTIRMAZ.
   Kurtarma yalnızca `RISK_GUVENLI` araçlar kullanır. "WhatsApp gönderimi
   başarısız oldu, tekrar deneyeyim" davranışı aynı mesajı iki kez gönderme
   riskidir. Riskli bir adım başarısız olduğunda kurtarma sadece TEŞHİS yapar
   (arar, bulur, bildirir) ve kararı kullanıcıya bırakır.

2. KURTARMA LLM ÇAĞIRMAZ.
   Deterministik zincir. Planner zaten ~25 saniye harcıyor; başarısızlıkta bir
   25 saniye daha eklemek Ultron'u kullanılamaz yapar. Kurtarma milisaniyeler
   içinde alternatif üretir.

Ayrıca: deneme sayısı SINIRLI (varsayılan 2). Sınırsız kurtarma, kullanıcı
farkında olmadan onlarca sorgu çalıştıran bir döngüye dönüşür.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.tools import DEFTER, RISK_GUVENLI

# Bir başarısızlık için en fazla kaç alternatif denenir
MAKS_DENEME = 2

# --- Başarısızlık tipleri -------------------------------------------------
BULUNAMADI = "bulunamadi"
ERISILEMEDI = "erisilemedi"
BILINMIYOR = "bilinmiyor"

# ⚠️ Sınıflandırma araçların MESAJ metnine bakar — kırılgan bir yöntem.
# Araç mesajını değiştirirsen buradaki kalıbı da güncelle; yoksa kurtarma
# sessizce devreden çıkar (hata vermez, sadece alternatif üretmez).
_BULUNAMADI_KALIBI = re.compile(
    r'bulunamad|eşleşen dosya yok|sonuç yok|yerinde değil|o numarada bir dosya yok',
    re.IGNORECASE)
_ERISILEMEDI_KALIBI = re.compile(
    r'bağlan|erişilemedi|zaman aşımı|timeout|internet|ağ hatası',
    re.IGNORECASE)


def bulunamadi_mi(mesaj: str) -> bool:
    """Bu mesaj 'aradığını bulamadım' anlamına mı geliyor?"""
    return bool(_BULUNAMADI_KALIBI.search(mesaj or ''))


def hata_tipini_coz(sonuc) -> str:
    """Araç sonucundan başarısızlık tipini çıkarır."""
    # Araç açıkça belirttiyse ona güven — mesaj metnine bakmak son çaredir
    acik = getattr(sonuc, 'hata_tipi', None) or \
        (getattr(sonuc, 'veri', None) or {}).get('hata_tipi')
    if acik:
        return acik
    mesaj = getattr(sonuc, 'mesaj', '') or ''
    if _BULUNAMADI_KALIBI.search(mesaj):
        return BULUNAMADI
    if _ERISILEMEDI_KALIBI.search(mesaj):
        return ERISILEMEDI
    return BILINMIYOR


@dataclass
class KurtarmaDenemesi:
    """Denenecek tek bir alternatif."""
    aciklama: str                  # kullanıcıya gösterilir
    arac_adi: str
    parametreler: Dict[str, Any] = field(default_factory=dict)
    # Bu deneme asıl işi yapar mı, yoksa sadece teşhis mi? Teşhis denemeleri
    # başarılı olsa bile görev BAŞARILI sayılmaz — kullanıcıya sorulur.
    teshis: bool = False


@dataclass
class KurtarmaSonucu:
    denendi: bool = False
    basarili: bool = False
    mesaj: str = ""
    # Kullanıcıya gösterilecek adım günlüğü
    adimlar: List[str] = field(default_factory=list)


# =========================================================================
# Strateji üretimi
# =========================================================================
_DOSYA_ARACLARI = ("dosya_ara", "dosya_gonder", "dosya_ac")

# Sorgudan atılabilecek zayıf kelimeler.
#
# ⚠️ HEPSİ SADELEŞTİRİLMİŞ (ASCII) BİÇİMDE YAZILIR ve karşılaştırma da
# `file_index.sadelestir()` çıktısı üzerinde yapılır. Aksi halde "dosyasını"
# (noktasız ı) listedeki "dosyasini" ile eşleşmez, gürültü kelime elenmez ve
# "en uzun kelime" kuralı onu seçer — canlıda tam olarak bu oldu: kurtarma
# `dosyasını` diye arama yaptı.
_ZAYIF_TOKENLAR = {
    'dosya', 'dosyayi', 'dosyasi', 'dosyasini', 'dosyalari', 'dosyalarini',
    'son', 'yeni', 'eski', 'bir', 'tane', 'benim', 'bizim', 'diye', 'adli',
    'isimli', 'rapor', 'raporu', 'raporunu', 'belge', 'belgesi', 'belgeyi',
    'bul', 'ara', 'goster', 'listele', 'nerede',
    # Dolgu kelimeleri — canlıda "falan" seçilip anlamsız arama yapıldı
    'falan', 'filan', 'gibi', 'herhangi', 'seyler', 'sey',
}


def _gevsetme_adaylari(sorgu: str) -> List[str]:
    """
    Gevşetilmiş sorgu adaylarını sırayla döner (en umut verici önce).

    `file_index.ara` tüm kelimeleri AND'liyor; kelime sayısı azaldıkça eşleşme
    ihtimali artar. Tek kelimeye inip hangisinin işe yaradığını İNDEKSE sorarız.
    """
    if not sorgu:
        return []

    # Türkçe harfleri sadeleştir — zayıf kelime listesi ASCII biçimde tutulur
    # ve `file_index.ara` da aramayı sadeleştirilmiş metinde yapar.
    try:
        from features.file_index import sadelestir
        sade = sadelestir(sorgu)
    except Exception:
        sade = sorgu.lower()

    tokenlar = [t for t in re.findall(r"[\w\-.]+", sade) if len(t) >= 3]
    if len(tokenlar) < 2:
        return []                      # tek kelime zaten en gevşek hali

    anlamli = [t for t in tokenlar if t not in _ZAYIF_TOKENLAR]
    havuz = anlamli or tokenlar
    # Uzun kelime genelde daha ayırt edicidir; ama tek başına GÜVENİLMEZ —
    # canlıda "falan" (5 harf) "staj"ı (4 harf) yendi. Sıra sadece deneme
    # önceliğidir, kararı indeks verir.
    return sorted(dict.fromkeys(havuz), key=len, reverse=True)


def _sorguyu_gevset(sorgu: str) -> Optional[str]:
    """
    İndekste GERÇEKTEN eşleşen bir gevşetme bulur.

    Neden indekse soruyoruz: saf metin sezgisi ("en uzun kelime") canlıda iki
    kez yanlış seçti — önce `dosyasını`, sonra `falan`. 134 bin dosyalık bir
    indeks varken tahmin etmek gereksiz; adayları tek tek sorup sonuç vereni
    seçmek hem doğru hem milisaniyeler sürüyor.
    """
    adaylar = _gevsetme_adaylari(sorgu)
    if not adaylar:
        return None

    try:
        from features import file_index
        for aday in adaylar:
            if file_index.ara(aday, limit=1):
                return aday
    except Exception as e:
        print(f"[Ultron Kurtarma] İndeks sorgulanamadı: {e}")
        return adaylar[0]

    # Hiçbiri eşleşmedi: yine de en umut verici adayı dene ki kullanıcı
    # neyin denendiğini görsün ("falan diye aradım" gibi anlamsız bir şey değil).
    return adaylar[0]


def _indeks_bayat_mi() -> bool:
    """İndeks boş ya da hiç kurulmamışsa yenilemeye değer."""
    try:
        from features import file_index
        sayi, _son = file_index.indeks_durumu()
        return not sayi
    except Exception:
        return False


def kurtarma_denemeleri(arac_adi: str, parametreler: Dict[str, Any],
                        sonuc) -> List[KurtarmaDenemesi]:
    """
    Başarısız bir araç çağrısı için alternatif zinciri üretir.

    Boş liste = kurtarılacak bir şey yok, hatayı kullanıcıya söyle.
    """
    hata_tipi = hata_tipini_coz(sonuc)
    arac = DEFTER.getir(arac_adi)
    if arac is None:
        return []

    denemeler: List[KurtarmaDenemesi] = []

    # --- Dosya bulunamadı zinciri ------------------------------------
    if arac_adi in _DOSYA_ARACLARI and hata_tipi == BULUNAMADI:
        sorgu = (parametreler.get('sorgu') or parametreler.get('metin') or '')
        gevsek = _sorguyu_gevset(sorgu)
        if gevsek:
            denemeler.append(KurtarmaDenemesi(
                aciklama=f"adı gevşetip `{gevsek}` diye aradım",
                # `dosya_ara` DEĞİL: o klasör bazlı file_finder'a gider, indekse
                # değil. `indeks_ara` salt-okunur ve güvenli.
                arac_adi="indeks_ara",
                parametreler={"sorgu": gevsek},
                # Riskli araç başarısızsa (gönderim/açma) yalnızca TEŞHİS:
                # bulunanı kullanıcıya gösterir, kendiliğinden göndermez.
                teshis=(arac.risk != RISK_GUVENLI),
            ))

        if _indeks_bayat_mi():
            denemeler.append(KurtarmaDenemesi(
                aciklama="dosya indeksini güncelledim",
                arac_adi="indeks_yonet",
                parametreler={"metin": "dosya indeksini güncelle"},
                teshis=True,   # indeks güncellemek asıl görevi tamamlamaz
            ))

    # --- Ağ hatası: tek sefer tekrar ---------------------------------
    elif hata_tipi == ERISILEMEDI and arac.risk == RISK_GUVENLI:
        denemeler.append(KurtarmaDenemesi(
            aciklama="bağlantı hatasıydı, bir kez daha denedim",
            arac_adi=arac_adi,
            parametreler=dict(parametreler),
        ))

    # Riskli araçlar ASLA doğrudan tekrar edilmez — üretilen her denemenin
    # aracı güvenli olmalı. (Savunma: strateji tablosu yanlış yazılırsa da tutar.)
    guvenli = []
    for deneme in denemeler[:MAKS_DENEME]:
        hedef = DEFTER.getir(deneme.arac_adi)
        if hedef is not None and hedef.risk == RISK_GUVENLI:
            guvenli.append(deneme)
        else:
            print(f"[Ultron Kurtarma] Riskli araç kurtarmada kullanılamaz: "
                  f"{deneme.arac_adi}")
    return guvenli


# =========================================================================
# Yürütme
# =========================================================================
def kurtar(arac_adi: str, parametreler: Dict[str, Any], sonuc,
           db_cursor=None, db_conn=None, kanal="desktop") -> KurtarmaSonucu:
    """
    Başarısız bir araç çağrısını kurtarmayı dener.

    Dönüş `basarili=True` ise asıl iş tamamlanmıştır. `denendi=True` ama
    `basarili=False` ise alternatifler denendi, sonuç kullanıcıya bırakılıyor.
    """
    from core.tools import AracSonuc

    denemeler = kurtarma_denemeleri(arac_adi, parametreler, sonuc)
    if not denemeler:
        return KurtarmaSonucu()

    kurtarma = KurtarmaSonucu(denendi=True)

    for deneme in denemeler:
        arac = DEFTER.getir(deneme.arac_adi)
        argumanlar = dict(deneme.parametreler)
        argumanlar.setdefault('metin', argumanlar.get('sorgu', ''))
        if arac.db_ister:
            argumanlar['db_cursor'] = db_cursor
            argumanlar['db_conn'] = db_conn

        try:
            alt_sonuc = arac.calistir(**argumanlar)
        except Exception as e:
            print(f"[Ultron Kurtarma] {deneme.arac_adi} çöktü: {e}")
            kurtarma.adimlar.append(f"↳ {deneme.aciklama} — çalıştırılamadı")
            continue

        if alt_sonuc.islendi and alt_sonuc.basarili:
            kurtarma.adimlar.append(f"↳ {deneme.aciklama} ✅")
            kurtarma.mesaj = alt_sonuc.mesaj
            # Teşhis denemesi asıl işi TAMAMLAMAZ — kullanıcı karar versin.
            kurtarma.basarili = not deneme.teshis
            return kurtarma

        kurtarma.adimlar.append(f"↳ {deneme.aciklama} — sonuç yok")

    return kurtarma


def kurtarma_raporu(asil_mesaj: str, kurtarma: KurtarmaSonucu) -> str:
    """
    Kullanıcıya gösterilecek birleşik metin.

    ⚠️ CEVAPLANAMAYACAK SORU SORMA. Önceki sürüm her başarısızlıkta
    "Devam etmemi ister misin?" diye soruyordu; kullanıcı "devam et" yazınca
    sistemde onu karşılayan hiçbir şey yoktu (canlıda görüldü). Üstelik 9 sonuç
    listelenmişken "devam" neyi kastediyor belli değil.

    Kural: alternatif SONUÇ ÜRETTİYSE zaten kendi yönergesini taşır
    ("1'i bana gönder") — üstüne soru ekleme. Hiçbir şey bulunamadıysa
    kullanıcıdan somut ve yapılabilir tek şeyi iste: tam ad.
    """
    parcalar = [asil_mesaj] if asil_mesaj else []
    if kurtarma.adimlar:
        parcalar.append("\n**Denediklerim:**\n" + "\n".join(kurtarma.adimlar))
    if kurtarma.mesaj:
        parcalar.append("\n" + kurtarma.mesaj)
    elif kurtarma.denendi and not kurtarma.basarili:
        parcalar.append("\n❓ Dosyanın adını tam yazar mısın?")
    return "\n".join(p for p in parcalar if p)
