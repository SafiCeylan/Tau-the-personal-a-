# -*- coding: utf-8 -*-
"""
ULTRON — TAKMA ADLAR (Faz 3: Memory)

Kullanıcının notundan:

    > "Patronuma gönder."
    Ultron'un şunu bilmesi gerekir:  Patron → Ahmet Kaya → WhatsApp

═══════════════════════════════════════════════════════════════════════
BU MODÜL NEDEN TEMKİNLİ YAZILDI
═══════════════════════════════════════════════════════════════════════

Yanlış takma ad çözümü = **yanlış kişiye mesaj/dosya gitmesi**. Geri alınamaz.
Bu yüzden burada "akıllı" olmaya çalışmıyoruz; öngörülebilir olmaya çalışıyoruz.

Dört kural:

1. SADECE AÇIK ÖĞRETİM. Takma ad yalnızca kullanıcı BUNU KASTEDEREK söylediğinde
   kaydedilir ("patronum Ahmet Kaya demek"). Sohbetten çıkarım YAPILMAZ.
   "Bugün patronla tartıştım, Ahmet çok sinirliydi" cümlesinden patron=Ahmet
   sonucu çıkarmak, bir gün yanlış kişiye zam talebi göndermek demektir.

2. BULANIK EŞLEŞME YOK. Tam eşleşme + Türkçe yönelme eki toleransı, o kadar.
   Dosya adında bulanık eşleşme yanlış dosya gösterir (rahatsız edici);
   KİŞİDE bulanık eşleşme yanlış insana mesaj gönderir (telafisi yok).

3. REHBER TAKMA ADDAN ÖNCE GELİR. Rehberde doğrudan "annem" varsa o kullanılır;
   takma ad yalnızca doğrudan eşleşme YOKSA denenir. Doğrudan kayıt daha
   açık bir niyettir.

4. ÇÖZÜM HER ZAMAN GÖRÜNÜR. `kimlik_zinciri()` onay kartına "patronum →
   Ahmet Kaya" satırını koyar. Kullanıcı KİMİN kastedildiğini onaylamadan
   önce görmelidir.

Takma adlar `memory` tablosunda `Takma Ad` kategorisinde tutulur — böylece
mevcut hafıza ekranında görünür, kullanıcı yanlış olanı silebilir.
"""

import re
from typing import Dict, Optional

ANAHTAR_ONEKI = "takma_ad:"
KATEGORI = "Takma Ad"

# Türkçe yönelme ekleri — "patronuma" → "patronum" (kisi_coz ile aynı tolerans)
_EKLER = ('ye', 'ya', 'e', 'a', 'na', 'ne')

# Takma ad olamayacak kelimeler: bunlar kişi değil, komut parçası.
# ("bana gönder" cümlesindeki "bana" takma ad sanılmamalı.)
_YASAK_ADLAR = {
    'bana', 'sana', 'ona', 'bize', 'size', 'onlara', 'kendime', 'kendine',
    'telegram', 'whatsapp', 'mail', 'eposta', 'e-posta', 'birine', 'birisine',
}

# Açık öğretim kalıpları. Hepsi kullanıcının BUNU KASTETMESİNİ gerektirir.
_OGRETIM_KALIPLARI = (
    # "patronum Ahmet Kaya demek"
    re.compile(r'^\s*(?P<ad>[\wçğıöşüÇĞİÖŞÜ\s]{2,30}?)\s+(?P<kisi>[\wçğıöşüÇĞİÖŞÜ\s\.\+@-]{2,60}?)\s+demek\s*\.?\s*$',
               re.IGNORECASE),
    # "patronum = Ahmet Kaya"
    re.compile(r'^\s*(?P<ad>[\wçğıöşüÇĞİÖŞÜ\s]{2,30}?)\s*=\s*(?P<kisi>.{2,60}?)\s*$'),
    # "patronum aslında Ahmet Kaya"
    re.compile(r'^\s*(?P<ad>[\wçğıöşüÇĞİÖŞÜ\s]{2,30}?)\s+aslında\s+(?P<kisi>.{2,60}?)\s*\.?\s*$',
               re.IGNORECASE),
    # "patronum Ahmet Kaya'dır"
    re.compile(r'^\s*(?P<ad>[\wçğıöşüÇĞİÖŞÜ\s]{2,30}?)\s+(?P<kisi>[\wçğıöşüÇĞİÖŞÜ\s\.]{2,60}?)[\'’]?d[ıi]r\s*\.?\s*$',
               re.IGNORECASE),
)


def _sadelestir(ad: str) -> str:
    return (ad or '').strip().lower().strip('.,!?')


def _ek_at(ad: str) -> str:
    """'patronuma' → 'patronum'. Yalnızca bilinen yönelme ekleri atılır."""
    for ek in sorted(_EKLER, key=len, reverse=True):
        if ad.endswith(ek) and len(ad) - len(ek) >= 3:
            return ad[:-len(ek)]
    return ad


# =========================================================================
# Yazma
# =========================================================================
def takma_ad_kaydet(cursor, conn, takma_ad: str, gercek_kisi: str) -> bool:
    """Takma adı hafızaya yazar. Doğrudan çağrı için (öğretim kalıbı gerekmez)."""
    ad = _sadelestir(takma_ad)
    kisi = (gercek_kisi or '').strip()
    if not ad or not kisi or ad in _YASAK_ADLAR:
        return False
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO memory (key, value, category) VALUES (?, ?, ?)",
            (f"{ANAHTAR_ONEKI}{ad}", kisi, KATEGORI))
        conn.commit()
        return True
    except Exception as e:
        print(f"[Ultron TakmaAd] Kaydedilemedi: {e}")
        return False


def takma_ad_ogren(mesaj: str, cursor, conn) -> Optional[str]:
    """
    Cümlede AÇIK bir takma ad öğretimi varsa kaydeder → onay metni veya None.

    ⚠️ Buraya yeni ve gevşek bir kalıp eklemek, sıradan sohbet cümlelerinin
    takma ad sanılmasına yol açar. Kalıp eklerken "kullanıcı bunu kasten mi
    söyledi?" sorusunu geçmesi gerekir.
    """
    if cursor is None or conn is None or not mesaj:
        return None

    for kalip in _OGRETIM_KALIPLARI:
        eslesme = kalip.match(mesaj.strip())
        if not eslesme:
            continue
        ad = _sadelestir(eslesme.group('ad'))
        kisi = eslesme.group('kisi').strip().strip('.,!?')
        if not ad or not kisi or ad in _YASAK_ADLAR:
            continue
        # Kendini işaret eden kayıt anlamsız ("ahmet = ahmet")
        if _sadelestir(kisi) == ad:
            continue
        if takma_ad_kaydet(cursor, conn, ad, kisi):
            return f"🧠 **Not aldım:** `{ad}` dediğinde **{kisi}** anlıyorum."
    return None


def takma_ad_sil(cursor, conn, takma_ad: str) -> bool:
    ad = _sadelestir(takma_ad)
    try:
        cursor.execute("DELETE FROM memory WHERE key = ?", (f"{ANAHTAR_ONEKI}{ad}",))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[Ultron TakmaAd] Silinemedi: {e}")
        return False


# =========================================================================
# Okuma
# =========================================================================
def takma_adlari_getir(cursor=None) -> Dict[str, str]:
    """
    Tüm takma adlar → {'patronum': 'Ahmet Kaya'}.

    `cursor` verilmezse kendi bağlantısını açar. Sebep: takma ad çözümü
    `kisi_coz` gibi derinlerde, cursor'ın olmadığı yerlerde gerekiyor ve
    cursor'ı bütün katmanlardan geçirmek boru hattını kirletirdi.
    (Proje kuralı: SQLite thread'ler arası paylaşılamaz, her çağrı kendi
    bağlantısını açar.)
    """
    if cursor is not None:
        try:
            satirlar = cursor.execute(
                "SELECT key, value FROM memory WHERE key LIKE ?",
                (f"{ANAHTAR_ONEKI}%",)).fetchall()
        except Exception as e:
            print(f"[Ultron TakmaAd] Okunamadı: {e}")
            return {}
        return {k[len(ANAHTAR_ONEKI):]: v for k, v in satirlar}

    try:
        import sqlite3
        from core.paths import veri_yolu
        conn = sqlite3.connect(veri_yolu('bilgiler.db'), timeout=5)
        try:
            satirlar = conn.execute(
                "SELECT key, value FROM memory WHERE key LIKE ?",
                (f"{ANAHTAR_ONEKI}%",)).fetchall()
        finally:
            conn.close()
    except Exception as e:
        print(f"[Ultron TakmaAd] Bağlantı açılamadı: {e}")
        return {}
    return {k[len(ANAHTAR_ONEKI):]: v for k, v in satirlar}


def takma_adi_coz(ad: str, cursor=None) -> Optional[str]:
    """
    Takma adı gerçek kişiye çevirir → 'Ahmet Kaya' veya None.

    ⚠️ BULANIK EŞLEŞME YOK. Tam eşleşme, sonra Türkçe yönelme eki atılmış hâli.
    Başka hiçbir şey denenmez: yanlış kişiye mesaj göndermenin telafisi yoktur.
    """
    anahtar = _sadelestir(ad)
    if not anahtar or anahtar in _YASAK_ADLAR:
        return None

    takma_adlar = takma_adlari_getir(cursor)
    if not takma_adlar:
        return None

    if anahtar in takma_adlar:
        return takma_adlar[anahtar]

    eksiz = _ek_at(anahtar)
    if eksiz != anahtar and eksiz in takma_adlar:
        return takma_adlar[eksiz]

    return None


def kimlik_zinciri(alici: str, cursor=None) -> str:
    """
    Onay kartında gösterilecek kimlik ifadesi.

        "patronuma"  →  "patronuma → **Ahmet Kaya**"
        "annem"      →  "annem"                (takma ad yok, olduğu gibi)

    ⚠️ Bu satır güvenlik özelliğidir, süs değil. Kullanıcı "patronuma gönder"
    dediğinde ONAYLAMADAN ÖNCE kimin kastedildiğini görmelidir; yoksa yanlış
    kişiye gönderim ancak iş işten geçtikten sonra fark edilir.
    """
    gercek = takma_adi_coz(alici, cursor)
    if gercek:
        return f"{alici} → **{gercek}**"
    return str(alici or '')
