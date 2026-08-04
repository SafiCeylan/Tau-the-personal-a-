"""
WhatsApp Kontrolü — ULTRON Interaction Engine'in ilk pilot görevi.

Gönderim akışı (Adaptive Interaction Pipeline):
  Level 1: whatsapp://send?phone=..&text=..  → sohbet, mesaj hazır yazılmış açılır
  Level 2: UIA ile "Gönder" butonu bulunur ve Invoke edilir (fare/klavye YOK)
  Level 4: UIA başarısızsa — WhatsApp penceresi ÖNDE olduğu doğrulanıp Enter basılır
  Verify : mesaj kutusu boşaldıysa gönderim doğrulanmış sayılır

Kişi rehberi user_data.json içinde "whatsapp_kisiler" anahtarında tutulur:
  {"annem": "+905551112233", ...}

Komutlar:
  annem'e whatsapp'tan mesaj gönder: naber        → onay kartı sonrası gönderir
  whatsapp kişi ekle: annem = 0555 111 22 33
  whatsapp kişileri listele
  whatsapp kişi sil: annem
"""

import json
import os
import re
import time
import urllib.parse

from core.interaction import InteractionResult, InteractionStrategy, InteractionDecisionEngine
from core.interaction import level1_native, level2_uia, level4_input, verification

from core.paths import veri_yolu

USER_DATA_PATH = veri_yolu('user_data.json')

KISILER_KEY = 'whatsapp_kisiler'
WA_TITLE_RE = r'.*WhatsApp.*'

# Gönderim fiilleri ve alıcı ayıklamada elenecek gürültü kelimeleri
# ⚠️ Kelime sınırı ŞART: çıplak 'at' alt dizisi "saat/anlat/hayat", 'yaz' ise
# "ne yazık/yazılım/yaz tatili" içinde geçiyor. Sınırsız hâlde bu cümleler
# WhatsApp komutu sayılıp kullanıcıya "komutu çözemedim" rehberi basılıyordu.
# Not: 'de' de bir gönderim fiilidir ("anneme geç kalacağım DE"). Eski sınırsız
# sürümde bu cümle kapıdan yalnızca "whatsAPP" kelimesinin içindeki 'at' alt
# dizisi sayesinde geçiyordu — yani doğru sonuç yanlış sebeple çıkıyordu.
_FIIL_RE = re.compile(
    r'\b(?:gönder\w*|yolla\w*|at|atar|atsana|yaz|yazar|yazsana|de|dedi|diye|söyle\w*)\b')


def _fiil_var_mi(ml: str) -> bool:
    return bool(_FIIL_RE.search(ml))


_NOISE = {'tan', 'dan', 'ten', 'den', 'üzerinden', 'mesaj', 'mesajı', 'whatsapp', 'wp', 'bir'}


# ---------------------------------------------------------------------------
# Kişi Rehberi
# ---------------------------------------------------------------------------
def _user_data_yukle() -> dict:
    try:
        with open(USER_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _user_data_kaydet(data: dict):
    with open(USER_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def kisiler_yukle() -> dict:
    data = _user_data_yukle()
    kisiler = data.get(KISILER_KEY, {})
    return kisiler if isinstance(kisiler, dict) else {}


def numara_normalize(raw: str):
    """'0555 111 22 33' → '+905551112233'. Geçersizse None."""
    s = re.sub(r'[ \-().]', '', (raw or '').strip())
    if s.startswith('00'):
        s = '+' + s[2:]
    if re.fullmatch(r'0\d{10}', s):        # 05551112233 → +905551112233
        s = '+9' + s
    elif re.fullmatch(r'5\d{9}', s):       # 5551112233 → +905551112233
        s = '+90' + s
    if re.fullmatch(r'\+\d{10,15}', s):
        return s
    return None


def kisi_ekle(isim: str, numara_raw: str):
    isim = isim.lower().strip()
    numara = numara_normalize(numara_raw)
    if not isim:
        return True, "⚠️ Kişi adı boş olamaz."
    if not numara:
        return True, (f"⚠️ '{numara_raw}' geçerli bir telefon numarası değil.\n"
                      "Kabul edilen biçimler: `+905551112233`, `05551112233`, `0555 111 22 33`")
    data = _user_data_yukle()
    kisiler = data.get(KISILER_KEY, {})
    kisiler[isim] = numara
    data[KISILER_KEY] = kisiler
    _user_data_kaydet(data)
    return True, f"✅ **WhatsApp rehberine eklendi:** {isim} → `{numara}`"


def kisi_sil(isim: str):
    isim = isim.lower().strip()
    data = _user_data_yukle()
    kisiler = data.get(KISILER_KEY, {})
    if isim in kisiler:
        del kisiler[isim]
        data[KISILER_KEY] = kisiler
        _user_data_kaydet(data)
        return True, f"🗑️ **{isim}** WhatsApp rehberinden silindi."
    return True, f"⚠️ '{isim}' rehberde bulunamadı."


def kisileri_listele():
    kisiler = kisiler_yukle()
    if not kisiler:
        return True, ("📱 WhatsApp rehberi boş.\n"
                      "Eklemek için: `whatsapp kişi ekle: annem = 0555 111 22 33`")
    lines = [f"• **{isim}** → `{num}`" for isim, num in sorted(kisiler.items())]
    return True, "📱 **WHATSAPP REHBERİ:**\n\n" + "\n".join(lines)


def kisi_coz(alici: str):
    """Alıcı adını/numarasını çözer → '+90...' veya None.
    Türkçe yönelme eklerini tolere eder: 'anneme' → 'annem'.

    Rehberde bulunamazsa TAKMA AD katmanına sorulur ("patronum" → "Ahmet Kaya").
    ⚠️ Sıra önemli: rehberdeki DOĞRUDAN kayıt her zaman kazanır. Doğrudan kayıt
    daha açık bir niyettir; takma ad yalnızca son çare."""
    key = (alici or '').lower().strip()
    kisiler = kisiler_yukle()
    if key in kisiler:
        return kisiler[key]
    for suf in ('ye', 'ya', 'e', 'a'):
        if key.endswith(suf) and key[:-len(suf)] in kisiler:
            return kisiler[key[:-len(suf)]]

    # Takma ad → gerçek kişi → rehber
    try:
        from core.aliases import takma_adi_coz
        gercek = takma_adi_coz(key)
        if gercek and gercek.lower().strip() in kisiler:
            return kisiler[gercek.lower().strip()]
    except Exception as e:
        print(f"[Ultron TakmaAd] Kişi çözümü atlandı: {e}")

    return numara_normalize(key)


# ---------------------------------------------------------------------------
# Komut Ayrıştırma
# ---------------------------------------------------------------------------
def _whatsapp_gecinor_mu(ml: str) -> bool:
    return 'whatsapp' in ml or re.search(r'\bwp\b', ml) is not None


def kanalsiz_mesaj_ayristir(mesaj: str):
    """Kanal adı GEÇMEYEN mesaj cümlesini ayrıştırır → (alici, metin) | None.

    "anneme mesaj at: yoldayım" / "anneme yaz geç kalacağım" gibi cümlelerde
    kullanıcı "whatsapp" demez. Niyet katmanı kanalı zaten REHBERE sorarak
    belirlediği için (bkz. `_rehberden_kanal_coz`), burada kanal kelimesi
    aramayız — yoksa niyet WhatsApp'a gelir ama araç cümleyi reddeder ve
    komut sessizce LLM'e düşerdi.
    """
    kaliplar = (
        r"(\S+?)['’]?[ea]\s+(?:mesaj\s+)?(?:gönder|yolla|yaz|at)\s*:\s*(.+)$",
        r"(\S+?)['’]?[ea]\s+(?:mesaj\s+)?(?:gönder|yolla|yaz|at)\s+(.+)$",
    )
    for kalip in kaliplar:
        m = re.search(kalip, mesaj, re.IGNORECASE | re.DOTALL)
        if m:
            alici = ' '.join(t for t in m.group(1).strip().lower().split()
                             if t not in _NOISE).strip()
            metin = m.group(2).strip()
            if alici and metin:
                return alici, metin
    return None


def whatsapp_gonderim_ayristir(mesaj: str):
    """
    Gönderim komutunu ayrıştırır → (alici, metin) veya None.
    Desteklenen biçimler:
      "annem'e whatsapp'tan mesaj gönder: naber"
      "whatsapp'tan annem'e yaz: naber kanka"
      "whatsapp gönder annem: naber"
    """
    ml = mesaj.lower().strip()
    if not _whatsapp_gecinor_mu(ml):
        return None
    if not _fiil_var_mi(ml):
        return None
    if 'kişi' in ml:  # rehber komutlarıyla karışmasın
        return None

    # ── DOĞAL (iki noktasız) KALIPLAR ──
    # "anneme iyi akşamlar yazılı mesaj gönder whatsapp üzerinden"
    # "whatsapp'tan anneme iyi akşamlar gönder" / "anneme whatsapptan naber yaz"
    dogal_kaliplar = [
        r"(\S+?)['’]?[ea]\s+(.+?)\s+(?:yazılı|yazan|diye)\s+(?:bir\s+)?mesaj",
        r"whatsapp\S*(?:\s+üzerinden)?\s+(\S+?)['’]?[ea]\s+(.+?)\s+(?:gönder|yolla|yaz|at)\b",
        r"(\S+?)['’]?[ea]\s+whatsapp\S*\s+(.+?)\s+(?:gönder|yolla|yaz|at)\b",
        # FİİL ORTADA — en doğal yazım, eskiden HİÇ desteklenmiyordu:
        #   "anneme whatsapp at yarın gelemeyeceğim"
        #   "seyit'e whatsapp gönder toplantı ertelendi"
        r"(\S+?)['’]?[ea]\s+whatsapp\S*(?:\s+üzerinden)?\s+"
        r"(?:gönder|yolla|yaz|at)\s+(.+)$",
        #   "whatsapp ile anneme geç kalacağım de"
        r"whatsapp\S*(?:\s+ile|\s+üzerinden)?\s+(\S+?)['’]?[ea]\s+(.+?)\s+de\s*$",
        #   "whatsapp'tan anneme yaz geç kalacağım"
        r"whatsapp\S*(?:\s+ile|\s+üzerinden)?\s+(\S+?)['’]?[ea]\s+"
        r"(?:gönder|yolla|yaz|at)\s+(.+)$",
    ]
    for kalip in dogal_kaliplar:
        m = re.search(kalip, mesaj, re.IGNORECASE)
        if m:
            alici = m.group(1).strip().lower()
            metin = m.group(2).strip()
            # Mesaj içinden whatsapp/bağlaç kalıntılarını süz
            metin = re.sub(r"\bwhatsapp\S*\b|\büzerinden\b|\bmesaj\b|\byazılı\b|\bdiye\b",
                           " ", metin, flags=re.IGNORECASE)
            metin = re.sub(r'\s+', ' ', metin).strip()
            alici = ' '.join(t for t in alici.split() if t not in _NOISE).strip()
            if alici and metin:
                return alici, metin

    # ── KLASİK ':' KALIBI ──
    m = re.search(r'\b(?:gönder|yolla|at|yaz)\s*:\s*(.+)$', mesaj, re.IGNORECASE | re.DOTALL)
    if m:
        metin = m.group(1).strip()
        once = mesaj[:m.start()]
    else:
        once, sep, metin = mesaj.partition(':')
        if not sep:
            return None
        metin = metin.strip()
    if not metin:
        return None

    once_l = once.lower()

    # Alıcı: "X'e" / "Xe" kalıbı.
    # ⚠️ KESME İŞARETİ ZORUNLU DEĞİL. Eski hâli `['’]` şart koşuyordu; kimse
    # "annem'e" yazmıyor, "anneme" yazıyor. Bu yüzden BELGELENMİŞ biçim olan
    # "anneme whatsapp gönder: yoldayım" bile ayrıştırılamıyordu.
    alici = None
    m = re.search(r"\b([\wçğıöşü+]{2,}?)['’]?(?:ye|ya|e|a)\b", once_l)
    if m:
        alici = m.group(1).strip()
    else:
        # "whatsapp gönder annem" kalıbı: fiilden sonraki kelime(ler)
        m = re.search(r"\b(?:gönder|yolla|at|yaz)\s+([\w+ ]+)$", once_l)
        if m:
            alici = m.group(1).strip()

    if not alici:
        return None

    # Gürültü kelimelerini ayıkla ("tan annem" → "annem")
    alici = ' '.join(t for t in alici.split() if t not in _NOISE).strip()
    if not alici:
        return None

    return alici, metin


# ---------------------------------------------------------------------------
# AIP Stratejileri — "whatsapp_send" aksiyonu
# ---------------------------------------------------------------------------
class _UIASendStrategy(InteractionStrategy):
    """Level 2: WhatsApp penceresinde 'Gönder' butonunu UIA ile Invoke eder."""
    level = "uia"
    name = "whatsapp_uia_send"

    def available(self) -> bool:
        return level2_uia.uia_available()

    def execute(self, **kwargs) -> InteractionResult:
        win = level2_uia.find_window(WA_TITLE_RE, timeout=20)
        if win is None:
            return InteractionResult(False, self.level, "WhatsApp penceresi bulunamadı")

        # Metin kutusunda hazır yazılmış mesajın gelmesini bekle (URI prefill gecikebilir)
        edit = level2_uia.find_edit(win, timeout=10)
        if edit is not None:
            deadline = time.time() + 8
            while time.time() < deadline:
                if (level2_uia.get_edit_text(edit) or "").strip():
                    break
                time.sleep(0.5)

        btn = level2_uia.find_button(win, ["Gönder", "Send"], timeout=10)
        if btn is None:
            return InteractionResult(False, self.level, "Gönder butonu UIA ağacında bulunamadı")
        if not level2_uia.invoke(btn):
            return InteractionResult(False, self.level, "Gönder butonu tetiklenemedi")
        return InteractionResult(True, self.level, "UIA ile gönderildi (fare kullanılmadı)")


class _InputSendStrategy(InteractionStrategy):
    """Level 4 (son çare): WhatsApp penceresi ÖNDEYSE Enter basar."""
    level = "input"
    name = "whatsapp_focus_enter"

    def execute(self, **kwargs) -> InteractionResult:
        # Prefill'in yerleşmesi için kısa bekleme
        time.sleep(2.0)
        if level4_input.press_enter(require_title_contains="whatsapp", timeout=12):
            return InteractionResult(True, self.level, "Odak korumalı Enter ile gönderildi")
        return InteractionResult(False, self.level,
                                 "WhatsApp penceresi öne gelmedi — güvenlik gereği tuş gönderilmedi")


_engine = InteractionDecisionEngine()
_engine.register("whatsapp_send", [_UIASendStrategy(), _InputSendStrategy()])


def _dogrulayici(**kwargs):
    return verification.verify_edit_cleared(WA_TITLE_RE, timeout=6)


# ---------------------------------------------------------------------------
# Gönderim
# ---------------------------------------------------------------------------
def whatsapp_mesaj_gonder(alici: str, metin: str):
    """Onay SONRASI çağrılır. Sohbeti açar, AIP zinciriyle gönderir, doğrular."""
    numara = kisi_coz(alici)
    if not numara:
        kisiler = kisiler_yukle()
        mevcut = ', '.join(sorted(kisiler)) if kisiler else 'rehber boş'
        return True, (f"⚠️ **'{alici}'** WhatsApp rehberinde bulunamadı. (Kayıtlı: {mevcut})\n"
                      f"Eklemek için: `whatsapp kişi ekle: {alici} = 0555 111 22 33`")

    # Level 1: sohbeti mesaj hazır yazılmış şekilde aç
    uri = f"whatsapp://send?phone={numara}&text={urllib.parse.quote(metin)}"
    if not level1_native.open_uri(uri):
        return True, "❌ WhatsApp URI ile açılamadı. WhatsApp Desktop kurulu mu?"

    # Level 2 → Level 4 zinciri + doğrulama
    res = _engine.run("whatsapp_send", verifier=_dogrulayici, metin=metin)

    if res.success:
        seviye = {"uia": "UI Automation (Level 2)", "input": "Klavye (Level 4)"}.get(res.level, res.level)
        dogruluk = {True: "✅ doğrulandı (mesaj kutusu boşaldı)",
                    False: "⚠️ doğrulanamadı",
                    None: "ℹ️ doğrulama yapılamadı"}[res.verified]
        return True, (f"📱 **WHATSAPP GÖNDERİLDİ**\n"
                      f"• Alıcı: **{alici}** (`{numara}`)\n"
                      f"• Mesaj: \"{metin}\"\n"
                      f"• Yöntem: {seviye}\n"
                      f"• Durum: {dogruluk}")

    denemeler = "\n".join(f"  - {a}" for a in res.detail.get('attempts', []))
    return True, (f"❌ **WHATSAPP GÖNDERİLEMEDİ** — sohbet açıldı ama gönderim tamamlanamadı.\n"
                  f"Denenen yöntemler:\n{denemeler}\n"
                  f"Mesaj WhatsApp'ta hazır yazılı bekliyor olabilir — elle Enter'a basabilirsiniz.")


# ---------------------------------------------------------------------------
# Ana Komut Algılayıcı
# ---------------------------------------------------------------------------
def whatsapp_komutu_algila(mesaj: str):
    """
    WhatsApp komutlarını algılar ve yürütür.
    Dönen değer: (işlendi_mi, yanıt) — işlenmediyse (False, None)
    """
    ml = mesaj.lower().strip()
    if not _whatsapp_gecinor_mu(ml):
        # Kanal adı yok ama niyet katmanı rehberden WhatsApp'a karar vermiş
        # olabilir ("anneme mesaj at: yoldayım"). Alıcı rehberde ÇÖZÜLÜYORSA
        # üstleniriz; çözülmüyorsa dokunmayız (yanlış kişiye mesaj gitmesin).
        kanalsiz = kanalsiz_mesaj_ayristir(mesaj)
        if kanalsiz and kisi_coz(kanalsiz[0]):
            return whatsapp_mesaj_gonder(*kanalsiz)
        return False, None

    # Rehber yönetimi
    m = re.search(r'kişi\s+ekle\s*:\s*(.+?)\s*=\s*(.+)$', mesaj, re.IGNORECASE)
    if m:
        return kisi_ekle(m.group(1), m.group(2))

    m = re.search(r'kişi\s+sil\s*:\s*(.+)$', mesaj, re.IGNORECASE)
    if m:
        return kisi_sil(m.group(1))

    if 'kişi' in ml and any(k in ml for k in ['listele', 'göster', 'liste']):
        return kisileri_listele()
    if ml in ('whatsapp kişiler', 'whatsapp rehber', 'whatsapp rehberi'):
        return kisileri_listele()

    # Mesaj gönderimi
    parsed = whatsapp_gonderim_ayristir(mesaj)
    if parsed:
        alici, metin = parsed
        return whatsapp_mesaj_gonder(alici, metin)

    # WhatsApp'la ilgili bir gönderim isteği ama çözülemedi →
    # LLM'e DÜŞÜRME (saçmalıyor); kullanım rehberi göster
    if 'mesaj' in ml or _fiil_var_mi(ml):
        return True, ("⚠️ WhatsApp komutunu tam çözemedim. Şu biçimlerden birini kullan:\n"
                      "• `annem'e whatsapp'tan mesaj gönder: iyi akşamlar`\n"
                      "• `anneme iyi akşamlar yazılı mesaj gönder whatsapp üzerinden`\n"
                      "• Rehber: `whatsapp kişi ekle: annem = 05XX XXX XX XX`\n"
                      "• `whatsapp kişileri listele`")

    return False, None
