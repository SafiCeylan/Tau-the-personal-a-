"""
ULTRON — YERLEŞİK ARAÇLAR

`ExecutionEngineLayer` içindeki if/elif zinciri buraya, isimli araçlara taşındı.

⚠️ DAVRANIŞ BİREBİR KORUNMALI. Eski zincirin iki ayrı "başarısızlık" durumu vardı
ve bunları karıştırmak Ultron'u uydurmaya iter:

    handled=False  → araç üstlenmedi, akış LLM'e düşer   → AracSonuc.islenmedi()
    basarili=False → araç denedi, olmadı (mesajı var)     → AracSonuc.hata(mesaj)

KAYIT SIRASI ÖNEMLİDİR: intent haritasında ilk kaydedilen kazanır. Sıra, eski
if/elif zincirinin sırasıyla aynı tutulmuştur (FILE_SEARCH, SYSTEM_CONTROL'dan
önce gelmeli — yoksa "pdf aç" uygulama açmaya çalışır).

Araç imzası:  fn(metin="", db_cursor=None, db_conn=None, **params) -> AracSonuc
`metin` ham kullanıcı cümlesidir (regex ayrıştırıcılar onu bekler); `params`
planner'ın ürettiği kanonik parametrelerdir ve varsa metne TERCİH EDİLİR.
"""

import re

from core.tools import AracSonuc, arac_kaydet, RISK_GUVENLI, RISK_ONAY
from core.recovery import BULUNAMADI, bulunamadi_mi


from features.actions.system_control import sistem_komutu_algila, medya_kontrol, medya_komutu_algila
from features.actions.whatsapp_control import whatsapp_komutu_algila
from features.briefing import (
    sabah_brifingi_olustur, aksam_raporu_olustur, hava_raporu, doviz_raporu,
)
from features.calendar_tools import takvim_komutu_algila
from features.clipboard_tools import pano_komutu
from features.email_control import email_komutu_algila
from features.file_finder import dosya_bul_ve_islet
from features.actions.ui_click import ekranda_tikla, tiklama_hedefi_coz
from features import screen_context
from features.screen_reader import ekran_komutu
from features.file_reader import dosya_oku_ve_analiz_et, dosya_okuma_niyeti_algila
from features import file_index
from features.file_send import dosya_komutu_isle, indeks_komutu_algila
from features.qa import cevapla_guven_skoru_ile
from features.quick_tools import (
    hesapla, hesap_niyeti_algila, saat_tarih_raporu, sayac_niyeti_algila,
    sayac_kur, not_niyeti_algila, not_ekle, notlari_getir, notlari_sil,
)
from features.reminders import hatirlatma_algila, hatirlatma_kaydet, gecmis_getir
from features.reporting import analiz_raporu_olustur
from features.scheduler import zamanlama_komutu_algila
from features.screenshot_tool import ekran_goruntusu_al
from features.web_search import canli_web_ara


def _dosya_sonucu(cevap: str) -> AracSonuc:
    """
    Dosya araçlarının ortak çıkışı.

    "bulunamadı" mesajı BAŞARILI sayılır (arayüz mesajı göstersin, LLM devreye
    girip uydurmasın) ama `hata_tipi` işaretlenir ki Recovery Engine alternatif
    üretebilsin. İkisi farklı sorular: "araç düzgün çalıştı mı" ve
    "hedefe ulaşıldı mı".
    """
    if bulunamadi_mi(cevap):
        return AracSonuc.ok(cevap, hata_tipi=BULUNAMADI)
    return AracSonuc.ok(cevap)


# =========================================================================
# ZAMANLAMA / İNDEKS / DOSYA
# =========================================================================

@arac_kaydet(
    "gorev_zamanla",
    "Belirli bir saatte çalışacak görev kurar, listeler veya siler.",
    {"metin": "zamanlama cümlesi (örn. 'her sabah 8'de hava durumu')"},
    intent="SCHEDULE_TASK", db_ister=True,
)
def gorev_zamanla(metin="", db_cursor=None, db_conn=None, **_):
    if not (db_cursor and db_conn):
        return AracSonuc.islenmedi()
    islendi, cevap = zamanlama_komutu_algila(metin, db_cursor, db_conn)
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "indeks_yonet",
    "Dosya indeksini günceller veya indeks durumunu raporlar.",
    {"metin": "indeks komutu"},
    intent="FILE_INDEX",
)
def indeks_yonet(metin="", **_):
    islendi, cevap = indeks_komutu_algila(metin)
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "dosya_gonder",
    "Bilgisayarda dosya bulup Telegram/e-posta/WhatsApp ile gönderir.",
    {"metin": "gönderim cümlesi", "kanal": "desktop veya Telegram chat_id"},
    risk=RISK_ONAY, intent="FILE_TRANSFER",
)
def dosya_gonder(metin="", kanal="desktop", plan=None, **_):
    islendi, cevap = dosya_komutu_isle(metin, kanal=kanal, plan=plan)
    return _dosya_sonucu(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "indeks_ara",
    "Dosya indeksinde arar ve eşleşenleri LİSTELER (göndermez, açmaz).",
    {"sorgu": "aranacak dosya adı", "tur": "uzantı (.pdf gibi)"},
)
def indeks_ara(metin="", sorgu=None, tur=None, kanal="desktop", **_):
    """
    Salt-okunur indeks araması.

    Neden ayrı araç: indeks araması `dosya_gonder` içinde gömülüydü ve o araç
    RISK_ONAY olduğu için Recovery Engine onu çalıştıramıyordu (haklı olarak —
    kurtarma dosya göndermemeli). `dosya_ara` ise klasör bazlı `file_finder`'a
    gidiyor, indekse değil. Kurtarmanın "adı gevşetip tekrar ara" adımı bu
    güvenli aracı kullanır.
    """
    hedef = sorgu or metin
    toplam = file_index.sonuc_sayisi(hedef or '', tur=tur)
    sonuclar = file_index.ara(hedef or '', tur=tur, limit=10)
    if not sonuclar:
        return AracSonuc.ok(
            f"🔍 `{hedef or tur}` için eşleşen dosya bulunamadı.",
            hata_tipi=BULUNAMADI,
        )
    file_index.son_sonuclari_kaydet(kanal, sonuclar, sorgu=hedef or '', tur=tur,
                                    offset=0, toplam=toplam)
    return AracSonuc.ok(file_index.sonuclari_bicimle(
        sonuclar, "Bulunan dosyalar", toplam=toplam))


@arac_kaydet(
    "dosya_ac",
    "Bilgisayardaki bir dosyayı varsayılan uygulamasıyla açar (PDF, Word, resim...).",
    {"sorgu": "açılacak dosya adı"},
    risk=RISK_ONAY,   # program çalıştırma riski — planner onaysız yürütemez
)
def dosya_ac(metin="", sorgu=None, kanal="desktop", **_):
    # Planner parametre verdiyse aracın anlayacağı cümleyi kur; regex yolunda
    # ham metin zaten "X dosyasını aç" biçimindedir.
    komut = f"{sorgu} dosyasını aç" if sorgu else metin
    islendi, cevap = dosya_komutu_isle(komut, kanal=kanal)
    return _dosya_sonucu(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "dosya_ara",
    "Bilgisayarda dosya arar ve bulursa gösterir/açar. (Sıra: SYSTEM_CONTROL'dan ÖNCE.)",
    {"sorgu": "aranacak dosya adı/türü"},
    intent="FILE_SEARCH",
)
def dosya_ara(metin="", sorgu=None, **_):
    s = sorgu or metin
    islendi, cevap = dosya_bul_ve_islet(s)
    if islendi:
        return _dosya_sonucu(cevap)
    # Klasör bazlı arama (Downloads vb.) sonuç vermediyse, indeksten genel arama yap
    toplam = file_index.sonuc_sayisi(s or '')
    sonuclar = file_index.ara(s or '', limit=10)
    if sonuclar:
        return AracSonuc.ok(file_index.sonuclari_bicimle(sonuclar, "Bulunan dosyalar", toplam=toplam))
    return AracSonuc.ok(f"🔍 `{s}` için eşleşen dosya bulunamadı.", hata_tipi=BULUNAMADI)


@arac_kaydet(
    "dosya_oku",
    "Bir dosyanın içeriğini okur ve özetler.",
    {"yol": "dosya yolu"},
    intent="FILE_OPERATION",
)
def dosya_oku(metin="", yol=None, **_):
    _var, bulunan = dosya_okuma_niyeti_algila(metin)
    hedef = yol or bulunan
    if not hedef:
        return AracSonuc.islenmedi()
    basarili, cevap = dosya_oku_ve_analiz_et(hedef)
    return AracSonuc(islendi=True, basarili=basarili, mesaj=cevap)


# =========================================================================
# MESAJLAŞMA (riskli — onay katmanı ayrıca devrede)
# =========================================================================

@arac_kaydet(
    "whatsapp_yonet",
    "WhatsApp rehberini yönetir; bilinmeyen alıcıda kullanıcıya sorar.",
    {"metin": "whatsapp cümlesi"},
    risk=RISK_ONAY, intent="WHATSAPP_MESSAGE",
)
def whatsapp_yonet(metin="", **_):
    islendi, cevap = whatsapp_komutu_algila(metin)
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "eposta_yonet",
    "E-posta rehberini yönetir; bilinmeyen alıcıda kullanıcıya sorar.",
    {"metin": "e-posta cümlesi"},
    risk=RISK_ONAY, intent="EMAIL_MESSAGE",
)
def eposta_yonet(metin="", **_):
    islendi, cevap = email_komutu_algila(metin)
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


# =========================================================================
# RAPORLAR
# =========================================================================

@arac_kaydet(
    "sabah_brifingi", "Hava, döviz ve bugünkü hatırlatmaları özetler.",
    intent="MORNING_BRIEFING", db_ister=True,
)
def sabah_brifingi(metin="", db_cursor=None, db_conn=None, **_):
    return AracSonuc.ok(sabah_brifingi_olustur(db_cursor))


@arac_kaydet(
    "aksam_raporu", "Günün özetini ve yarının hatırlatmalarını verir.",
    intent="EVENING_REPORT", db_ister=True,
)
def aksam_raporu(metin="", db_cursor=None, db_conn=None, **_):
    return AracSonuc.ok(aksam_raporu_olustur(db_cursor))


@arac_kaydet(
    "analiz_raporu", "Haftalık kişisel kullanım/ruh hali analizini çıkarır.",
    intent="ANALYSIS_REPORT", db_ister=True,
)
def analiz_raporu(metin="", db_cursor=None, db_conn=None, **_):
    if not db_cursor:
        return AracSonuc.islenmedi()
    try:
        rapor = analiz_raporu_olustur(db_cursor)
    except Exception as e:
        # Eski davranış: hata basılır ve akış LLM'e düşer
        print(f"[Ultron Report] Analiz raporu hatası: {e}")
        return AracSonuc.islenmedi()
    rapor = rapor.replace("<br>", "\n").replace("<b>", "**").replace("</b>", "**")
    return AracSonuc.ok(rapor)


# =========================================================================
# ANLIK VERİ — LLM'e sorulmaz, kaynaktan okunur
# =========================================================================

@arac_kaydet("hava_durumu", "Güncel hava durumunu verir (wttr.in).", intent="WEATHER")
def hava_durumu(metin="", **_):
    try:
        return AracSonuc.ok(hava_raporu())
    except Exception as e:
        print(f"[Ultron Weather] {e}")
        return AracSonuc.islenmedi()


@arac_kaydet("doviz", "Güncel döviz kurlarını verir.", intent="CURRENCY")
def doviz(metin="", **_):
    return AracSonuc.ok(doviz_raporu())


@arac_kaydet(
    "hesap_makinesi", "Matematik ifadesini Python ile hesaplar (LLM tahmin etmez).",
    {"ifade": "hesaplanacak ifade"}, intent="CALCULATOR",
)
def hesap_makinesi(metin="", ifade=None, **_):
    hedef = ifade or hesap_niyeti_algila(metin) or metin
    basarili, cevap = hesapla(hedef)
    return AracSonuc(islendi=True, basarili=basarili, mesaj=cevap)


@arac_kaydet(
    "saat_tarih", "Sistemin gerçek saatini/tarihini söyler.", intent="TIME_DATE",
)
def saat_tarih(metin="", **_):
    basarili, cevap = saat_tarih_raporu(metin)
    return AracSonuc(islendi=True, basarili=basarili, mesaj=cevap)


@arac_kaydet(
    "web_ara", "İnternette arama yapar ve özet döner.",
    {"sorgu": "arama sorgusu"}, intent="WEB_SEARCH",
)
def web_ara(metin="", sorgu=None, **_):
    basarili, cevap = canli_web_ara(sorgu or metin)
    # Eski davranış: başarısızsa üstlenilmez, akış LLM'e düşer
    return AracSonuc.ok(cevap) if basarili else AracSonuc.islenmedi()


# =========================================================================
# HATIRLATMA / SAYAÇ / NOT
# =========================================================================

@arac_kaydet(
    "takvim_yonet",
    "Takvime etkinlik ekler, günün/haftanın programını listeler, etkinlik siler, "
    "dış takvimi (ICS) senkronize eder veya takvimi .ics olarak dışa aktarır.",
    {"metin": "takvim cümlesi (örn. 'takvime yarın 14:00 toplantı ekle')"},
    intent="CALENDAR", db_ister=True,
)
def takvim_yonet(metin="", db_cursor=None, db_conn=None, **_):
    if db_cursor is None:
        return AracSonuc.islenmedi()
    islendi, cevap = takvim_komutu_algila(metin, db_cursor, db_conn)
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "hatirlatma_kur", "Hatırlatma kaydeder veya kayıtlı hatırlatmaları listeler.",
    {"metin": "hatırlatma cümlesi"}, intent="CREATE_REMINDER", db_ister=True,
)
def hatirlatma_kur(metin="", db_cursor=None, db_conn=None, **_):
    kayit = hatirlatma_algila(metin)
    if not kayit:
        return AracSonuc.islenmedi()

    if kayit.get('tip') == 'hatirlatma':
        if db_cursor and db_conn and hatirlatma_kaydet(db_cursor, db_conn, kayit):
            return AracSonuc.ok(
                f"✅ Hatırlatma kaydedildi! '{kayit['metin']}' konusunda "
                f"{kayit.get('detay', '')} hatırlatacağım."
            )
        return AracSonuc.islenmedi()

    if kayit.get('tip') == 'gecmis_takip' and db_cursor:
        satirlar = gecmis_getir(db_cursor)
        if satirlar:
            liste = [f"{i}. {mtn} ({durum})"
                     for i, (mtn, _t, _o, durum) in enumerate(satirlar, 1)]
            return AracSonuc.ok("📅 **KAYITLI HATIRLATMALARINIZ:**\n\n" + "\n".join(liste))
        return AracSonuc.ok("📅 Henüz kayıtlı bir hatırlatmanız bulunmuyor.")

    return AracSonuc.islenmedi()


@arac_kaydet(
    "sayac", "Belirtilen dakika için sayaç kurar.",
    {"dakika": "süre (dakika)"}, intent="TIMER", db_ister=True,
)
def sayac(metin="", dakika=None, db_cursor=None, db_conn=None, **_):
    sure = dakika or sayac_niyeti_algila(metin)
    if not (sure and db_cursor is not None):
        return AracSonuc.islenmedi()
    basarili, cevap = sayac_kur(db_cursor, db_conn, sure)
    return AracSonuc(islendi=True, basarili=basarili, mesaj=cevap)


@arac_kaydet(
    "not_yonet", "Not ekler, notları listeler veya siler.",
    {"islem": "ekle|listele|sil", "icerik": "not metni"},
    intent="NOTE_TAKE", db_ister=True,
)
def not_yonet(metin="", islem=None, icerik=None, db_cursor=None, db_conn=None, **_):
    if db_cursor is None:
        return AracSonuc.islenmedi()

    ayristirma = not_niyeti_algila(metin)
    if ayristirma is None and (icerik or islem):
        ayristirma = (islem or 'ekle', icerik or '')
    if not ayristirma:
        return AracSonuc.islenmedi()

    eylem, cozulen = ayristirma
    if eylem == 'ekle':
        basarili, cevap = not_ekle(db_cursor, db_conn, icerik or cozulen)
    elif eylem == 'listele':
        basarili, cevap = notlari_getir(db_cursor, db_conn)
    else:
        basarili, cevap = notlari_sil(db_cursor, db_conn)
    return AracSonuc(islendi=True, basarili=basarili, mesaj=cevap)


# =========================================================================
# SİSTEM / MEDYA / EKRAN / PANO / ODAK
# =========================================================================

@arac_kaydet(
    "medya_kontrol", "Çalan medyayı duraklatır, devam ettirir, sesi ayarlar veya geçer.",
    {"aksiyon": "playpause|next|prev|ses seviyesi komutu"}, intent="MEDIA_CONTROL",
)
def medya(metin="", aksiyon=None, **_):
    sorgu = aksiyon or metin or ""
    if any(k in sorgu.lower() for k in ["ses", "%", "yüzde", "seviye", "volume"]):
        islendi, cevap = sistem_komutu_algila(metin or (f"sesi {sorgu} yap" if "ses" not in sorgu.lower() else sorgu))
        if islendi:
            return AracSonuc.ok(cevap)
    hedef = aksiyon or medya_komutu_algila(metin) or "playpause"
    basarili, cevap = medya_kontrol(hedef)
    return AracSonuc(islendi=True, basarili=basarili, mesaj=cevap)


@arac_kaydet(
    "uygulama_calistir",
    "Sistem komutu çalıştırır: uygulama aç/kapat, ses seviyesi ayarla, müzik çal, sistem bilgilerini göster.",
    {"metin": "doğal dil komutu (örn. 'chrome aç', 'sesi %50 yap', 'sistem bilgileri', 'spotify kapat')"},
    intent=("SYSTEM_CONTROL", "SET_VOLUME", "PLAY_MUSIC"),
)
def uygulama_calistir(metin="", uygulama=None, sarki=None, **_):
    import time
    # Planner/LLM kanonik parametre verdiyse regex'in anlayacağı komuta çevir.
    if sarki:
        komut = f"{sarki} çal"
    elif uygulama:
        komut = f"{uygulama} aç"
    else:
        komut = metin
    islendi, cevap = sistem_komutu_algila(komut)
    if islendi and cevap and ("başlatılıyor" in cevap or "açılıyor" in cevap):
        time.sleep(1.2)  # Uygulamanın penceresini açıp odağı alması için bekleme
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet("ekran_goruntusu", "Ekran görüntüsü alır.", intent="SCREENSHOT")
def ekran_goruntusu(metin="", **_):
    yol, cevap = ekran_goruntusu_al()
    if yol:
        return AracSonuc.ok(cevap, screenshot_path=yol)
    return AracSonuc.hata(cevap)


@arac_kaydet(
    "ekranda_sec",
    "Ekran okumasındaki numaralı öğeyi açar ('3'ü aç', 'ikinciyi aç').",
    {"metin": "seçim komutu"},
    risk=RISK_ONAY,   # kullanıcı adına tıklar
    intent="SCREEN_SELECT",
)
def ekranda_sec_araci(metin="", **_):
    referans = screen_context.secim_referansi_coz(metin)
    if not referans:
        return AracSonuc.islenmedi()

    oge, hata = screen_context.ogeyi_sec(referans, screen_context.VARSAYILAN_KANAL)
    if hata:
        return AracSonuc.ok(f"🤔 {hata}")

    from core.interaction import level3_ocr
    x, y = oge['merkez']
    sonuc = level3_ocr.noktaya_tikla(x, y, oge['baslik'])
    if sonuc.success:
        return AracSonuc.ok(f"🖱️ **{oge['sira']}. {oge['baslik'][:60]}** açılıyor.")
    return AracSonuc.ok(f"⚠️ **{oge['baslik'][:60]}** açılamadı — {sonuc.message}")


@arac_kaydet(
    "ekranda_tikla", "Ekranda adı verilen düğmeye tıklar (önce UIA, olmazsa OCR).",
    {"metin": "tıklama komutu"},
    risk=RISK_ONAY,   # kullanıcı adına düğmeye basar — planner tek başına tetikleyemez
    intent="SCREEN_CLICK",
)
def ekranda_tikla_araci(metin="", hedef=None, **_):
    secilen = hedef or tiklama_hedefi_coz(metin) or (metin.strip() if metin else None)
    if not secilen:
        return AracSonuc.islenmedi()
    islendi, cevap = ekranda_tikla(secilen)
    return AracSonuc.ok(cevap) if islendi else AracSonuc.islenmedi()


@arac_kaydet(
    "ekrani_oku", "Ekrandaki yazıyı OCR ile okur; özetler, açıklar veya içinde arar.",
    {"metin": "ekran okuma komutu"}, intent="SCREEN_READ",
)
def ekrani_oku_araci(metin="", **_):
    sonuc = ekran_komutu(metin)
    if not sonuc:
        return AracSonuc.islenmedi()
    if sonuc['tip'] == 'direct':
        return AracSonuc.ok(sonuc['sonuc'])
    # 'ai' → okunan metin LLM'e akmalı: üstlenilmez ama bağlama veri bırakılır.
    # Bulut sağlayıcıya GÖNDERİLMEZ — kararı PromptGeneratorLayer verir.
    return AracSonuc(
        islendi=False, basarili=False,
        veri={'ekran_icerik': sonuc['icerik'], 'ekran_gorev': sonuc['gorev'],
              'ekran_kaynak': sonuc.get('baslik', '')},
    )


@arac_kaydet(
    "pano_isle", "Panodaki metni okur, özetler, çevirir veya açıklar.",
    {"metin": "pano komutu"}, intent="CLIPBOARD",
)
def pano_isle(metin="", **_):
    sonuc = pano_komutu(metin)
    if not sonuc:
        return AracSonuc.islenmedi()
    if sonuc['tip'] == 'direct':
        return AracSonuc.ok(sonuc['sonuc'])
    # 'ai' → içerik LLM'e akmalı: üstlenilmez ama bağlama veri bırakılır
    return AracSonuc(
        islendi=False, basarili=False,
        veri={'pano_icerik': sonuc['icerik'], 'pano_gorev': sonuc['gorev']},
    )


@arac_kaydet(
    "odak_modu", "Pomodoro odak modunu başlatır, durdurur veya durumunu söyler.",
    {"aksiyon": "start|cancel|status", "dakika": "süre"}, intent="FOCUS_MODE",
)
def odak_modu(metin="", aksiyon=None, dakika=None, **_):
    kucuk = (metin or "").lower()
    if aksiyon:
        eylem = aksiyon
    elif any(k in kucuk for k in ['iptal', 'durdur', 'bitir', 'kapat']):
        eylem = 'cancel'
    elif any(k in kucuk for k in ['durum', 'kaldı', 'ne kadar']):
        eylem = 'status'
    else:
        eylem = 'start'

    veri = {'focus_action': eylem}
    if eylem == 'start':
        if not dakika:
            eslesme = re.search(r'(\d+)\s*(?:dakika|dk)', kucuk)
            dakika = int(eslesme.group(1)) if eslesme else 25
        veri['focus_minutes'] = int(dakika)
    # Asıl zamanlayıcı UI tarafında kurulur; mesaj orada ezilir.
    return AracSonuc.ok("🎯 Odak modu isteği alındı.", **veri)


@arac_kaydet(
    "klavye_tusu",
    "Klavyeden tuş basar veya tuş kombinasyonu/metin gönderir (ctrl+enter, enter, alt+f4, 1234 enter vb.).",
    {"metin": "tuş kombinasyonu veya yazılacak metin"},
    intent="KEYBOARD_INPUT",
)
def klavye_tusu(metin="", **_):
    from core.interaction import level4_input
    basarili, cevap = level4_input.send_keyboard_input(metin)
    return AracSonuc.ok(cevap) if basarili else AracSonuc.hata(cevap)


@arac_kaydet(
    "ogrenme_raporu",
    "Geçmiş sohbetlerden öğrenilen alışkanlıkları raporlar, alışkanlığa dayalı "
    "öneri sunar/uygular veya yanlış öğrenilmiş bir kalıbı unutur "
    "('ne öğrendin', 'önerilerin', '1. öneriyi uygula', 'şunu unut: ...').",
    {"metin": "kullanıcının cümlesi"}, intent="LEARNING_REPORT", db_ister=True,
)
def ogrenme_raporu_arac(metin="", db_cursor=None, db_conn=None, **_):
    from features import chat_learning, suggestions
    komut = chat_learning.ogrenme_komutu_algila(metin or "")
    islem = (komut or {}).get('islem')
    hedef = (komut or {}).get('hedef', '')

    if islem == 'unut':
        return AracSonuc.ok(chat_learning.unut(hedef))
    if islem == 'oneri':
        return AracSonuc.ok(suggestions.oneri_metni(db_cursor=db_cursor))
    if islem == 'oneri_kabul':
        return AracSonuc.ok(suggestions.kabul_et(hedef, db_cursor=db_cursor,
                                                 db_conn=db_conn))
    if islem == 'oneri_red':
        return AracSonuc.ok(suggestions.reddet(hedef, db_cursor=db_cursor))

    # Niyet katmanı bu aracı yalnızca komut tanındığında çağırır; yine de
    # doğrudan (planner/test) çağrılabildiği için varsayılan rapordur.
    # Öneriler rapora eklenir: keşif tek bir komuta bağlı kalmasın.
    return AracSonuc.ok(chat_learning.ogrenme_raporu() +
                        suggestions.rapor_eki(db_cursor=db_cursor))


# =========================================================================
# ÖĞRENİLMİŞ CEVAP (en sonda — LLM'e düşmeden önceki son durak)
# =========================================================================

@arac_kaydet(
    "ogrenilmis_cevap",
    "Daha önce öğretilmiş soru-cevapları yüksek güvenle yanıtlar.",
    intent="GENERAL_CONVERSATION", db_ister=True,
)
def ogrenilmis_cevap(metin="", db_cursor=None, db_conn=None, **_):
    if not db_cursor:
        return AracSonuc.islenmedi()
    try:
        cevap, skor = cevapla_guven_skoru_ile(db_cursor, metin)
    except Exception as e:
        print(f"[Ultron QA] Soru-cevap eşleşme hatası: {e}")
        return AracSonuc.islenmedi()
    if skor >= 85:
        return AracSonuc.ok(cevap)
    return AracSonuc.islenmedi()
