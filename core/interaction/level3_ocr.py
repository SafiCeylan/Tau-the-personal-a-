"""
AIP Level 3 — Vision (OCR) katmanı.

UIA'nın GÖREMEDİĞİ arayüzler için: Electron uygulamaları, oyunlar, uzak masaüstü,
canvas/WebGL çizen pencereler. Metni ekrandan okur, koordinatını bulur, tıklar.

Zincirdeki yeri neden burası:
  • Level 2 (UIA) daha güvenilir — element ağacı DPI/konum değişse de doğru.
    Bu yüzden ondan SONRA denenir.
  • Level 4 (kör klavye) daha kırılgan — nereye bastığını görmez.
    Bu yüzden ondan ÖNCE denenir. Level 3 nereye tıkladığını GÖRÜR.

⚠️ DÖRT GÜVENLİK KİLİDİ — biri bile ihlal edilirse tıklama yapılmaz:

  1. TEK EŞLEŞME ŞARTI. "Kaydet" ekranda üç yerde geçiyorsa hangisi olduğunu
     bilemeyiz. Yanlış yere tıklamak, hiç tıklamamaktan KÖTÜDÜR — iptal edilir
     ve adaylar mesajda döner. (`sira` verilirse kullanıcı seçmiş sayılır.)
  2. ODAK KORUMASI. Hedef pencere önde değilse tıklanmaz (Level 4 felsefesi).
  3. PENCERE KAYMADI KONTROLÜ. OCR ile tıklama arasında pencere taşındıysa
     koordinat bayattır; pencere dikdörtgeni yeniden ölçülür, değiştiyse iptal.
  4. NOKTA SAHİBİ KONTROLÜ. Tıklanacak pikselin hangi pencereye ait olduğu
     `WindowFromPoint` ile sorulur. Araya bir bildirim/açılır pencere girdiyse
     o pencere yanıt verir → iptal.

Tıklamadan sonra fare imleci ESKİ KONUMUNA döndürülür.
"""

import ctypes
import re
import sys
import time
from ctypes import wintypes

from core.interaction.base import InteractionResult, InteractionStrategy
from features import screen_reader as sr

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Pencere dikdörtgeninde bu kadar piksel oynama tolere edilir (gölge/DPI payı)
_KAYMA_TOLERANSI = 2


def ocr_click_available() -> bool:
    """Bu makinede OCR ile tıklama mümkün mü?"""
    if sys.platform != 'win32':
        return False
    hazir, _ = sr.ocr_hazir()
    return hazir


# ---------------------------------------------------------------------------
# Fare (yalnızca bu modülden — zırh testlerde bu ctypes'ı taklitler)
# ---------------------------------------------------------------------------
def _imlec_konumu():
    nokta = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(nokta))
    return nokta.x, nokta.y


def _sol_tikla(x, y, geri_don=True):
    """(x, y) noktasına tıklar ve imleci eski yerine bırakır."""
    eski = _imlec_konumu() if geri_don else None
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)                     # hedef pencere hover'ı işlesin
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    if eski:
        time.sleep(0.05)
        ctypes.windll.user32.SetCursorPos(eski[0], eski[1])


def _kok_pencere(hwnd):
    """Alt kontrolden üst seviye pencereye çıkar (GA_ROOT = 2)."""
    try:
        return ctypes.windll.user32.GetAncestor(hwnd, 2) or hwnd
    except Exception:
        return hwnd


def _noktadaki_pencere_basligi(x, y) -> str:
    """O pikselin sahibi olan ÜST SEVİYE pencerenin başlığı."""
    try:
        nokta = wintypes.POINT(int(x), int(y))
        hwnd = ctypes.windll.user32.WindowFromPoint(nokta)
        if not hwnd:
            return ""
        return sr._pencere_basligi(_kok_pencere(hwnd))
    except Exception:
        return ""


def _onplan_basligi() -> str:
    try:
        return sr._pencere_basligi(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        return ""


def _bolge_ayni_mi(baslik, beklenen_bolge) -> bool:
    """Pencere OCR'dan bu yana kaydı mı? (bayat koordinatla tıklamayı önler)"""
    if not beklenen_bolge:
        return True
    guncel, _ = sr.okunacak_pencere()
    if not guncel:
        return False
    return all(abs(guncel[k] - beklenen_bolge[k]) <= _KAYMA_TOLERANSI
               for k in ("left", "top", "width", "height"))


# ---------------------------------------------------------------------------
# Ana yetenek
# ---------------------------------------------------------------------------
def metne_tikla(metin, sira=None, odak_zorunlu=True, okuma=None) -> InteractionResult:
    """Ekranda geçen metni bulur ve üstüne tıklar.

    metin  : aranacak yazı ("Gönder", "Dosyayı Kaydet")
    sira   : birden çok eşleşme varsa kaçıncısı (0 tabanlı). Verilmezse ÇOKLU
             eşleşmede tıklanmaz — hangi 'Kaydet' olduğunu bilmiyoruz.
    okuma  : hazır `ekrani_oku()` sonucu (iki kez okumamak için)
    """
    if not ocr_click_available():
        return InteractionResult(False, "vision", "OCR bu makinede kullanılamıyor.")

    metin = (metin or "").strip()
    if not metin:
        return InteractionResult(False, "vision", "Aranacak metin boş.")

    okuma = okuma or sr.ekrani_oku()
    if not okuma.get("ok"):
        return InteractionResult(False, "vision", okuma.get("hata") or "Ekran okunamadı.")

    hedef_pencere = okuma.get("baslik") or ""
    eslesmeler = sr.metni_bul(metin, sonuc=okuma)

    if not eslesmeler:
        # HANGİ pencereye baktığımızı söylemek şart: kullanıcı başka bir pencereyi
        # kastediyor olabilir (Ultron ön plandayken arkadaki pencere okunur).
        nerede = f"'{hedef_pencere}' penceresinde" if hedef_pencere else "ekranda"
        yakin = sr.yakin_metinler(metin, okuma)
        oneri = f" Ekranda en yakın: {', '.join(yakin)}." if yakin else ""
        return InteractionResult(
            False, "vision", f"'{metin}' {nerede} bulunamadı.{oneri}",
            detail={'window': hedef_pencere})

    # KİLİT 1 — çok eşleşme: tahmin yürütme
    if len(eslesmeler) > 1 and sira is None:
        # İSTİSNA: Hedef rakam/sıra numarası ise ("1", "1'e", "1'yi aç", "1. video")
        # kullanıcı açıkça ekrandaki ilk eşleşmeyi (0. aday) istemektedir.
        if re.search(r'\b\d+\b', metin):
            sira = 0
        else:
            adaylar = ", ".join(f"[{i}] ({e['merkez'][0]},{e['merkez'][1]})"
                                for i, e in enumerate(eslesmeler[:6]))
            return InteractionResult(
                False, "vision",
                f"'{metin}' {len(eslesmeler)} yerde geçiyor — hangisi olduğu belirsiz, "
                f"tıklamadım. Adaylar: {adaylar}",
                detail={'matches': eslesmeler})

    secilen = eslesmeler[sira or 0] if (sira or 0) < len(eslesmeler) else None
    if secilen is None:
        return InteractionResult(False, "vision",
                                 f"Sıra {sira} yok ({len(eslesmeler)} eşleşme var).")

    x, y = secilen["merkez"]

    # KİLİT 2 — odak koruması
    if odak_zorunlu and hedef_pencere:
        onplan = _onplan_basligi()
        if "ultron" in onplan.lower() and "ultron" not in hedef_pencere.lower():
            # Ultron onay almak için öne geçmişti; hedef pencereyi tekrar öne getir
            try:
                from core.world_state import uygun_pencereyi_odakla
                uygun_pencereyi_odakla(hedef_pencere)
                time.sleep(0.3)
                onplan = _onplan_basligi()
            except Exception:
                pass

        if hedef_pencere.lower() not in onplan.lower():
            return InteractionResult(
                False, "vision",
                f"Odak koruması: '{hedef_pencere}' önde değil (önde: '{onplan}'), tıklamadım.")

    # KİLİT 3 — pencere OCR'dan sonra kaydı mı?
    if not _bolge_ayni_mi(hedef_pencere, okuma.get("bolge")):
        return InteractionResult(
            False, "vision",
            "Pencere okuma ile tıklama arasında taşındı — koordinat bayat, tıklamadım.")

    # KİLİT 4 — o pikselin sahibi gerçekten hedef pencere mi?
    if hedef_pencere:
        sahip = _noktadaki_pencere_basligi(x, y)
        if sahip and hedef_pencere.lower() not in sahip.lower():
            return InteractionResult(
                False, "vision",
                f"({x},{y}) noktası '{sahip}' penceresine ait, '{hedef_pencere}' değil — "
                f"araya bir pencere girmiş olabilir, tıklamadım.")

    _sol_tikla(x, y)
    return InteractionResult(
        True, "vision", f"'{secilen['metin']}' ({x},{y}) tıklandı.",
        detail={'x': x, 'y': y, 'window': hedef_pencere,
                'match_count': len(eslesmeler)})


def noktaya_tikla(x, y, etiket="", odak_zorunlu=True) -> InteractionResult:
    """Ekran okumasından gelen HAZIR koordinata tıklar.

    `metne_tikla`dan farkı: metni yeniden aramaz — öğe zaten seçilmiştir.
    Ama güvenlik kilitleri aynen uygulanır (odak + nokta sahibi), çünkü
    okuma ile tıklama arasında ekran değişmiş olabilir.
    """
    if not ocr_click_available():
        return InteractionResult(False, "vision", "OCR bu makinede kullanılamıyor.")

    _, hedef_pencere = sr.okunacak_pencere()

    if odak_zorunlu and hedef_pencere:
        onplan = _onplan_basligi()
        if hedef_pencere.lower() not in onplan.lower():
            return InteractionResult(
                False, "vision",
                f"Odak koruması: '{hedef_pencere}' önde değil (önde: '{onplan}').")

    sahip = _noktadaki_pencere_basligi(x, y)
    if hedef_pencere and sahip and hedef_pencere.lower() not in sahip.lower():
        return InteractionResult(
            False, "vision",
            f"({x},{y}) noktası '{sahip}' penceresine ait — araya bir pencere girmiş.")

    _sol_tikla(x, y)
    return InteractionResult(True, "vision", f"'{etiket or 'öğe'}' ({x},{y}) tıklandı.",
                             detail={'x': x, 'y': y, 'window': hedef_pencere})


def metin_kayboldu_mu(metin, bekle=0.6) -> bool:
    """Doğrulayıcı: tıklanan metin ekrandan kalktı mı (diyalog kapandı mı)?"""
    time.sleep(bekle)
    return not sr.metni_bul(metin)


class OcrClickStrategy(InteractionStrategy):
    """Karar motoruna takılabilen Level 3 stratejisi.

    Beklenen kwargs: `ocr_text` (zorunlu), `ocr_index`, `ocr_require_focus`.
    Zincirdeki diğer stratejilerin kwargs'ını görmezden gelir.
    """
    level = "vision"
    name = "ocr_click"

    def available(self) -> bool:
        return ocr_click_available()

    def execute(self, **kwargs) -> InteractionResult:
        metin = kwargs.get('ocr_text') or kwargs.get('buton_metni')
        if not metin:
            return InteractionResult(False, "vision",
                                     "OCR stratejisi için 'ocr_text' verilmedi.")
        return metne_tikla(metin,
                           sira=kwargs.get('ocr_index'),
                           odak_zorunlu=kwargs.get('ocr_require_focus', True))
