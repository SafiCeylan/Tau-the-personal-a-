# -*- coding: utf-8 -*-
"""
ULTRON — WORLD STATE (Faz 6)

Kullanıcının notundan:

    Ultron sürekli bilir ki: Chrome açık · VS Code açık · Spotify çalıyor ·
    İnternet var · Pil %35
    Böylece gereksiz işlem yapmaz.
        > Spotify aç
        > Zaten açık.

═══════════════════════════════════════════════════════════════════════
TASARIM KURALI: ŞÜPHEDEYSEN İŞİ YAP (fail open)
═══════════════════════════════════════════════════════════════════════

"Zaten açık" demek, kullanıcının komutunu SESSİZCE İPTAL ETMEKTİR. Yanlış
tespit edersek kullanıcı "Spotify aç" der, Ultron "zaten açık" der ve hiçbir
şey olmaz — kullanıcı Ultron'un bozulduğunu düşünür.

Bu yüzden:
  • Durum tespiti YALNIZCA mesajı zenginleştirir; komutu iptal ETMEZ.
    Uygulama zaten açıksa bile başlatıcı yine çağrılır (Windows'ta bu
    mevcut pencereyi öne getirir) — sadece kullanıcıya doğrusu söylenir.
  • Süreç eşleşmesi TEMKİNLİ: kısa/belirsiz adlar eşleştirilmez.
    "not" kelimesi notepad'i eşleştirmemeli.

Önbellek: `psutil.process_iter` ucuz değil. Tek bir komut içinde birkaç kez
sorulabildiği için kısa ömürlü (birkaç saniye) önbellek tutulur.
"""

import time
from typing import Dict, Optional, Set

try:
    import psutil
except ImportError:                                   # pragma: no cover
    psutil = None

# Süreç listesi bu kadar saniye taze sayılır. Kısa: kullanıcı uygulamayı
# kapatıp hemen sorabilir.
ONBELLEK_OMRU_SN = 3.0

# Bu uzunluğun altındaki adlarla süreç eşleştirilmez — "not", "cmd", "vs"
# gibi parçalar yanlış eşleşir.
MIN_AD_UZUNLUGU = 4

_onbellek: Dict[str, object] = {'zaman': 0.0, 'surecler': set()}


def _surec_adlari(taze: bool = False) -> Set[str]:
    """Çalışan süreçlerin adları (küçük harf, uzantısız)."""
    if psutil is None:
        return set()

    simdi = time.time()
    if not taze and simdi - float(_onbellek['zaman']) < ONBELLEK_OMRU_SN:
        return _onbellek['surecler']            # type: ignore[return-value]

    adlar = set()
    try:
        for surec in psutil.process_iter(['name']):
            ad = (surec.info.get('name') or '').lower()
            if not ad:
                continue
            adlar.add(ad)
            if ad.endswith('.exe'):
                adlar.add(ad[:-4])
    except Exception as e:
        print(f"[Ultron WorldState] Süreçler okunamadı: {e}")
        return _onbellek['surecler']            # type: ignore[return-value]

    _onbellek['zaman'] = simdi
    _onbellek['surecler'] = adlar
    return adlar


def onbellegi_temizle():
    _onbellek['zaman'] = 0.0
    _onbellek['surecler'] = set()


def uygulama_calisiyor_mu(ad: str) -> bool:
    """
    Bu uygulama şu an açık mı?

    ⚠️ TEMKİNLİ EŞLEŞME. Yanlış "evet" cevabı kullanıcının komutunu iptal
    ettirebilir, o yüzden emin olmadığımızda False deriz:
      • 4 harften kısa adlar eşleştirilmez
      • Kısmi eşleşme yalnızca süreç adı, aranan adla BAŞLIYORSA kabul edilir
        ("spotify" → "spotify.exe" ✓, ama "not" → "notepad" ✗)
    """
    hedef = (ad or '').lower().strip()
    if len(hedef) < MIN_AD_UZUNLUGU:
        return False

    surecler = _surec_adlari()
    if hedef in surecler:
        return True
    return any(s.startswith(hedef) for s in surecler)


def pil_durumu() -> Optional[dict]:
    """→ {'yuzde': 35, 'sarjda': False} veya None (masaüstü / okunamadı)."""
    if psutil is None:
        return None
    try:
        pil = psutil.sensors_battery()
    except Exception:
        return None
    if pil is None:
        return None
    return {'yuzde': int(pil.percent), 'sarjda': bool(pil.power_plugged)}


def internet_var_mi(zaman_asimi: float = 2.0) -> bool:
    """
    Hızlı bağlantı kontrolü — ALAN ADI üzerinden.

    ⚠️ Önce "DNS'e güvenme, doğrudan 8.8.8.8:53'e bağlan" diye yazılmıştı ve
    bu makinede YANLIŞ sonuç verdi: ağ doğrudan IP bağlantılarını engelliyor
    (8.8.8.8, 1.1.1.1 — hepsi zaman aşımı), alan adı üzerinden ise 0.05 sn'de
    geçiyor. İnternet varken "YOK" demek, olmadığını söylemekten daha kötü:
    Ultron çalışan araçları denemekten vazgeçebilir.

    Bu yüzden gerçek trafiğin gittiği yolu taklit ediyoruz — alan adı çözümü
    dahil. Yavaşlığı önemli değil, sonuç doğru olsun.
    """
    import socket
    for adres in (('www.google.com', 443), ('cloudflare.com', 443)):
        try:
            with socket.create_connection(adres, timeout=zaman_asimi):
                return True
        except OSError:
            continue
    return False


def durum_ozeti(uygulamalar=('chrome', 'spotify', 'code', 'whatsapp')) -> str:
    """Kullanıcıya gösterilebilir kısa dünya durumu."""
    satirlar = []

    acik = [u for u in uygulamalar if uygulama_calisiyor_mu(u)]
    satirlar.append("🖥️ Açık: " + (", ".join(a.title() for a in acik) if acik
                                   else "izlenen uygulama yok"))

    pil = pil_durumu()
    if pil:
        simge = "🔌" if pil['sarjda'] else "🔋"
        satirlar.append(f"{simge} Pil: %{pil['yuzde']}"
                        + (" (şarjda)" if pil['sarjda'] else ""))

    satirlar.append("🌐 İnternet: " + ("var" if internet_var_mi() else "YOK"))
    return "\n".join(satirlar)
