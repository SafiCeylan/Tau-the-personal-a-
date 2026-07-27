"""
E-posta Kontrolü — Gmail SMTP üzerinden onay kartlı gönderim.

Komutlar:
  annem'e mail gönder: naber nasılsın                → konu otomatik
  annem'e mail gönder: Toplantı | yarın 14:00'te     → "|" öncesi konu, sonrası içerik
  mail kişi ekle: annem = ornek@gmail.com
  mail kişileri listele
  mail kişi sil: annem

SMTP ayarları config.json'dan okunur (Ayarlar sayfasından girilir):
  smtp_user  → Gmail adresi
  smtp_pass  → Gmail UYGULAMA ŞİFRESİ (normal şifre değil!)
Rehber user_data.json içinde "email_kisiler" anahtarında tutulur.
"""

import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import Header

from core.paths import veri_yolu

USER_DATA_PATH = veri_yolu('user_data.json')
CONFIG_PATH = veri_yolu('config.json')

EMAIL_KEY = 'email_kisiler'
VARSAYILAN_KONU = 'ULTRON Asistan Mesajı'

_FIILLER = ('gönder', 'yolla', 'at', 'yaz')
_NOISE = {'tan', 'dan', 'ten', 'den', 'üzerinden', 'mail', 'maili', 'eposta', 'e-posta', 'bir'}
_EMAIL_RE = re.compile(r'^[\w.+-]+@[\w-]+\.[\w.-]+$')


# ---------------------------------------------------------------------------
# Yapılandırma & Rehber
# ---------------------------------------------------------------------------
def _smtp_ayarlari():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        return (cfg.get('smtp_user') or '').strip(), (cfg.get('smtp_pass') or '').strip()
    except Exception:
        return '', ''


def _user_data_yukle() -> dict:
    try:
        with open(USER_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _user_data_kaydet(data: dict):
    with open(USER_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def email_kisiler() -> dict:
    kisiler = _user_data_yukle().get(EMAIL_KEY, {})
    return kisiler if isinstance(kisiler, dict) else {}


def email_kisi_ekle(isim: str, adres: str):
    isim = isim.lower().strip()
    adres = adres.strip()
    if not isim:
        return True, "⚠️ Kişi adı boş olamaz."
    if not _EMAIL_RE.match(adres):
        return True, f"⚠️ '{adres}' geçerli bir e-posta adresi değil."
    data = _user_data_yukle()
    kisiler = data.get(EMAIL_KEY, {})
    kisiler[isim] = adres
    data[EMAIL_KEY] = kisiler
    _user_data_kaydet(data)
    return True, f"✅ **E-posta rehberine eklendi:** {isim} → `{adres}`"


def email_kisi_sil(isim: str):
    isim = isim.lower().strip()
    data = _user_data_yukle()
    kisiler = data.get(EMAIL_KEY, {})
    if isim in kisiler:
        del kisiler[isim]
        data[EMAIL_KEY] = kisiler
        _user_data_kaydet(data)
        return True, f"🗑️ **{isim}** e-posta rehberinden silindi."
    return True, f"⚠️ '{isim}' e-posta rehberinde bulunamadı."


def email_kisileri_listele():
    kisiler = email_kisiler()
    if not kisiler:
        return True, ("📧 E-posta rehberi boş.\n"
                      "Eklemek için: `mail kişi ekle: annem = ornek@gmail.com`")
    lines = [f"• **{isim}** → `{adres}`" for isim, adres in sorted(kisiler.items())]
    return True, "📧 **E-POSTA REHBERİ:**\n\n" + "\n".join(lines)


def email_coz(alici: str):
    """Alıcı adını/adresini çözer → e-posta adresi veya None.

    Rehberde yoksa TAKMA AD katmanına sorulur ("patronum" → "Ahmet Kaya").
    ⚠️ Rehberdeki doğrudan kayıt her zaman önce gelir."""
    key = (alici or '').lower().strip()
    kisiler = email_kisiler()
    if key in kisiler:
        return kisiler[key]
    if _EMAIL_RE.match(key):
        return key

    try:
        from core.aliases import takma_adi_coz
        gercek = takma_adi_coz(key)
        if gercek:
            gercek_key = gercek.lower().strip()
            if gercek_key in kisiler:
                return kisiler[gercek_key]
            if _EMAIL_RE.match(gercek_key):
                return gercek_key
    except Exception as e:
        print(f"[Ultron TakmaAd] E-posta çözümü atlandı: {e}")

    return None


# ---------------------------------------------------------------------------
# Komut Ayrıştırma
# ---------------------------------------------------------------------------
def _email_gecinor_mu(ml: str) -> bool:
    return re.search(r'\b(mail|e-posta|eposta)\b', ml) is not None


def email_gonderim_ayristir(mesaj: str):
    """
    Gönderim komutunu ayrıştırır → (alici, konu, icerik) veya None.
    "annem'e mail gönder: Konu Başlığı | içerik metni"
    "annem'e mail gönder: sadece içerik"  (konu varsayılan olur)
    """
    ml = mesaj.lower().strip()
    if not _email_gecinor_mu(ml):
        return None
    if not any(f in ml for f in _FIILLER):
        return None
    if 'kişi' in ml:
        return None

    m = re.search(r'\b(?:gönder|yolla|at|yaz)\s*:\s*(.+)$', mesaj, re.IGNORECASE | re.DOTALL)
    if m:
        govde = m.group(1).strip()
        once = mesaj[:m.start()]
    else:
        once, sep, govde = mesaj.partition(':')
        if not sep:
            return None
        govde = govde.strip()
    if not govde:
        return None

    # "Konu | içerik" ayrımı
    if '|' in govde:
        konu, _, icerik = govde.partition('|')
        konu, icerik = konu.strip(), icerik.strip()
        if not icerik:
            icerik, konu = konu, VARSAYILAN_KONU
    else:
        konu, icerik = VARSAYILAN_KONU, govde

    once_l = once.lower()
    alici = None
    m = re.search(r"([\w.+\-@ ]{2,}?)['’](?:e|a|ye|ya)\b", once_l)
    if m:
        alici = m.group(1).strip()
    else:
        m = re.search(r"\b(?:gönder|yolla|at|yaz)\s+([\w.+\-@ ]+)$", once_l)
        if m:
            alici = m.group(1).strip()
    if not alici:
        return None

    alici = ' '.join(t for t in alici.split() if t not in _NOISE).strip()
    if not alici:
        return None

    return alici, konu, icerik


# ---------------------------------------------------------------------------
# Gönderim (Level 1 — Native SMTP, arayüz yok, fare yok)
# ---------------------------------------------------------------------------
def email_gonder(alici: str, konu: str, icerik: str, ek_dosya: str = None):
    """Mail gönderir. `ek_dosya` verilirse dosyayı ek olarak iliştirir (Gmail sınırı 25 MB)."""
    adres = email_coz(alici)
    if not adres:
        kisiler = email_kisiler()
        mevcut = ', '.join(sorted(kisiler)) if kisiler else 'rehber boş'
        return True, (f"⚠️ **'{alici}'** e-posta rehberinde bulunamadı. (Kayıtlı: {mevcut})\n"
                      f"Eklemek için: `mail kişi ekle: {alici} = ornek@gmail.com`")

    smtp_user, smtp_pass = _smtp_ayarlari()
    if not smtp_user or not smtp_pass:
        return True, ("⚠️ **SMTP yapılandırılmamış.** Ayarlar sayfasından Gmail adresinizi ve "
                      "**uygulama şifrenizi** girin.\n"
                      "Uygulama şifresi almak için: Google Hesabı → Güvenlik → 2 Adımlı Doğrulama → "
                      "Uygulama şifreleri")

    ek_notu = ""
    try:
        if ek_dosya:
            if not os.path.isfile(ek_dosya):
                return True, f"⚠️ Ek dosya bulunamadı: `{ek_dosya}`"
            boyut = os.path.getsize(ek_dosya)
            if boyut > 24 * 1024 * 1024:
                return True, (f"⚠️ Dosya {boyut / 1024 / 1024:.0f} MB — Gmail eki 25 MB ile sınırlı. "
                              f"Daha küçük bir dosya seç ya da bulut bağlantısı gönder.")

            msg = MIMEMultipart()
            msg.attach(MIMEText(icerik, 'plain', 'utf-8'))
            with open(ek_dosya, 'rb') as f:
                parca = MIMEApplication(f.read(), Name=os.path.basename(ek_dosya))
            # Türkçe/boşluklu dosya adları bozulmasın diye RFC2231 kodlaması
            parca.add_header('Content-Disposition', 'attachment',
                             filename=('utf-8', '', os.path.basename(ek_dosya)))
            msg.attach(parca)
            ek_notu = (f"\n• Ek: `{os.path.basename(ek_dosya)}` "
                       f"({boyut / 1024 / 1024:.1f} MB)")
        else:
            msg = MIMEText(icerik, 'plain', 'utf-8')

        msg['Subject'] = Header(konu, 'utf-8')
        msg['From'] = smtp_user
        msg['To'] = adres

        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=60) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [adres], msg.as_string())

        return True, (f"📧 **E-POSTA GÖNDERİLDİ**\n"
                      f"• Alıcı: **{alici}** (`{adres}`)\n"
                      f"• Konu: {konu}{ek_notu}\n"
                      f"• Yöntem: SMTP (Level 1 — Native API)")
    except smtplib.SMTPAuthenticationError:
        return True, ("❌ **SMTP giriş hatası:** Gmail adresi veya uygulama şifresi yanlış.\n"
                      "Not: Normal Gmail şifresi ÇALIŞMAZ — uygulama şifresi gerekir.")
    except Exception as e:
        return True, f"❌ E-posta gönderilemedi: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Ana Komut Algılayıcı
# ---------------------------------------------------------------------------
def email_komutu_algila(mesaj: str):
    """E-posta komutlarını algılar → (işlendi_mi, yanıt); işlenmediyse (False, None)."""
    ml = mesaj.lower().strip()
    if not _email_gecinor_mu(ml):
        return False, None

    m = re.search(r'kişi\s+ekle\s*:\s*(.+?)\s*=\s*(.+)$', mesaj, re.IGNORECASE)
    if m:
        return email_kisi_ekle(m.group(1), m.group(2))

    m = re.search(r'kişi\s+sil\s*:\s*(.+)$', mesaj, re.IGNORECASE)
    if m:
        return email_kisi_sil(m.group(1))

    if 'kişi' in ml and any(k in ml for k in ['listele', 'göster', 'liste']):
        return email_kisileri_listele()
    if ml in ('mail kişiler', 'mail rehber', 'mail rehberi', 'eposta rehberi', 'e-posta rehberi'):
        return email_kisileri_listele()

    parsed = email_gonderim_ayristir(mesaj)
    if parsed:
        return email_gonder(*parsed)

    # E-postayla ilgili gönderim isteği ama çözülemedi → LLM'e düşürme, rehber göster
    if any(f in ml for f in _FIILLER):
        return True, ("⚠️ E-posta komutunu tam çözemedim. Şu biçimlerden birini kullan:\n"
                      "• `annem'e mail gönder: iyi akşamlar`\n"
                      "• `annem'e mail gönder: Konu Başlığı | mesaj içeriği`\n"
                      "• Rehber: `mail kişi ekle: annem = ornek@gmail.com`")

    return False, None
