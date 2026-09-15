# -*- coding: utf-8 -*-
"""
ULTRON PROAKTİF OLAY MOTORU — Yaklaşan takvim etkinliği + mola uyarısı.

Otonom döngüden (`ui/tau_window._autonomous_tick`, 30 sn) çağrılır.

⚠️ MOLA SAYACI GERÇEK HAREKETSİZLİĞE BAKAR.
   İlk sürüm sayacı modül IMPORT anında başlatıyordu: uygulama sabah açıldıysa
   kullanıcı bilgisayarın başında olmasa bile tam 2 saat sonra "2 saattir
   kesintisiz çalışıyorsun" diyordu. Söylediği şey ölçülmüş bir gerçek değil,
   açılıştan beri geçen süreydi. Artık Windows'un `GetLastInputInfo`'su
   okunur: kullanıcı MOLA_ESIGI kadar klavye/fareye dokunmadıysa molayı
   zaten vermiştir, sayaç sıfırlanır.

   Yanlış zamanda gelen sağlık uyarısı zararsız görünür ama asistanı dırdıra
   çevirir — `features/suggestions.py`'deki "reddedilen geri gelmez" kuralıyla
   aynı gerekçe.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from core.paths import veri_dizini

# Etkinlik kaç dakika önce haber verilsin
ETKINLIK_HABER_DK = 15
# Kesintisiz çalışma bu süreyi aşarsa mola önerilir
MOLA_SURESI_SN = 2 * 60 * 60
# Kullanıcı bu kadar süre hiç dokunmadıysa "mola verdi" sayılır
MOLA_ESIGI_SN = 5 * 60
# Uyarılan etkinlik kaydı bu süre sonra unutulur (sonsuz büyümesin)
UYARI_HAFIZA_SN = 6 * 60 * 60

_UYARILAN_ETKINLIKLER: Dict[Any, datetime] = {}
_SON_MOLA_ZAMANI: Optional[datetime] = None


def _db_baglantisi():
    db_yolu = os.path.join(veri_dizini(), "bilgiler.db")
    conn = sqlite3.connect(db_yolu)
    conn.row_factory = sqlite3.Row
    return conn


def bosta_gecen_sure_sn() -> Optional[float]:
    """Kullanıcının klavye/fareye en son dokunmasından bu yana geçen saniye.

    Windows dışında ya da API erişilemezse None döner — o zaman mola uyarısı
    hiç verilmez. Ölçemediğin şey hakkında kesin konuşmak, yanlış konuşmaktır.
    """
    try:
        import ctypes

        class _LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

        bilgi = _LASTINPUTINFO()
        bilgi.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(bilgi)):
            return None
        simdi_ms = ctypes.windll.kernel32.GetTickCount64()
        return max(0.0, (simdi_ms - bilgi.dwTime) / 1000.0)
    except Exception:
        return None


def takvim_yaklasan_etkinlikler(dakika: int = ETKINLIK_HABER_DK) -> List[Dict[str, Any]]:
    """Önümüzdeki `dakika` içinde başlayacak etkinlikler.

    Tüm gün süren etkinlikler DIŞARIDA bırakılır: başlangıçları 00:00'dır,
    "15 dakika kaldı" demek gece yarısı anlamsız bir uyarı üretirdi.
    """
    simdi = datetime.now()
    hedef = simdi + timedelta(minutes=dakika)
    etkinlikler: List[Dict[str, Any]] = []
    conn = None
    try:
        # ⚠️ `with sqlite3.connect(...)` bağlantıyı KAPATMAZ, yalnızca işlemi
        #    yönetir. Bu fonksiyon otonom döngüden 30 sn'de bir çağrılıyor;
        #    kapatılmayan bağlantı günde binlerce dosya tanıtıcısı demektir.
        conn = _db_baglantisi()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, baslik, baslangic, yer, aciklama
            FROM takvim_etkinlikleri
            WHERE baslangic >= ? AND baslangic <= ?
              AND COALESCE(tum_gun, 0) = 0
            ORDER BY baslangic
            """,
            (simdi.strftime('%Y-%m-%d %H:%M:%S'), hedef.strftime('%Y-%m-%d %H:%M:%S')),
        )
        etkinlikler = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[ULTRON Proaktif] Takvim okuma hatasi: {e}")
    finally:
        if conn is not None:
            conn.close()
    return etkinlikler


def _hafizayi_buda(simdi: datetime) -> None:
    eski = [k for k, t in _UYARILAN_ETKINLIKLER.items()
            if (simdi - t).total_seconds() > UYARI_HAFIZA_SN]
    for k in eski:
        _UYARILAN_ETKINLIKLER.pop(k, None)


def _mola_kontrolu(simdi: datetime) -> Optional[str]:
    global _SON_MOLA_ZAMANI

    bosta = bosta_gecen_sure_sn()
    if bosta is None:
        return None                      # ölçemiyorsak uyarı da yok

    if bosta >= MOLA_ESIGI_SN:
        # Kullanıcı zaten ara vermiş; sayaç dönüşünden itibaren yeniden işler.
        _SON_MOLA_ZAMANI = simdi
        return None

    if _SON_MOLA_ZAMANI is None:
        _SON_MOLA_ZAMANI = simdi         # ilk ölçüm: şimdiden saymaya başla
        return None

    if (simdi - _SON_MOLA_ZAMANI).total_seconds() < MOLA_SURESI_SN:
        return None

    _SON_MOLA_ZAMANI = simdi
    return ("🧘 **Mola Zamanı:** 2 saattir ara vermeden çalışıyorsun. "
            "5 dakika gözlerini dinlendirip bir bardak su almayı unutma!")


def proaktif_olaylari_kontrol_et() -> List[str]:
    """Bildirilecek mesajları döner. Hiçbir şey yoksa boş liste."""
    simdi = datetime.now()
    bildirimler: List[str] = []

    _hafizayi_buda(simdi)
    for etk in takvim_yaklasan_etkinlikler():
        etk_id = etk.get("id")
        if etk_id in _UYARILAN_ETKINLIKLER:
            continue
        _UYARILAN_ETKINLIKLER[etk_id] = simdi

        baslik = etk.get("baslik") or "Etkinlik"
        yer = (etk.get("yer") or "").strip()
        kalan = ""
        try:
            bas = datetime.strptime(etk["baslangic"], '%Y-%m-%d %H:%M:%S')
            kalan = f" ({max(1, round((bas - simdi).total_seconds() / 60))} dk kaldı)"
        except Exception:
            pass
        bildirimler.append(
            f"📅 **Yaklaşan Etkinlik{kalan}:** {baslik}" + (f" — {yer}" if yer else "")
        )

    mola = _mola_kontrolu(simdi)
    if mola:
        bildirimler.append(mola)

    return bildirimler


def mola_zamanini_sifirla() -> None:
    global _SON_MOLA_ZAMANI
    _SON_MOLA_ZAMANI = datetime.now()


def _durumu_sifirla() -> None:
    """Yalnızca testler için — modül durumunu temizler."""
    global _SON_MOLA_ZAMANI
    _UYARILAN_ETKINLIKLER.clear()
    _SON_MOLA_ZAMANI = None
