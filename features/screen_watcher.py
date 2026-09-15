"""
Akıllı Ekran Takipçisi (Smart Screen Watcher & Region Trigger).

Ekranda belirli bir metin/kelime/durum belirene (veya kaybolana) kadar
arka planda Windows yerleşik OCR motoru ile periyodik tarama yapmasının yanında
masaüstü pencere başlıklarını da izler.
Hedef tespit edildiğinde sesli duyuru, sistem toast bildirimi ve Telegram bildirimi tetikler.
"""

import threading
import time
import re
from typing import Optional, Dict, Any

_TAKIP_THREAD: Optional['ScreenWatcherThread'] = None
_TAKIP_LOCK = threading.Lock()


def _ultron_pencereleri():
    """Ultron'un kendi görünür pencerelerinin (sol, üst, sağ, alt) dikdörtgenleri."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        dikdortgenler = []

        def enum_cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if 'ultron' in (buf.value or '').lower():
                r = wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                    dikdortgenler.append((r.left, r.top, r.right, r.bottom))
            return True

        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(CMPFUNC(enum_cb), 0)
        return dikdortgenler
    except Exception:
        return []


def _pencere_basliklari():
    """Görünür pencere başlıkları — Ultron'un kendi pencereleri HARİÇ."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        titles = []

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    baslik = buf.value or ''
                    if 'ultron' not in baslik.lower():
                        titles.append(baslik)
            return True

        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(CMPFUNC(enum_cb), 0)
        return titles
    except Exception:
        return []


class ScreenWatcherThread(threading.Thread):
    """
    ⚠️ İKİ KORUMA — ikisi de kendi kendini tetiklemeye karşı:

    1. **Ultron'un kendi penceresi sayılmaz.** Kullanıcının komutu ("ekranda
       Claude açılınca haber ver") ve Ultron'un cevabı ekranda YAZILI durur;
       tam ekran OCR bunu okuyup ilk taramada alarm veriyordu. Eşleşmenin
       koordinatı Ultron penceresinin içindeyse yok sayılır.
    2. **Alarm GEÇİŞTE verilir**, durumda değil. İlk tarama "temel çekim"dir;
       hedef zaten ekrandaysa alarm çalmaz, kaybolup tekrar belirmesi beklenir.
    """

    def __init__(self, hedef_metin: str, kanal: str = "desktop", interval: float = 3.0,
                 mod: str = "belirdi"):
        super().__init__(daemon=True)
        self.hedef_metin = hedef_metin.strip()
        self.kanal = kanal
        self.interval = interval
        self.mod = mod  # "belirdi" veya "kayboldu"
        self._durdur_event = threading.Event()
        self.tespit_edildi = False
        self.tespit_zamanı = 0.0
        self.son_ekran_basligi = ""
        self.baslangicta_vardi: Optional[bool] = None

    def durdur(self):
        self._durdur_event.set()

    def _hedef_ekranda_mi(self):
        """(bulundu_mu, kaynak_başlığı) — Ultron'un kendi penceresi hariç."""
        from features import screen_reader

        sonuc = screen_reader.ekrani_oku(tum_ekran=True)
        if sonuc.get("ok"):
            bulunanlar = screen_reader.metni_bul(self.hedef_metin, sonuc=sonuc, tum_ekran=True)
            if bulunanlar:
                ultron_alanlari = _ultron_pencereleri()

                def _ultron_icinde(b):
                    cx, cy = b.get("merkez", (b.get("x", 0), b.get("y", 0)))
                    return any(l <= cx <= r and t <= cy <= alt
                               for (l, t, r, alt) in ultron_alanlari)

                dis_bulunanlar = [b for b in bulunanlar if not _ultron_icinde(b)]
                if dis_bulunanlar:
                    return True, (sonuc.get("baslik") or "Tüm Ekran")

        for wt in _pencere_basliklari():
            if self.hedef_metin.lower() in wt.lower():
                return True, wt

        return False, "Tüm Ekran"

    def run(self):
        print(f"[ULTRON ScreenWatcher] Ekran takibi başlatıldı: '{self.hedef_metin}' ({self.mod})")
        onceki_var = None

        while not self._durdur_event.is_set():
            try:
                var_mi, sonuc_baslik = self._hedef_ekranda_mi()
                self.son_ekran_basligi = sonuc_baslik

                if onceki_var is None:
                    # Temel çekim: mevcut durum alarm sayılmaz.
                    onceki_var = var_mi
                    self.baslangicta_vardi = var_mi
                    if var_mi:
                        print(f"[ULTRON ScreenWatcher] '{self.hedef_metin}' zaten ekranda; "
                              f"değişim bekleniyor.")
                else:
                    beliren = var_mi and not onceki_var
                    kaybolan = onceki_var and not var_mi
                    onceki_var = var_mi
                    if (self.mod == "belirdi" and beliren) or (self.mod == "kayboldu" and kaybolan):
                        self.tespit_edildi = True
                        self.tespit_zamanı = time.time()
                        self._bildirim_gonder({}, [])
                        break
            except Exception as e:
                print(f"[ULTRON ScreenWatcher] Tarama hatası: {e}")

            if self._durdur_event.wait(self.interval):
                break

    def _bildirim_gonder(self, ocr_sonuc: dict, bulunanlar: list):
        mesaj = (f"👁️ **[EKRAN TAKİP UYARISI]**\n"
                 f"• Hedef: `{self.hedef_metin}` ekranda {self.mod}!\n"
                 f"• Kaynak: **{self.son_ekran_basligi}**")
        
        print(f"[ULTRON ScreenWatcher] {mesaj}")

        # 1. Sesli bildirim
        try:
            from features.speech import seslendir
            threading.Thread(target=seslendir, args=(f"Ekranda {self.hedef_metin} {self.mod}!",), daemon=True).start()
        except Exception as e:
            print(f"[ULTRON ScreenWatcher] Sesli bildirim hatası: {e}")

        # 2. Telegram bildirimi (varsa)
        try:
            from features import telegram_bridge
            telegram_bridge.telegram_mesaj_gonder(mesaj)
        except Exception:
            pass


def takip_baslat(hedef_metin: str, kanal: str = "desktop", interval: float = 3.0, mod: str = "belirdi") -> str:
    """Ekranda hedef metni arka planda takip etmeye başlar."""
    global _TAKIP_THREAD
    with _TAKIP_LOCK:
        if _TAKIP_THREAD and _TAKIP_THREAD.is_alive():
            _TAKIP_THREAD.durdur()
            _TAKIP_THREAD.join(timeout=1.0)
        
        _TAKIP_THREAD = ScreenWatcherThread(hedef_metin=hedef_metin, kanal=kanal, interval=interval, mod=mod)
        _TAKIP_THREAD.start()
        return f"👁️ **Ekran Takibi Başlatıldı:** Ekranda `{hedef_metin}` {mod} zaman haber verilecek."


def takip_durdur() -> str:
    """Aktif ekran takibini sonlandırır."""
    global _TAKIP_THREAD
    with _TAKIP_LOCK:
        if _TAKIP_THREAD and _TAKIP_THREAD.is_alive():
            hedef = _TAKIP_THREAD.hedef_metin
            _TAKIP_THREAD.durdur()
            _TAKIP_THREAD = None
            return f"🛑 **Ekran Takibi Durduruldu:** `{hedef}` takibi sonlandırıldı."
        return "ℹ️ Aktif bir ekran takibi bulunmuyor."


def takip_durumu() -> str:
    """Ekran takibi durumunu döner."""
    with _TAKIP_LOCK:
        if _TAKIP_THREAD and _TAKIP_THREAD.is_alive():
            return (f"👁️ **Ekran Takibi Aktif:**\n"
                    f"• Hedef: `{_TAKIP_THREAD.hedef_metin}`\n"
                    f"• Durum: Taranıyor ({_TAKIP_THREAD.interval} sn aralıkla)")
        return "ℹ️ Aktif bir ekran takibi bulunmuyor."


def ekran_takip_niyeti_algila(mesaj: str) -> bool:
    """Mesaj bir ekran takip komutu mu?"""
    m = (mesaj or "").lower().strip()
    if 'ekran' not in m and 'takip' not in m and 'haber ver' not in m and 'uyar' not in m:
        return False
    kalıplar = [
        r'ekranda?\s+.+\s+(çıkınca|görünce|belirince|olunca|yazınca|açılınca|başlayınca|görününce|gelince|varsa|olursa)\s*(?:haber\s+ver|uyar|bildir)?',
        r'ekranda?\s+.+\s+(kaybolunca|silinince|kapanınca)\s*(?:haber\s+ver|uyar|bildir)?',
        r'ekran\s+takibini?\s+(başlat|başlatır|durdu|durdur|kapat|durumu)',
        r'ekranda?\s+.+\s+takip\s+et',
    ]
    return any(re.search(k, m, re.IGNORECASE) for k in kalıplar)


def ekran_takip_komutu_isle(mesaj: str) -> Optional[Dict[str, Any]]:
    """Komutu ayrıştırır ve ilgili fonksiyonu tetikler."""
    if not ekran_takip_niyeti_algila(mesaj):
        return None
        
    m = (mesaj or "").strip()
    
    # Durdur / Kapat
    if re.search(r'takibini?\s+(durdur|kapat|iptal)', m, re.IGNORECASE):
        return {"tip": "direct", "sonuc": takip_durdur()}
        
    # Durum
    if re.search(r'takib?i?\s+durum', m, re.IGNORECASE):
        return {"tip": "direct", "sonuc": takip_durumu()}
        
    # Başlat: "ekranda Notepad çıkınca haber ver" / "ekranda Claude açılınca uyar"
    eslesme = re.search(r'ekranda?\s+["\'`]?(.+?)["\'`]?\s+(?:çıkınca|görünce|belirince|olunca|yazınca|açılınca|başlayınca|görününce|gelince|varsa|olursa|takip\s+et)\s*(?:haber\s+ver|uyar|bildir)?', m, re.IGNORECASE)
    if eslesme:
        hedef = eslesme.group(1).strip()
        mod = "kayboldu" if any(k in m.lower() for k in ["kaybol", "kapan", "silin"]) else "belirdi"
        return {"tip": "direct", "sonuc": takip_baslat(hedef_metin=hedef, mod=mod)}
        
    return {"tip": "direct", "sonuc": "👁️ Ekran takibi için hedef metin anlaşılamadı. Örnek: `ekranda İndirme Bitti çıkınca haber ver`"}
