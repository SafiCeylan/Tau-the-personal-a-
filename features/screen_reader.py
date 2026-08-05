"""
Ekran Okuma (OCR) — "ekranda ne yazıyor", "şu hatayı oku ve açıkla".

Windows'un YERLEŞİK OCR motorunu kullanır (`Windows.Media.Ocr`):
model indirmesi yok, internet yok, motor RAM maliyeti ~3 MB.
Bu makinede ölçüldü (1920x1080): görüntü 41ms + dönüşüm 33ms + OCR 108ms ≈ 0.2 sn.

⚠️ VARSAYILAN TÜM EKRAN DEĞİL. Kullanıcı "ekranda ne yazıyor" derken kendi
Ultron penceresini kastetmiyor — o an baktığı pencereyi kastediyor. Bu yüzden
Z-sırasında ULTRON'UN ARKASINDAKİ ilk gerçek pencere okunur. Tüm ekran istenirse
komutta açıkça belirtilmeli ("tüm ekranı oku").

Thread-safe: Qt worker thread'inden çağrılabilir — kendi event loop'unu kurar,
Qt gerektirmez, Telegram worker'ından da güvenle çağrılır.
"""

import asyncio
import ctypes
import os
import re
from ctypes import wintypes

# Motor bir kez kurulur, sonraki çağrılarda yeniden kurulmaz.
_MOTOR = None
_MOTOR_DENENDI = False

# OCR motorunun kabul ettiği en küçük görüntü (bundan küçük pencere okunmaz)
_MIN_KENAR = 40


def ocr_hazir():
    """(kullanilabilir_mi, aciklama) döner. Kurulum eksikse nedenini söyler."""
    try:
        from winsdk.windows.media.ocr import OcrEngine  # noqa: F401
    except ImportError:
        return False, ("⚠️ Ekran okuma için `winsdk` gerekli: `pip install winsdk`\n"
                       "(Windows'un kendi OCR motorunu kullanır, ek model indirmez.)")
    try:
        import mss  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False, "⚠️ Ekran okuma için `mss` ve `Pillow` gerekli."

    if _ocr_motoru() is None:
        return False, ("⚠️ Windows'ta kurulu OCR dili bulunamadı.\n"
                       "Ayarlar → Saat ve Dil → Dil → (dil) → Seçenekler → "
                       "İsteğe bağlı özellikler → **El yazısı / OCR** ekle.")
    return True, "Ekran okuma hazır."


def _ocr_motoru():
    """Türkçe motoru dener, yoksa kullanıcı profili dillerine düşer. Sonucu önbelleğe alır."""
    global _MOTOR, _MOTOR_DENENDI
    if _MOTOR_DENENDI:
        return _MOTOR
    _MOTOR_DENENDI = True
    try:
        from winsdk.windows.globalization import Language
        from winsdk.windows.media.ocr import OcrEngine
        _MOTOR = OcrEngine.try_create_from_language(Language("tr"))
        if _MOTOR is None:
            _MOTOR = OcrEngine.try_create_from_user_profile_languages()
        if _MOTOR is None:
            diller = list(OcrEngine.available_recognizer_languages)
            if diller:
                _MOTOR = OcrEngine.try_create_from_language(diller[0])
    except Exception as e:
        print(f"[ULTRON] OCR motoru kurulamadı: {e}")
        _MOTOR = None
    return _MOTOR


# ----------------------------------------------------------------------------
# Hangi pencere okunacak?
# ----------------------------------------------------------------------------
def _pencere_dikdortgeni(hwnd):
    """Gölge/kenarlık payı olmayan gerçek pencere sınırı (DWM), yoksa klasik rect."""
    r = wintypes.RECT()
    try:
        # DWMWA_EXTENDED_FRAME_BOUNDS = 9
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(
                wintypes.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r)) == 0:
            return r
    except Exception:
        pass
    ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r))
    return r


def _gizli_mi(hwnd):
    """UWP'nin askıya alınmış hayalet pencereleri görünür sanılır — DWM'e sor."""
    try:
        gizli = ctypes.c_int(0)
        # DWMWA_CLOAKED = 14
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), 14, ctypes.byref(gizli), ctypes.sizeof(gizli))
        return gizli.value != 0
    except Exception:
        return False


def _pencere_basligi(hwnd):
    n = ctypes.windll.user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if n <= 0:
        return ""
    tampon = ctypes.create_unicode_buffer(n + 1)
    ctypes.windll.user32.GetWindowTextW(wintypes.HWND(hwnd), tampon, n + 1)
    return tampon.value


def okunacak_pencere(kendi_pid=None):
    """Ultron'un ARKASINDAKİ ilk gerçek pencere: (bolge, baslik) veya (None, "").

    Z-sırasında yukarıdan aşağı tarar; görünmez, simge durumunda, başlıksız,
    hayalet (cloaked) ve KENDİ sürecimize ait pencereleri atlar.
    """
    kendi_pid = kendi_pid if kendi_pid is not None else os.getpid()
    user32 = ctypes.windll.user32
    bulunan = {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _her_pencere(hwnd, _lparam):
        if bulunan:
            return False
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if _gizli_mi(hwnd):
            return True
        baslik = _pencere_basligi(hwnd)
        if not baslik or baslik == "Program Manager":
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == kendi_pid:
            return True          # kendi penceremizi okumanın anlamı yok

        r = _pencere_dikdortgeni(hwnd)
        g, y = r.right - r.left, r.bottom - r.top
        if g < _MIN_KENAR or y < _MIN_KENAR:
            return True

        bulunan['bolge'] = {"left": r.left, "top": r.top, "width": g, "height": y}
        bulunan['baslik'] = baslik
        return False

    try:
        user32.EnumWindows(_her_pencere, 0)
    except Exception as e:
        print(f"[ULTRON] Pencere taraması başarısız: {e}")

    return bulunan.get('bolge'), bulunan.get('baslik', "")


def _bolgeyi_kirp(bolge):
    """Ekran dışına taşan koordinatları sanal masaüstü sınırına çeker."""
    user32 = ctypes.windll.user32
    sanal = {
        "left": user32.GetSystemMetrics(76),    # SM_XVIRTUALSCREEN
        "top": user32.GetSystemMetrics(77),     # SM_YVIRTUALSCREEN
        "width": user32.GetSystemMetrics(78),   # SM_CXVIRTUALSCREEN
        "height": user32.GetSystemMetrics(79),  # SM_CYVIRTUALSCREEN
    }
    sol = max(bolge["left"], sanal["left"])
    ust = max(bolge["top"], sanal["top"])
    sag = min(bolge["left"] + bolge["width"], sanal["left"] + sanal["width"])
    alt = min(bolge["top"] + bolge["height"], sanal["top"] + sanal["height"])
    return {"left": sol, "top": ust, "width": max(0, sag - sol), "height": max(0, alt - ust)}


# ----------------------------------------------------------------------------
# OCR
# ----------------------------------------------------------------------------
def _pil_to_bitmap(img):
    from winsdk.windows.graphics.imaging import (BitmapAlphaMode, BitmapPixelFormat,
                                                 SoftwareBitmap)
    from winsdk.windows.storage.streams import DataWriter

    img = img.convert("RGBA")
    yazici = DataWriter()
    yazici.write_bytes(img.tobytes("raw", "BGRA"))
    return SoftwareBitmap.create_copy_from_buffer(
        yazici.detach_buffer(), BitmapPixelFormat.BGRA8,
        img.width, img.height, BitmapAlphaMode.PREMULTIPLIED)


def _ocr_calistir(img, ofset=(0, 0)):
    """PIL görüntüsünü OCR'dan geçirir. Testler bu fonksiyonu taklitler.

    Dönen: {"metin": str, "satirlar": [str], "kelimeler": [{metin,x,y,w,h}]}
    Koordinatlar `ofset` ile EKRAN koordinatına çevrilir (tıklamak için şart).
    """
    motor = _ocr_motoru()
    if motor is None:
        # Anahtarların tamamı dönmeli — çağıranlar 'satir_kutulari'na bakıyor.
        return {"metin": "", "satirlar": [], "satir_kutulari": [], "kelimeler": []}

    bitmap = _pil_to_bitmap(img)

    async def _calis():
        return await motor.recognize_async(bitmap)

    dongu = asyncio.new_event_loop()
    try:
        sonuc = dongu.run_until_complete(_calis())
    finally:
        dongu.close()

    ox, oy = ofset
    satirlar, satir_kutulari, kelimeler = [], [], []
    for satir in sonuc.lines:
        satirlar.append(satir.text)
        satir_kelimeleri = []
        for k in satir.words:
            b = k.bounding_rect
            kayit = {
                "metin": k.text,
                "x": int(b.x) + ox, "y": int(b.y) + oy,
                "w": int(b.width), "h": int(b.height),
            }
            kelimeler.append(kayit)
            satir_kelimeleri.append(kayit)
        # Satır kutusu = kelimelerinin birleşimi. Öğe gruplaması buna dayanır:
        # ekranı "kelime çöplüğü" yerine anlamlı bloklara ayırmak için şart.
        if satir_kelimeleri:
            sol = min(k["x"] for k in satir_kelimeleri)
            ust = min(k["y"] for k in satir_kelimeleri)
            sag = max(k["x"] + k["w"] for k in satir_kelimeleri)
            alt = max(k["y"] + k["h"] for k in satir_kelimeleri)
            satir_kutulari.append({
                "metin": satir.text, "x": sol, "y": ust,
                "w": sag - sol, "h": alt - ust,
            })
    return {"metin": "\n".join(satirlar), "satirlar": satirlar,
            "satir_kutulari": satir_kutulari, "kelimeler": kelimeler}


def ekrani_oku(tum_ekran=False):
    """Pencereyi (veya tüm ekranı) okur.

    Dönen: {"ok": bool, "metin": str, "satirlar": [...], "kelimeler": [...],
            "baslik": str, "hata": str}
    """
    hazir, neden = ocr_hazir()
    if not hazir:
        return {"ok": False, "metin": "", "satirlar": [], "kelimeler": [],
                "baslik": "", "hata": neden}

    import mss
    from PIL import Image

    baslik = ""
    if tum_ekran:
        bolge = None
    else:
        bolge, baslik = okunacak_pencere()
        if bolge:
            bolge = _bolgeyi_kirp(bolge)
        if not bolge or bolge["width"] < _MIN_KENAR or bolge["height"] < _MIN_KENAR:
            bolge = None          # uygun pencere yok → tüm ekrana düş

    try:
        with mss.mss() as sct:
            hedef = bolge or sct.monitors[1]
            ham = sct.grab(hedef)
            img = Image.frombytes("RGB", ham.size, ham.rgb)
            ofset = (hedef["left"], hedef["top"])
    except Exception as e:
        return {"ok": False, "metin": "", "satirlar": [], "kelimeler": [],
                "baslik": baslik, "hata": f"⚠️ Ekran yakalanamadı: {e}"}

    try:
        sonuc = _ocr_calistir(img, ofset)
    except Exception as e:
        return {"ok": False, "metin": "", "satirlar": [], "kelimeler": [],
                "baslik": baslik, "hata": f"⚠️ OCR başarısız: {e}"}

    # `bolge` AIP seviye 3 için şart: tıklamadan hemen önce pencerenin kayıp
    # kaymadığı bu dikdörtgenle karşılaştırılarak anlaşılır.
    sonuc.update({"ok": True, "baslik": "" if tum_ekran else baslik,
                  "bolge": dict(hedef), "hata": ""})
    return sonuc


# ----------------------------------------------------------------------------
# Metin arama (AIP seviye 3'ün temeli: metni bul → koordinatını al → tıkla)
# ----------------------------------------------------------------------------
_KATLAMA = str.maketrans({
    'İ': 'i', 'I': 'i', 'ı': 'i', 'i': 'i',
    'Ş': 's', 'ş': 's', 'Ğ': 'g', 'ğ': 'g', 'Ç': 'c', 'ç': 'c',
    'Ü': 'u', 'ü': 'u', 'Ö': 'o', 'ö': 'o',
    'Â': 'a', 'â': 'a', 'Î': 'i', 'î': 'i', 'Û': 'u', 'û': 'u',
})


def _katla(metin):
    """Eşleştirme için Türkçe-güvenli katlama.

    ⚠️ Bu fonksiyon olmadan Türkçe arayüzlerin EN YAYGIN düğmeleri hiç
    bulunamıyordu: `'İptal'.lower()` → 'i' + U+0307 (birleşen nokta) + 'ptal'
    üretir, `'iptal' in ...` **False** döner. İptal / İleri / İndir / İzin Ver /
    İşlem — hepsi sessizce bulunamaz oluyordu.

    Ayrıca Türkçe karakter yazmadan arayanı da kurtarır: 'gonder' → 'Gönder'.
    Sadece EŞLEŞTİRMEDE kullanılır; kullanıcıya dönen metin hep orijinaldir.
    """
    return (metin or "").translate(_KATLAMA).lower().replace('̇', '')


def yakin_metinler(aranan, sonuc=None, adet=3):
    """Bulunamayan metne ekrandaki en yakın kelimeler (kullanıcıya öneri)."""
    if sonuc is None or not sonuc.get("ok"):
        return []
    kelimeler = [k["metin"] for k in sonuc.get("kelimeler", []) if len(k["metin"]) > 1]
    if not kelimeler:
        return []
    try:
        from rapidfuzz import process
        eslesmeler = process.extract(aranan, list(dict.fromkeys(kelimeler)),
                                     limit=adet, score_cutoff=55,
                                     processor=_katla)
        return [m[0] for m in eslesmeler]
    except Exception:
        return []


def metni_bul(aranan, sonuc=None, tum_ekran=False):
    """Ekranda geçen metnin EKRAN koordinatlarını döner.

    Tek kelime de çok kelimeli ifade de aranabilir; çok kelimelide ardışık
    kelimeler birleştirilip kutuları toplanır.
    Dönen: [{"metin", "x", "y", "w", "h", "merkez": (x, y)}]  (soldan-üstten sıralı)
    """
    aranan = (aranan or "").strip()
    if not aranan:
        return []
    if sonuc is None:
        sonuc = ekrani_oku(tum_ekran=tum_ekran)
    if not sonuc.get("ok"):
        return []

    def _ara(hedef_metin):
        kelimeler = sonuc["kelimeler"]
        parcalar = [_katla(p) for p in hedef_metin.split() if p.strip()]
        if not parcalar:
            return []
        bulunanlar = []
        for i in range(len(kelimeler) - len(parcalar) + 1):
            dilim = kelimeler[i:i + len(parcalar)]
            if not all(p in _katla(d["metin"]) or _katla(d["metin"]) in p for p, d in zip(parcalar, dilim)):
                continue
            sol = min(d["x"] for d in dilim)
            ust = min(d["y"] for d in dilim)
            sag = max(d["x"] + d["w"] for d in dilim)
            alt = max(d["y"] + d["h"] for d in dilim)
            bulunanlar.append({
                "metin": " ".join(d["metin"] for d in dilim),
                "x": sol, "y": ust, "w": sag - sol, "h": alt - ust,
                "merkez": (sol + (sag - sol) // 2, ust + (alt - ust) // 2),
            })
        bulunanlar.sort(key=lambda d: (d["y"], d["x"]))
        return bulunanlar

    res = _ara(aranan)
    if res:
        return res

    # Ek temizliği: "1'yi aç" -> "1 aç" / "1'e" -> "1"
    temiz = re.sub(r"['’](?:e|a|ye|ya|ne|na|i|ı|u|ü|yi|yı|yu|yü)", "", aranan, flags=re.IGNORECASE)
    if temiz != aranan:
        res = _ara(temiz)
        if res:
            return res

    # Sadece ilk sayı / anahtar kelime dene (örn. "1'yi aç" -> "1")
    m_sayi = re.search(r'\b(\d+)\b', aranan)
    if m_sayi:
        res = _ara(m_sayi.group(1))
        if res:
            return res

    return []


# ----------------------------------------------------------------------------
# Komut ayrıştırma — `clipboard_tools.pano_komutu` ile aynı sözleşme
# ----------------------------------------------------------------------------
_GOREVLER = (
    (('özetle', 'özet çıkar', 'özetini'),
     'Bu ekran içeriğini Türkçe olarak madde madde, kısa ve net özetle.'),
    (('çevir',),
     'Bu ekran içeriğini Türkçeye çevir. Sadece çeviriyi yaz.'),
    (('hata', 'sorun', 'neden çalışmıyor'),
     'Bu ekrandaki hata mesajını Türkçe açıkla ve nasıl çözüleceğini adım adım söyle.'),
    (('açıkla', 'ne demek', 'ne anlama', 'yorumla', 'anlat'),
     'Bu ekran içeriğini basit Türkçeyle açıkla.'),
)

_OKUMA_KALIPLARI = (
    'ne yazıyor', 'ne yazar', 'ekranı oku', 'ekranda ne var', 'ekranı tara',
    'ekrandaki yazı', 'ekrandaki metn', 'ekranı okur', 'ekranda yazan',
)


def ekran_niyeti_algila(mesaj):
    """Deterministik niyet: bu cümle ekran okuma mı? (SCREENSHOT'tan SONRA bakılır)"""
    m = (mesaj or "").lower()
    if 'ekran' not in m:
        return False
    if any(k in m for k in _OKUMA_KALIPLARI):
        return True
    # "ekrandaki hatayı açıkla", "ekranı özetle", "ekranda X var mı"
    if re.search(r'ekran\w*\s+.{0,30}\b(oku|özetle|açıkla|çevir|yorumla|bul)\b', m):
        return True
    if re.search(r'ekran\w*\s+(hata|yazı|metn|metin)', m):
        return True
    if re.search(r'ekranda\s+.+\s+var\s+mı', m):
        return True
    return False


def ekran_komutu(mesaj):
    """Ekran okuma komutunu yürütür.

    Dönen: None (üstlenilmedi) | {'tip':'direct','sonuc':str}
                                | {'tip':'ai','icerik':str,'gorev':str,'baslik':str}
    """
    if not ekran_niyeti_algila(mesaj):
        return None

    m = (mesaj or "").lower()
    tum_ekran = any(k in m for k in ('tüm ekran', 'bütün ekran', 'tum ekran', 'her yeri'))

    sonuc = ekrani_oku(tum_ekran=tum_ekran)
    if not sonuc["ok"]:
        return {'tip': 'direct', 'sonuc': sonuc["hata"]}

    kaynak = "tüm ekran" if tum_ekran else (sonuc["baslik"] or "ön plandaki pencere")

    # "ekranda X var mı" / "ekranda X'i bul" → arama + koordinat
    arama = re.search(r'ekranda\s+["\'`]?(.+?)["\'`]?\s+(?:var\s+mı|arıyorum|bul)', m)
    if arama:
        hedef = arama.group(1).strip()
        eslesme = metni_bul(hedef, sonuc=sonuc)
        if not eslesme:
            return {'tip': 'direct',
                    'sonuc': f"🔍 **{kaynak}** içinde `{hedef}` bulunamadı."}
        satirlar = "\n".join(
            f"• `{e['metin']}` → ({e['merkez'][0]}, {e['merkez'][1]})" for e in eslesme[:8])
        fazla = f"\n*(+{len(eslesme) - 8} eşleşme daha)*" if len(eslesme) > 8 else ""
        return {'tip': 'direct',
                'sonuc': f"🔍 **{kaynak}** içinde {len(eslesme)} eşleşme:\n{satirlar}{fazla}"}

    metin = sonuc["metin"].strip()
    if not metin:
        return {'tip': 'direct',
                'sonuc': f"👁️ **{kaynak}** okundu ama okunabilir metin çıkmadı."}

    # LLM görevi mi (özetle/açıkla/çevir/hata) yoksa düz okuma mı?
    for anahtarlar, gorev in _GOREVLER:
        if any(a in m for a in anahtarlar):
            return {'tip': 'ai', 'icerik': metin, 'gorev': gorev, 'baslik': kaynak}

    # DÜZ OKUMA → kelime çöplüğü DEĞİL, numaralı seçilebilir öğe listesi.
    # Kullanıcı bu listeye "3'ü aç" diyerek geri dönebilsin diye saklanır.
    from features import screen_context
    ogeler = screen_context.ogeleri_cikar(sonuc)
    if ogeler:
        screen_context.okumayi_kaydet(screen_context.VARSAYILAN_KANAL, ogeler, kaynak)
        return {'tip': 'direct', 'sonuc': screen_context.ozet_uret(ogeler, kaynak),
                'ogeler': ogeler}

    # Öğe çıkmadıysa (düz metin belgesi vb.) ham metne düşülür
    kesik = metin[:1500]
    not_ = "\n\n*(ilk 1500 karakter gösterildi)*" if len(metin) > 1500 else ""
    return {'tip': 'direct',
            'sonuc': f"👁️ **{kaynak}** okundu:\n```\n{kesik}\n```{not_}"}
