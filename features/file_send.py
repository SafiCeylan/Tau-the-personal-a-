# -*- coding: utf-8 -*-
"""
Dosya Gönderimi — "bul ve gönder" akışının beyni.

Akış:
    telefondan:  "staj raporunu bul"        → indekste ara, numaralı liste dön
                 "1'i bana gönder"          → dosya Telegram'a gelir
                 "1'i anneme mail at"       → dosya e-posta EKİ olarak gider
                 "1'i anneme whatsapp'tan gönder" → panoya kopyala + sohbete yapıştır

Tek adımda da olur: "staj raporunu anneme mail at" — tek sonuç varsa doğrudan
gönderir, birden fazlaysa listeler ve numara sorar.

GÜVENLİK:
  • Gönderim hedefi BAŞKASI ise (mail/whatsapp) komut onay kartından geçer —
    onayı `pipeline_layers` SecurityAnalyzer verir, yürütmeyi `confirmed_executor`.
  • "bana gönder" (kendi Telegram'ına) onay istemez; dosya sahibinin kendisine gider.
  • Sır taşıyan dosyalar indekste zaten yok (`file_index.gizli_mi`), ayrıca gönderim
    anında bir kez daha kontrol edilir (dosya sonradan değişmiş olabilir).
"""

import json
import os
import re
import sys
import time

from features import file_index

from core.paths import veri_yolu

CONFIG_PATH = veri_yolu('config.json')

# Varsayılan kanal: masaüstünden verilen komutlar bu ada yazılır
MASAUSTU_KANALI = 'desktop'

_ARAMA_FIILLERI = ('bul', 'ara', 'nerede', 'listele', 'göster')
_GONDERIM_FIILLERI = ('gönder', 'yolla', 'at', 'ilet', 'paylaş')
# "aç" fiili SYSTEM_CONTROL ile çakışır ("chrome aç"). Bu yüzden 'ac' işlemi
# YALNIZCA güçlü dosya sinyali olan cümlelerde üretilir — aşağıya bak.
#
# ⚠️ Karşılaştırma `file_index.sadelestir()` çıktısı üzerinde yapılır: Türkçe
# harfler sadeleşir, "aç" → "ac". Bu yüzden kalıp ASCII olmalı.
# ⚠️ Kelime sınırı şart: çıplak "ac" alt dizisi "ihtiyac", "acele", "aciklama"
# gibi kelimelerin içinde geçer.
_ACMA_RE = re.compile(r'\bac\b')

# os.startfile bu uzantılarda dosyayı AÇMAZ, ÇALIŞTIRIR. İndekste 134 bin dosya
# var; yanlış eşleşme program başlatmak demek. Bunlar onay kartından geçer.
CALISTIRILABILIR_UZANTILAR = (
    '.exe', '.bat', '.cmd', '.com', '.msi', '.ps1', '.vbs', '.vbe',
    '.js', '.jse', '.wsf', '.wsh', '.scr', '.cpl', '.reg', '.lnk', '.jar',
)


def calistirilabilir_mi(yol: str) -> bool:
    """Bu dosyayı 'açmak' aslında program çalıştırmak mı olur?"""
    return str(yol or '').lower().endswith(CALISTIRILABILIR_UZANTILAR)

# "1'i", "2'yi", "3.", "4 numaralı" gibi seçim ifadeleri
_SECIM_RE = re.compile(
    r"^\s*(\d{1,2})\s*['’´]?\s*(?:y?[iıuü]|nci|inci|uncu|üncü|numaral[iı]|numara)?\s*[\.\)]?\s+",
    re.IGNORECASE)

# Bunlar METİN mesajı komutudur, dosya komutu değil — karışma
_MESAJ_ISARETLERI = re.compile(r'\b(mesaj|yaz[iı]l[iı]|yaz)\b')

# Dosya olduğuna dair GÜÇLÜ sinyaller
_KLASOR_KELIMELERI = ('masaustu', 'masaustunde', 'indirilenler', 'belgeler', 'resimler',
                      'videolar', 'muzikler', 'downloads', 'desktop', 'documents')
_YER_KELIMELERI = ('nerede', 'nerde', 'bilgisayarim', 'bilgisayarimda', 'pcde', 'pcmde',
                   'diskimde', 'klasor')

_TUR_SOZLUGU = file_index.TUR_UZANTILARI


def _config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# KOMUT AYRIŞTIRMA
# ---------------------------------------------------------------------------
def _hedef_belirle(ml: str):
    """Mesajdan gönderim hedefini çıkarır → ('telegram'|'email'|'whatsapp', alici)"""
    if re.search(r'\bwhatsapp|wp\b', ml):
        return 'whatsapp', _alici_cikar(ml)
    if re.search(r'\b(mail|e-?posta)\b', ml):
        return 'email', _alici_cikar(ml)
    if re.search(r'\b(bana|telefonuma|telegram\w*)\b', ml):
        return 'telegram', None
    return None, None


def _alici_cikar(ml: str):
    """"anneme mail at" → "anneme" (kişi çözümü ilgili modülde yapılır)."""
    m = re.search(r"([\wçğıöşü.+\-@]{2,})['’]?(?:e|a|ye|ya)\s+(?:whatsapp|wp|mail|e-?posta)", ml)
    if m:
        return m.group(1)
    # "mail at anneme" / "whatsapp'tan anneme gönder" gibi ters diziliş
    m = re.search(r"(?:mail|e-?posta|whatsapp|wp)[\w'’]*\s+(?:olarak\s+)?([\wçğıöşü.+\-@]{2,})['’]?(?:e|a|ye|ya)\b", ml)
    if m:
        return m.group(1)
    # Serbest: cümledeki ilk yönelme hâli ("anneme ... gönder")
    m = re.search(r"\b([\wçğıöşü.+\-@]{3,})(?:'|’)?(?:e|a|ye|ya)\s+(?:gönder|yolla|at|ilet|paylaş)", ml)
    if m and m.group(1) not in ('bana', 'telegram'):
        return m.group(1)
    return None


def dosya_komutu_ayristir(mesaj: str):
    """
    → {'islem': 'ara'|'gonder', 'sorgu', 'secim', 'hedef', 'alici', 'tur', 'zayif'}
    Dosya komutu değilse None.

    `zayif=True`: cümlede dosya olduğuna dair güçlü bir işaret yok ("staj raporunu
    anneme mail at" gibi). Bu durumda karar İNDEKSE bırakılır — eşleşme varsa dosya
    komutudur, yoksa çağıran katman (WhatsApp mesajı / web araması / LLM) devam eder.
    Bu sayede "whatsapp'tan anneme naber gönder" yanlışlıkla dosya komutu sayılmaz.
    """
    ham = (mesaj or '').strip()
    ml = file_index.sadelestir(ham)
    if not ml:
        return None

    # Metin mesajı komutları bu modülün işi değil ("...mesaj gönder: naber")
    if _MESAJ_ISARETLERI.search(ml) or ':' in ham:
        return None

    hedef, alici = _hedef_belirle(ml)
    gonderim_var = any(f in ml for f in _GONDERIM_FIILLERI) or hedef is not None
    arama_var = any(f in ml for f in _ARAMA_FIILLERI)
    acma_var = bool(_ACMA_RE.search(ml))

    # Sıra numarasıyla seçim: "1'i bana gönder"
    secim = None
    m = _SECIM_RE.match(ham)
    if m and gonderim_var:
        secim = int(m.group(1))
        sorgu_ham = ham[m.end():]
    else:
        sorgu_ham = ham

    if not (gonderim_var or arama_var or acma_var):
        return None

    tur = _tur_bul(ml)
    sorgu = _sorguyu_temizle(sorgu_ham, tur)

    # Güçlü dosya sinyali var mı?
    guclu = bool(
        re.search(r'\bdosya', ml) or tur or secim is not None
        or any(k in ml for k in _YER_KELIMELERI)
        or any(k in ml for k in _KLASOR_KELIMELERI)
    )

    if secim is not None or hedef:
        islem = 'gonder'
    elif acma_var and guclu:
        # ⚠️ 'ac' SADECE güçlü sinyalde. Aksi halde "chrome aç" indekste
        # chrome.exe'yi bulup uygulama başlatmak yerine dosya açmaya kalkardı.
        # Bağlamdan gelen ikame "X dosyasını aç" olduğu için bu koşulu sağlar.
        islem = 'ac'
    else:
        islem = 'ara'

    if islem == 'ara' and not arama_var:
        return None

    return {'islem': islem, 'sorgu': sorgu or None, 'secim': secim,
            'hedef': hedef, 'alici': alici, 'tur': tur, 'zayif': not guclu}


def dosya_niyeti_coz(mesaj: str, kanal=MASAUSTU_KANALI):
    """
    Niyet katmanı için: bu cümle GERÇEKTEN bir dosya komutu mu?

    Güçlü sinyalli cümlelerde ("dosya", tür adı, seçim numarası…) doğrudan evet.
    Zayıf sinyalli cümlelerde ("staj raporunu anneme mail at") karar İNDEKSE
    sorulur — eşleşme yoksa None döner ve cümle WhatsApp/e-posta/LLM akışına
    kalır. Karar burada verilir ki güvenlik katmanı doğru niyeti görsün.
    """
    plan = dosya_komutu_ayristir(mesaj)
    if not plan:
        return None
    if not plan['zayif']:
        return plan
    if plan['secim'] is not None:
        return plan
    if not plan['sorgu'] and not plan['tur']:
        return None
    try:
        if file_index.ara(plan['sorgu'] or '', tur=plan['tur'], limit=1):
            return plan
    except Exception as e:
        print(f"[Dosya niyeti] İndeks sorgulanamadı: {e}")
    return None


def _tur_bul(ml: str):
    for tur in _TUR_SOZLUGU:
        if re.search(r'\b' + file_index.sadelestir(tur), ml):
            return tur
    m = re.search(r'\.(\w{2,5})\b', ml)
    return '.' + m.group(1) if m else None


# Sorgudan atılacak komut kelimeleri (dosya adı değiller)
_GURULTU = {
    'dosya', 'dosyayi', 'dosyayı', 'dosyasini', 'dosyasını', 'dosyalari', 'dosyaları',
    'bul', 'ara', 'arar', 'nerede', 'listele', 'goster', 'göster', 'bakar',
    'ac', 'aç', 'acar', 'açar',
    'gonder', 'gönder', 'yolla', 'at', 'ilet', 'paylas', 'paylaş', 'gonderir',
    'bana', 'telefonuma', 'telegram', 'telegrama', 'telegramdan',
    'mail', 'maille', 'mailden', 'maile', 'eposta', 'e-posta', 'epostayla',
    'whatsapp', 'whatsapptan', 'whatsapptan', 'wp', 'wpden', 'uzerinden', 'üzerinden',
    'olarak', 'ile', 'bir', 'tane', 'lutfen', 'lütfen', 'adli', 'adlı', 'isimli',
    'bilgisayarimda', 'bilgisayarımda', 'pcde', 'pcmde', 'hangi', 'nerde',
    'son', 'en', 'yeni', 'ki', 'deki', 'daki', 'var', 'mi', 'mı', 'i', 'ı',
}


def _sorguyu_temizle(metin: str, tur: str = None):
    """Cümleden dosya adı adaylarını çıkarır ('staj raporunu anneme mail at' → 'staj rapor')."""
    # Çift tırnaklı ifade varsa aynen kullan (tek tırnak Türkçe kesme işaretidir!)
    m = re.search(r'"(.+?)"', metin)
    if m:
        return m.group(1).strip()

    ml = file_index.sadelestir(metin)
    tur_sade = file_index.sadelestir(tur or '')
    alici = _alici_cikar(ml)

    tokenlar = []
    for t in re.findall(r"[\wçğıöşü\-.]+", ml):
        if t in _GURULTU or len(t) < 2 or t.isdigit():
            continue
        if t.startswith('dosya') or t.startswith('klasor'):
            continue
        if any(t.startswith(k[:7]) for k in _KLASOR_KELIMELERI):   # "masaustundeki"
            continue
        if tur_sade and t.startswith(tur_sade.lstrip('.')):
            continue
        if alici and t.startswith(alici[:4]):     # "anneme" gibi alıcı ekleri
            continue
        # Türkçe ek kırpma: "raporunu" → "rapor" (LIKE %rapor% zaten geniş eşleşir)
        t = re.sub(r'(unu|ünü|ini|ını|nun|nün|nin|nın|umu|imi|leri|ları|lari|'
                   r'dan|den|tan|ten|deki|daki|de|da)$', '', t)
        if len(t) >= 2 and t not in _GURULTU:
            tokenlar.append(t)
    return ' '.join(tokenlar).strip()


# ---------------------------------------------------------------------------
# GÖNDERİM HEDEFLERİ
# ---------------------------------------------------------------------------
def telegrama_gonder(yol: str, aciklama: str = ''):
    """Dosyayı kullanıcının kendi Telegram sohbetine yollar."""
    from features import telegram_bridge as tg
    cfg = _config()
    token = (cfg.get('telegram_token') or '').strip()
    chat_id = (cfg.get('telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return True, ("⚠️ Telegram yapılandırılmamış. Ayarlar → Telegram Token / Chat ID "
                      "alanlarını doldur.")

    ok, mesaj = tg.send_document(token, chat_id, yol,
                                 caption=aciklama or f"📎 {os.path.basename(yol)}")
    if ok:
        return True, (f"📤 **TELEGRAM'A GÖNDERİLDİ**\n"
                      f"• Dosya: `{os.path.basename(yol)}` "
                      f"({file_index.boyut_yazi(os.path.getsize(yol))})\n"
                      f"• 📁 {os.path.dirname(yol)}")
    return True, f"❌ Telegram'a gönderilemedi: {mesaj}"


def mail_ile_gonder(yol: str, alici: str, konu: str = None, icerik: str = None):
    """Dosyayı e-posta EKİ olarak gönderir."""
    from features.email_control import email_gonder
    ad = os.path.basename(yol)
    return email_gonder(
        alici,
        konu or f"{ad} — ULTRON",
        icerik or f"Merhaba,\n\n'{ad}' dosyası ektedir.\n\n— ULTRON Asistan",
        ek_dosya=yol,
    )


def _panoya_dosya_koy(yol: str) -> bool:
    """
    Dosyayı Windows panosuna DOSYA olarak koyar (CF_HDROP) — Explorer'da
    Ctrl+C ile aynı şey. Böylece WhatsApp'a Ctrl+V ile eklenebilir.
    """
    if sys.platform != 'win32':
        return False
    try:
        import struct
        import win32clipboard
        import win32con
    except ImportError:
        return False

    try:
        # DROPFILES yapısı: 20 baytlık başlık + çift-null biten UTF-16 yol listesi
        # (pFiles=başlık boyutu, pt.x, pt.y, fNC=0, fWide=1 → Unicode yol)
        yollar = os.path.abspath(yol) + '\0\0'
        baslik = struct.pack('<IiiII', 20, 0, 0, 0, 1)
        veri = baslik + yollar.encode('utf-16-le')

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_HDROP, veri)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"[Dosya gönderimi] Pano hatası: {type(e).__name__}: {e}")
        return False


def whatsapp_ile_gonder(yol: str, alici: str):
    """
    Dosyayı WhatsApp'tan gönderir.

    Yöntem (AIP felsefesi — fare yok): dosya panoya DOSYA olarak konur, sohbet
    `whatsapp://send` ile açılır, odak korumalı Ctrl+V ile eklenir, Enter ile
    gönderilir. WhatsApp'ın dosya seçici penceresi hiç açılmaz.
    """
    import urllib.parse
    from core.interaction import level1_native, level4_input
    from features.actions.whatsapp_control import kisi_coz, kisiler_yukle

    numara = kisi_coz(alici)
    if not numara:
        kisiler = kisiler_yukle()
        mevcut = ', '.join(sorted(kisiler)) if kisiler else 'rehber boş'
        return True, (f"⚠️ **'{alici}'** WhatsApp rehberinde yok. (Kayıtlı: {mevcut})\n"
                      f"Eklemek için: `whatsapp kişi ekle: {alici} = 0555 111 22 33`")

    ad = os.path.basename(yol)
    if not _panoya_dosya_koy(yol):
        return True, ("❌ Dosya panoya konamadı (pywin32 gerekli). "
                      "Mail ya da Telegram ile göndermeyi dene.")

    if not level1_native.open_uri(f"whatsapp://send?phone={numara}"):
        return True, "❌ WhatsApp açılamadı. WhatsApp Desktop kurulu mu?"

    # Sohbetin yüklenmesini bekle, sonra odak korumalı yapıştır
    time.sleep(3.0)
    if not level4_input.press_paste(require_title_contains="whatsapp", timeout=15):
        return True, (f"⚠️ WhatsApp öne gelmediği için dosya yapıştırılmadı "
                      f"(güvenlik: yanlış pencereye yapıştırmam).\n"
                      f"`{ad}` panoda hazır — WhatsApp'a geçip Ctrl+V yapabilirsin.")

    # Önizleme penceresi açılsın, sonra gönder
    time.sleep(2.5)
    gonderildi = level4_input.press_enter(require_title_contains="whatsapp", timeout=10)

    if gonderildi:
        return True, (f"📱 **WHATSAPP'A EKLENDİ VE GÖNDERİLDİ**\n"
                      f"• Alıcı: **{alici}** (`{numara}`)\n"
                      f"• Dosya: `{ad}` ({file_index.boyut_yazi(os.path.getsize(yol))})\n"
                      f"• Yöntem: Pano (CF_HDROP) + odak korumalı Ctrl+V → Enter\n"
                      f"• ⚠️ Doğrulama yapılamadı — WhatsApp'tan teyit et.")
    return True, (f"⚠️ Dosya WhatsApp'a eklendi ama Enter gönderilemedi.\n"
                  f"`{ad}` sohbette ekli bekliyor — elle Enter'a basabilirsin.")


# ---------------------------------------------------------------------------
# ANA AKIŞ
# ---------------------------------------------------------------------------
def hedef_dosyayi_coz(plan: dict, kanal=MASAUSTU_KANALI):
    """
    Gönderilecek dosyayı belirler → yol veya None.
    Onay kartında dosya adını gösterebilmek için güvenlik katmanı da bunu kullanır.
    """
    if not plan:
        return None
    if plan['secim'] is not None:
        return file_index.sonuctan_sec(kanal, plan['secim'])
    if plan['sorgu'] or plan['tur']:
        sonuclar = file_index.ara(plan['sorgu'] or '', tur=plan['tur'], limit=2)
        if len(sonuclar) == 1:
            return sonuclar[0]['yol']
    return None


def _dosyayi_ac(plan: dict, kanal, onaylandi: bool = False):
    """
    İndeksteki dosyayı sistemin varsayılan uygulamasıyla açar → (işlendi_mi, yanıt).

    ⚠️ `os.startfile` çalıştırılabilir dosyalarda dosyayı AÇMAZ, ÇALIŞTIRIR.
    Onay verilmediyse bu tür dosyalar açılmaz; güvenlik katmanı onay kartı
    gösterir ve onaylı çağrı `onaylandi=True` ile gelir.
    """
    yol = hedef_dosyayi_coz(plan, kanal)

    if not yol:
        sonuclar = file_index.ara(plan.get('sorgu') or '', tur=plan.get('tur'), limit=10)
        if not sonuclar:
            if plan.get('zayif'):
                return False, None      # dosya komutu değilmiş — çağıran devam etsin
            return True, f"🔍 `{plan.get('sorgu') or plan.get('tur')}` için dosya bulunamadı."
        file_index.son_sonuclari_kaydet(kanal, sonuclar)
        liste = file_index.sonuclari_bicimle(sonuclar, "Birden fazla eşleşme")
        return True, liste + "\n\n❓ Hangisini açayım? (`1'i aç` gibi)"

    if not os.path.exists(yol):
        return True, (f"⚠️ `{os.path.basename(yol)}` artık yerinde değil.\n"
                      f"`dosya indeksini güncelle` dersen listeyi tazelerim.")

    if calistirilabilir_mi(yol) and not onaylandi:
        return True, (f"⛔ `{os.path.basename(yol)}` bir **program**. Açmak onu "
                      f"ÇALIŞTIRMAK demektir — onayın gerekiyor.")

    try:
        if sys.platform == 'win32':
            os.startfile(yol)
        return True, (f"📂 **Açılıyor:** `{os.path.basename(yol)}`\n"
                      f"📁 {os.path.dirname(yol)}")
    except Exception as e:
        return True, f"⚠️ Dosya açılamadı: {e}"


def dosya_komutu_isle(mesaj: str, kanal=MASAUSTU_KANALI, plan: dict = None,
                      onaylandi: bool = False):
    """
    Dosya arama/gönderme/açma komutunu işler → (işlendi_mi, yanıt).
    `kanal`: seçim listesinin kime ait olduğu ('desktop' veya Telegram chat_id).
    `plan`: niyet katmanında zaten ayrıştırıldıysa tekrar ayrıştırma.
    `onaylandi`: kullanıcı onay kartını geçtiyse True (çalıştırılabilir dosya).
    """
    plan = plan or dosya_komutu_ayristir(mesaj)
    if not plan:
        return False, None

    if plan.get('islem') == 'ac':
        return _dosyayi_ac(plan, kanal, onaylandi=onaylandi)

    # --- Seçim numarasıyla gönderim: "2'yi anneme mail at"
    if plan['secim'] is not None:
        yol = file_index.sonuctan_sec(kanal, plan['secim'])
        if not yol:
            return True, ("⚠️ O numarada bir dosya yok. Önce arama yap: "
                          "`staj raporunu bul` gibi.")
        return True, _hedefe_gonder(yol, plan)

    # --- Arama
    sorgu = plan['sorgu']
    if not sorgu and not plan['tur']:
        if plan['zayif']:
            return False, None          # dosya komutu değilmiş — çağıran devam etsin
        return True, ("🔍 Neyi arayayım? Örnek: `staj raporunu bul` · "
                      "`bilgisayarımda cv ara` · `son pdf'leri listele`")

    sayi, son_tarama = file_index.indeks_durumu()
    if not sayi:
        if plan['zayif']:
            return False, None
        return True, ("📇 Dosya indeksi henüz kurulmamış. `dosya indeksini güncelle` "
                      "dersen bilgisayarını tarayıp hangi dosyanın nerede olduğunu öğrenirim.")

    sonuclar = file_index.ara(sorgu or '', tur=plan['tur'], limit=10)
    if not sonuclar:
        # Zayıf sinyalli cümlede eşleşme yoksa bu bir dosya komutu değildi —
        # WhatsApp mesajı / web araması / LLM devralsın.
        if plan['zayif']:
            return False, None
        return True, (f"🔍 `{sorgu or plan['tur']}` için eşleşen dosya bulunamadı.\n"
                      f"(İndekste {sayi:,} dosya var — son tarama: {son_tarama})\n"
                      f"Dosya yeniyse `dosya indeksini güncelle` diyebilirsin.")

    file_index.son_sonuclari_kaydet(kanal, sonuclar)

    # Tek sonuç + hedef belliyse doğrudan gönder
    if plan['hedef'] and len(sonuclar) == 1:
        return True, _hedefe_gonder(sonuclar[0]['yol'], plan)

    if plan['hedef']:
        liste = file_index.sonuclari_bicimle(sonuclar, "Birden fazla eşleşme")
        hedef_ad = {'telegram': 'sana', 'email': f"{plan['alici']}'e mail ile",
                    'whatsapp': f"{plan['alici']}'e WhatsApp'tan"}.get(plan['hedef'], '')
        return True, (liste + f"\n\n❓ Hangisini göndereyim {hedef_ad}? "
                              f"Numarasını söyle (örn. `1'i gönder`).")

    return True, file_index.sonuclari_bicimle(sonuclar, "Bulunan dosyalar")


def _hedefe_gonder(yol: str, plan: dict):
    """Seçilmiş dosyayı plandaki hedefe yollar."""
    if not file_index.dosya_gecerli_mi(yol):
        return ("⚠️ Dosya artık yok ya da gönderilemez (sır taşıyan dosyalar "
                "güvenlik gereği gönderilmez).")

    hedef = plan['hedef'] or 'telegram'   # hedef söylenmediyse kullanıcının kendisine
    if hedef == 'telegram':
        return telegrama_gonder(yol)[1]

    if not plan['alici']:
        return (f"⚠️ Kime göndereyim? Örnek: `1'i anneme mail at` · "
                f"`1'i patrona whatsapp'tan gönder`")

    if hedef == 'email':
        return mail_ile_gonder(yol, plan['alici'])[1]
    if hedef == 'whatsapp':
        return whatsapp_ile_gonder(yol, plan['alici'])[1]
    return "⚠️ Gönderim hedefini anlayamadım (bana / mail / whatsapp)."


# ---------------------------------------------------------------------------
# İNDEKS KOMUTLARI
# ---------------------------------------------------------------------------
def indeks_komutu_algila(mesaj: str):
    """'dosya indeksini güncelle' / 'indeks durumu' komutları → (işlendi_mi, yanıt)"""
    ml = file_index.sadelestir(mesaj)
    if 'indeks' not in ml and 'index' not in ml and 'dosyalari tara' not in ml:
        return False, None

    if any(k in ml for k in ('guncelle', 'yenile', 'tara', 'kur', 'olustur')):
        sayi, sure, gizli = file_index.indeksi_yenile()
        return True, (f"📇 **DOSYA İNDEKSİ GÜNCELLENDİ**\n"
                      f"• {sayi:,} dosya indekslendi ({sure} sn)\n"
                      f"• {gizli} hassas dosya güvenlik gereği atlandı\n"
                      f"Artık `staj raporunu bul` gibi arayabilirsin.")

    sayi, son = file_index.indeks_durumu()
    if not sayi:
        return True, "📇 Dosya indeksi boş. `dosya indeksini güncelle` diyerek kurabilirsin."
    return True, (f"📇 **DOSYA İNDEKSİ**\n• {sayi:,} dosya\n• Son tarama: {son}\n"
                  f"• Taranan: Masaüstü, Belgeler, İndirilenler, Resimler, Müzikler, Videolar")
