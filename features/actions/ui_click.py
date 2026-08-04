"""
Ekrandaki bir düğmeye tıklama — "ekranda Kaydet'e tıkla".

AIP zinciri (fare son çaredir):
    Level 2 (UIA)    → butonu erişilebilirlik ağacında isimle bul, Invoke et.
                       Fare hiç oynamaz, en güvenilir yol.
    Level 3 (Vision) → UIA butonu göremiyorsa (Electron, oyun, canvas, uzak
                       masaüstü) ekranda OCR ile gör ve koordinatına tıkla.

Level 4 YOKTUR: "bir yere kör tıklamak" diye bir şey olamaz. Koordinatı
göremiyorsak işlem yapılmaz.

⚠️ Bu modül kullanıcı adına DÜĞMEYE BASAR. Güvenlik `level3_ocr`'daki dört
kilitte ve buradaki hedef ayrıştırıcının katılığındadır: hedef açıkça
söylenmemişse hiçbir şey yapılmaz. Araç `RISK_ONAY` ile işaretlidir —
planner çok adımlı bir planın içinde bunu kendi başına tetikleyemez.
"""

import re

from core.interaction import level2_uia, level3_ocr, level4_input
from core.interaction.base import InteractionResult, InteractionStrategy
from core.interaction.decision_engine import InteractionDecisionEngine

# "enter bas", "ctrl+s bas" KLAVYE komutudur — bu modül onlara el koymamalı.
_TUS_ADLARI = {
    'enter', 'return', 'esc', 'escape', 'tab', 'space', 'boşluk', 'delete', 'del',
    'backspace', 'home', 'end', 'insert', 'pgup', 'pgdn', 'up', 'down', 'left',
    'right', 'yukarı', 'aşağı', 'sol', 'sağ', 'ctrl', 'alt', 'shift', 'win',
}
_FIIL = r'(?:t[ıi]kla(?:r\s+m[ıi]s[ıi]n)?|bas(?:ar\s+m[ıi]s[ıi]n)?|bast[ıi]r)'
_EK = r"(?:['’](?:e|a|ye|ya|ne|na))?"
# Tırnak içindeki hedefte ek kesme işaretsiz de yazılır: "İzin Ver"e tıkla.
# Bu gevşeklik SADECE tırnaklı kalıpta güvenli — hedefin nerede bittiği belli.
_EK_SERBEST = r"(?:['’]?(?:e|a|ye|ya|ne|na))?"
_NESNE = r'(?:butonuna|butonu|dü[ğg]mesine|dü[ğg]mesi|yaz[ıi]s[ıi]na|sekmesine|linkine)?'

_KALIPLAR = (
    # tırnaklı hedef her şeyden önce gelir: ekranda "İzin Ver"e tıkla
    r'["\'`“”]\s*(?P<hedef>[^"\'`“”]{2,40}?)\s*["\'`“”]\s*' + _EK_SERBEST + r'\s*' + _NESNE + r'\s*' + _FIIL,
    # ekranda Kaydet'e tıkla · ekranda Tamam butonuna bas
    r'ekranda(?:ki)?\s+(?P<hedef>.{2,40}?)\s*' + _EK + r'\s*' + _NESNE + r'\s*' + _FIIL,
    # Kaydet butonuna tıkla  (ekran kelimesi olmadan — 'butonuna' zorunlu)
    r'(?P<hedef>.{2,40}?)\s*' + _EK + r'\s*(?:butonuna|dü[ğg]mesine)\s*' + _FIIL,
)


def tiklama_hedefi_coz(mesaj):
    """Cümleden tıklanacak yazıyı çıkarır. Anlaşılmazsa None (hiçbir şey yapma)."""
    m = (mesaj or "").strip()
    if not m:
        return None

    # ⚠️ Küçük harfe çevirip konum aramak YAPILMAZ: Türkçede 'İ'.lower() iki
    # kod noktası üretir (i + birleşen nokta), dizin kayar ve hedef bozulur.
    # Eşleştirme doğrudan ORİJİNAL cümlede, IGNORECASE ile yapılır — buton
    # adının büyük/küçük yazımı da böylece korunur (UIA eşleşmesi için önemli).
    for kalip in _KALIPLAR:
        eslesme = re.search(kalip, m, re.IGNORECASE)
        if not eslesme:
            continue
        hedef = (eslesme.group('hedef') or "").strip(" '\"`’“”\t")
        # Türkçe yönelme eki temizliği: "Kaydet'e" → "Kaydet"
        hedef = re.sub(r"['’](?:e|a|ye|ya|ne|na)$", "", hedef, flags=re.IGNORECASE).strip()
        if len(hedef) < 2:
            return None
        # Tuş adıysa bu KLAVYE komutudur, bize ait değil
        if hedef.lower() in _TUS_ADLARI or '+' in hedef:
            return None
        return hedef
    return None


def tiklama_niyeti_algila(mesaj):
    return tiklama_hedefi_coz(mesaj) is not None


class _UiaClickStrategy(InteractionStrategy):
    """Level 2: ön plandaki pencerede butonu ADIYLA bulup Invoke eder (fare yok)."""
    level = "uia"
    name = "ui_uia_click"

    def available(self) -> bool:
        return level2_uia.uia_available()

    def execute(self, **kwargs) -> InteractionResult:
        hedef = kwargs.get('ocr_text')
        if not hedef:
            return InteractionResult(False, self.level, "Hedef metin yok")

        baslik = level4_input.foreground_window_title()
        if not baslik:
            return InteractionResult(False, self.level, "Ön plandaki pencere okunamadı")

        pencere = level2_uia.find_window(re.escape(baslik), timeout=3)
        if pencere is None:
            return InteractionResult(False, self.level,
                                     f"'{baslik}' UIA ağacında açılamadı")

        buton = level2_uia.find_button(pencere, [hedef], timeout=3)
        if buton is None:
            return InteractionResult(False, self.level,
                                     f"'{hedef}' butonu UIA ağacında yok")
        if not level2_uia.invoke(buton):
            return InteractionResult(False, self.level, f"'{hedef}' tetiklenemedi")
        return InteractionResult(True, self.level,
                                 f"'{hedef}' UIA ile tetiklendi (fare kullanılmadı)")


_engine = InteractionDecisionEngine()
_engine.register("ui_click", [_UiaClickStrategy(), level3_ocr.OcrClickStrategy()])


def ekranda_tikla(hedef, sira=None):
    """Zinciri çalıştırır. Dönen: (islendi, mesaj)."""
    if not hedef:
        return False, None

    res = _engine.run("ui_click", ocr_text=hedef, ocr_index=sira)

    if res.success:
        seviye = {"uia": "UI Automation (Level 2 — fare kullanılmadı)",
                  "vision": "OCR (Level 3 — ekranda görüp tıkladı)"}.get(res.level, res.level)
        return True, f"🖱️ **{hedef}** tıklandı.\n_{seviye}_"

    denemeler = res.detail.get('attempts') or []
    ayrinti = ("\n" + "\n".join(f"• {d}" for d in denemeler)) if denemeler else ""
    return True, (f"⚠️ **{hedef}** tıklanamadı — güvenlik gereği hiçbir yere basılmadı."
                  f"\n{res.message}{ayrinti}")
