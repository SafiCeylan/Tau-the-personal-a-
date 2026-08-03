# -*- coding: utf-8 -*-
"""
ULTRON ÖNERİ MOTORU — öğrenilen örüntüyü kullanıcıya SORU olarak geri verir.

NEDEN VAR
    Öğrenme katmanı (`features/chat_learning.py`) alışkanlıkları çıkarıyordu
    ama çıktısı bir RAPORDA kalıyordu: "her sabah 08:00'de hava durumu sordun,
    12 kez". Kullanıcının bunu kendi eliyle zamanlanmış göreve çevirmesi
    gerekiyordu. Öğrenmenin işe dönüştüğü yer burası.

EN ÖNEMLİ KURAL — ÖNERİ KENDİLİĞİNDEN UYGULANMAZ
    Bu modül hiçbir şeyi kurmaz; SORAR. Uygulama yalnızca kullanıcı açıkça
    "kabul et" dediğinde olur. Gerekçesi projedeki diğer yasaklarla aynı:
    sessiz uygulanan yanlış bir çıkarım, kullanıcının fark edemeyeceği bir
    hatadır (bkz. `aliases.py` bulanık eşleşme yasağı, `chat_learning`
    "öğrenilen kalıp sessiz olamaz").

DİĞER KURALLAR
    • REDDEDİLEN ÖNERİ GERİ GELMEZ. Kalıcı olarak kaydedilir. Aynı şeyi tekrar
      sormak asistanı dırdıra çevirir; kullanıcı da bir daha okumaz.
    • ZATEN KURULU OLAN ÖNERİLMEZ. Görev/kısayol listesi her üretimde kontrol
      edilir. Doğrulayamıyorsak (cursor yoksa) o tip öneri HİÇ üretilmez —
      "belki vardır" ile öneri sunmak kullanıcıya ikinci bir kopya kurdurur.
    • YALNIZCA GERİ ALINABİLİR EYLEM. Üretilen iki tip de tek komutla geri
      alınır (`zamanlama sil: N`, `kısayol sil: X`). Mesaj gönderen hiçbir
      niyet öneriye dönüşmez — beyaz liste `chat_learning.OGRENILEBILIR_INTENTLER`
      ile paylaşılır, iki ayrı liste tutulmaz.
    • SAYI, GÖSTERİLEN SIRADIR. "2. öneriyi uygula" en son GÖSTERİLEN listeye
      göre çözülür (`son_liste`); üretim sırası değişirse yanlış öneri kurulur.
      Aynı ders `file_send` sayfalamasında yaşandı: sessiz ve tehlikeli.
    • AKIŞI KIRMAZ. Her public fonksiyon kendi hatasını yutar.
"""

import json
import os
import re
from datetime import datetime

from core.paths import veri_dizini
from features import chat_learning

_DOSYA_ADI = "oneriler.json"

# Bir alışkanlığın öneriye dönüşmesi için gereken gözlem. Örüntü eşiğinden
# (MIN_ORUNTU_GOZLEM = 3) YÜKSEK: rapora bir satır yazmak ile her gün çalışacak
# bir görev kurmak aynı kanıtı hak etmiyor.
MIN_GOZLEM = 5
AZAMI_ONERI = 3          # bir seferde gösterilen öneri sayısı
AZAMI_KISAYOL_UZUNLUK = 60

# Zamanlanmış göreve çevrilebilecek niyetler: kendi kendine yeten, argümansız,
# çıktısı bir RAPOR olan komutlar. "müzik çal" burada yok — kullanıcı uyanmadan
# müzik başlatmak istenmeyen bir yan etkidir.
ZAMANLANABILIR = {
    'MORNING_BRIEFING': 'sabah brifingi',
    'EVENING_REPORT': 'akşam raporu',
    'WEATHER': 'hava durumu',
    'CURRENCY': 'dolar kaç',
    'ANALYSIS_REPORT': 'analiz raporu',
}


# ---------------------------------------------------------------------------
# DURUM (kabul/red kayıtları)
# ---------------------------------------------------------------------------
def _dosya_yolu() -> str:
    """Testler bu fonksiyonu yamalar — modül sabiti KULLANMA."""
    return os.path.join(veri_dizini(), _DOSYA_ADI)


def _durum_yukle() -> dict:
    try:
        yol = _dosya_yolu()
        if not os.path.exists(yol):
            return {'karar': {}, 'son_liste': []}
        with open(yol, 'r', encoding='utf-8') as f:
            veri = json.load(f)
        if not isinstance(veri, dict):
            return {'karar': {}, 'son_liste': []}
        veri.setdefault('karar', {})
        veri.setdefault('son_liste', [])
        return veri
    except Exception as e:
        print(f"[ULTRON Oneri] Durum okunamadi: {e}")
        return {'karar': {}, 'son_liste': []}


def _durum_kaydet(veri: dict) -> bool:
    try:
        with open(_dosya_yolu(), 'w', encoding='utf-8') as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ULTRON Oneri] Durum yazilamadi: {e}")
        return False


def _karar_yaz(oneri_id: str, durum: str) -> None:
    veri = _durum_yukle()
    veri['karar'][oneri_id] = {
        'durum': durum,
        'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    _durum_kaydet(veri)


# ---------------------------------------------------------------------------
# ÜRETİM
# ---------------------------------------------------------------------------
def oneriler(db_cursor=None, zorla: bool = False) -> list:
    """
    Örüntülerden üretilmiş, henüz karara bağlanmamış öneriler.

    `db_cursor` yoksa zamanlama önerisi ÜRETİLMEZ: mevcut görevlerle
    karşılaştırılamayan bir öneri, zaten kurulu olanı tekrar kurdurabilir.
    """
    try:
        veri = chat_learning.oruntuler(zorla=zorla)
        kararlar = _durum_yukle()['karar']
        mevcut = _mevcut_gorevler(db_cursor) if db_cursor is not None else None
        zamanlama = _zamanlama_onerileri(veri, mevcut)

        # Aynı komut için hem "her gün kurayım mı" hem "kısayol yapayım mı"
        # sormak iki ayrı iş değil, aynı ihtiyacın iki hâlidir. Zamanlama daha
        # güçlü çözüm olduğu için kısayol önerisi elenir.
        # KURULMUŞ görev de kapsar: kullanıcı az önce günlük görevi kurduysa
        # aynı komut için kısayol sormak, karara bağlanmış bir konuyu tekrar
        # açmaktır (öneri bir kez sorulur).
        kapsanan = {o['intent'] for o in zamanlama}
        if mevcut is not None:
            kapsanan |= {i for i, k in ZAMANLANABILIR.items()
                         if chat_learning.sadelestir(k) in mevcut}
        kisayol = [o for o in _kisayol_onerileri(veri)
                   if o['intent'] not in kapsanan]

        temiz = [o for o in zamanlama + kisayol if o['id'] not in kararlar]
        temiz.sort(key=lambda o: o['sayi'], reverse=True)
        return temiz[:AZAMI_ONERI]
    except Exception as e:
        print(f"[ULTRON Oneri] Uretilemedi: {e}")
        return []


def _zamanlama_onerileri(veri: dict, mevcut) -> list:
    """
    "Sabahları hep hava soruyorsun" → "08:00'e kurayım mı?".

    `mevcut` None ise (veritabanına ulaşılamadı) öneri ÜRETİLMEZ: kurulu
    görevlerle karşılaştıramadığımız bir öneri ikinci kopya kurdurur.
    """
    if mevcut is None:
        return []

    sonuc = []
    for z in veri.get('zaman') or []:
        intent = z.get('intent')
        komut = ZAMANLANABILIR.get(intent)
        saat = z.get('saat')
        if not komut or saat is None or z.get('sayi', 0) < MIN_GOZLEM:
            continue
        if chat_learning.sadelestir(komut) in mevcut:
            continue                      # zaten kurulu — sorma
        saat_metni = f"{int(saat):02d}:00"
        sonuc.append({
            'id': f"zamanlama:{intent}:{int(saat):02d}",
            'tip': 'zamanlama',
            'intent': intent,
            'sayi': z['sayi'],
            'baslik': f"Her gün {saat_metni}'de \"{komut}\" çalıştırayım mı?",
            'gerekce': (f"{z['dilim'].capitalize()} saatlerinde "
                        f"{chat_learning._intent_turkce(intent)} istemişsin "
                        f"({z['sayi']} kez, %{int(z.get('pay', 0) * 100)})"),
            'eylem': {'tip': 'zamanlama', 'saat': saat_metni, 'komut': komut},
        })
    return sonuc


def _mevcut_gorevler(db_cursor):
    """
    Kurulu günlük görevlerin komutları. Okunamazsa None döner.

    "Bilmiyorum" ile "hiç yok" aynı şey DEĞİL: hata hâlinde boş küme dönersek
    zaten kurulu olan görevi tekrar öneririz.
    """
    try:
        db_cursor.execute("SELECT komut FROM zamanli_gorevler WHERE aktif = 1")
        return {chat_learning.sadelestir(satir[0] or '') for satir in db_cursor.fetchall()}
    except Exception as e:
        print(f"[ULTRON Oneri] Gorev listesi okunamadi: {e}")
        return None


def _kisayol_onerileri(veri: dict) -> list:
    """Aynı cümleyi tekrar tekrar yazıyorsan tek tuşa bağlanabilir."""
    try:
        from features import custom_shortcuts
        mevcut = {chat_learning.sadelestir(k): True
                  for k in custom_shortcuts.yukle().values()}
    except Exception as e:
        print(f"[ULTRON Oneri] Kisayollar okunamadi: {e}")
        return []

    sonuc, karsilanan = [], set()
    for k in veri.get('sik_komut') or []:
        intent = k.get('intent')
        # Beyaz liste ORTAK: mesaj gönderen / tuş basan niyetler burada da yok.
        if intent not in chat_learning.OGRENILEBILIR_INTENTLER:
            continue
        if k.get('sayi', 0) < MIN_GOZLEM:
            continue
        # Aynı iş için tek öneri. Canlı testte "Ekran görüntüsü" (49 kez) ve
        # "ekran görüntüsü al" (17 kez) iki ayrı kısayol olarak sunuldu —
        # aynı şeyin iki söyleyişi. Liste sayıya göre sıralı geldiği için
        # en sık kullanılan söyleyiş kazanır.
        if intent in karsilanan:
            continue
        # Geri oynatılacak metin ORİJİNAL olmalı; `sade` ASCII'ye indirgenmiştir
        # ve Türkçe harfle yazılı niyet regex'lerine eşleşmez.
        komut = (k.get('ornek') or '').strip()
        if not komut or len(komut) > AZAMI_KISAYOL_UZUNLUK:
            continue
        if chat_learning.sadelestir(komut) in mevcut:
            continue
        karsilanan.add(intent)
        sonuc.append({
            'id': f"kisayol:{k['komut']}",
            'tip': 'kisayol',
            'intent': intent,
            'sayi': k['sayi'],
            'baslik': f"\"{komut}\" için kısayol oluşturayım mı?",
            'gerekce': f"Bu komutu {k['sayi']} kez yazmışsın",
            'eylem': {'tip': 'kisayol', 'ad': _kisayol_adi(komut), 'komut': komut},
        })
    return sonuc


def _kisayol_adi(komut: str) -> str:
    """Buton etiketi: ilk üç kelime. Emoji öneki `custom_shortcuts` geleneği."""
    kelimeler = re.findall(r'\w+', komut, flags=re.UNICODE)[:3]
    etiket = " ".join(w.capitalize() for w in kelimeler) or "Kısayol"
    return f"⚡ {etiket}"


# ---------------------------------------------------------------------------
# SUNUM
# ---------------------------------------------------------------------------
def _listeyi_isaretle(liste: list) -> None:
    """
    Gösterilen sırayı kaydeder — "2. öneriyi uygula" bunun üzerinden çözülür.

    Üretim sırası arşiv değiştikçe kayabilir; numarayı yeniden üretilen listeye
    uygulamak SESSİZCE yanlış öneriyi kurar.
    """
    veri = _durum_yukle()
    veri['son_liste'] = [o['id'] for o in liste]
    _durum_kaydet(veri)


def oneri_metni(db_cursor=None) -> str:
    """Kullanıcıya gösterilecek numaralı öneri listesi."""
    try:
        liste = oneriler(db_cursor=db_cursor, zorla=True)
        if not liste:
            return ("💡 Şu an önerim yok. Alışkanlıkların netleştikçe "
                    f"({MIN_GOZLEM}+ tekrar) buradan söylerim.")
        _listeyi_isaretle(liste)
        p = ["💡 **ÖNERİLERİM** — gözlediğim alışkanlıklardan\n"]
        for i, o in enumerate(liste, 1):
            p.append(f"**{i}.** {o['baslik']}\n   _{o['gerekce']}_")
        p.append("\n`1. öneriyi uygula` · `1. öneriyi reddet`"
                 "\n_Reddedileni bir daha sormam._")
        return "\n".join(p)
    except Exception as e:
        return f"⚠️ Öneriler getirilemedi: {e}"


def rapor_eki(db_cursor=None) -> str:
    """
    Öğrenme raporunun sonuna eklenen kısa öneri bölümü.

    Öneriler burada da görünür, çünkü keşif tek bir komuta bağlı kalmamalı:
    kullanıcı "ne öğrendin" derken zaten öğrenme katmanına bakıyordur.
    """
    try:
        liste = oneriler(db_cursor=db_cursor)
        if not liste:
            return ""
        _listeyi_isaretle(liste)
        p = ["\n\n💡 **ÖNERİLERİM**"]
        for i, o in enumerate(liste, 1):
            p.append(f"**{i}.** {o['baslik']} — _{o['gerekce']}_")
        p.append("_Kurmak için: `1. öneriyi uygula`_")
        return "\n".join(p)
    except Exception as e:
        print(f"[ULTRON Oneri] Rapor eki uretilemedi: {e}")
        return ""


# ---------------------------------------------------------------------------
# KARAR
# ---------------------------------------------------------------------------
def _secimi_coz(secim: str, liste: list):
    """
    Numarayı/boş seçimi bir öneriye bağlar. Dönüş: (oneri, hata_mesaji).

    Belirsizlik ÇÖZÜLMEZ, sorulur: birden fazla öneri varken çıplak "kabul et"
    hangisini kastettiğini bilmiyor demektir. Tahmin etmek, kullanıcının
    istemediği görevi kurmaktır.
    """
    if not liste:
        return None, "💡 Şu an bekleyen önerim yok."

    secim = (secim or '').strip()
    if secim:
        eslesme = re.search(r'\d+', secim)
        if eslesme:
            sira = int(eslesme.group())
            gosterilen = _durum_yukle()['son_liste']
            # Numara GÖSTERİLEN sıradan çözülür; liste henüz gösterilmemişse
            # üretim sırası kullanılır (aynı sıra, ama garanti değil).
            kimlikler = gosterilen or [o['id'] for o in liste]
            if not (1 <= sira <= len(kimlikler)):
                return None, (f"🤔 {sira} numaralı öneri yok. "
                              f"Listeyi görmek için: `önerilerin`")
            hedef_id = kimlikler[sira - 1]
            oneri = next((o for o in liste if o['id'] == hedef_id), None)
            if not oneri:
                return None, ("🤔 O öneri artık geçerli değil — listeyi "
                              "tazelemek için: `önerilerin`")
            return oneri, None

    if len(liste) == 1:
        return liste[0], None
    return None, ("🤔 Hangi öneri? Numarasını yaz: `1. öneriyi uygula`\n\n" +
                  "\n".join(f"**{i}.** {o['baslik']}" for i, o in enumerate(liste, 1)))


def kabul_et(secim: str = "", db_cursor=None, db_conn=None) -> str:
    """Öneriyi uygular (zamanlanmış görev kurar / kısayol ekler)."""
    try:
        liste = oneriler(db_cursor=db_cursor)
        oneri, hata = _secimi_coz(secim, liste)
        if hata:
            return hata

        eylem = oneri['eylem']
        if eylem['tip'] == 'zamanlama':
            if db_cursor is None or db_conn is None:
                return "⚠️ Görev kurulamadı: veritabanına ulaşamıyorum."
            from features import scheduler
            sonuc = scheduler.gorev_ekle(db_cursor, db_conn,
                                         eylem['saat'], eylem['komut'])
        elif eylem['tip'] == 'kisayol':
            from features import custom_shortcuts
            basarili, sonuc = custom_shortcuts.ekle(eylem['ad'], eylem['komut'])
            if not basarili:
                return f"⚠️ {sonuc}"
        else:
            return "⚠️ Bu öneriyi nasıl uygulayacağımı bilmiyorum."

        _karar_yaz(oneri['id'], 'kabul')
        return f"{sonuc}\n\n_Öneriden kuruldu. Vazgeçersen geri alabilirsin._"
    except Exception as e:
        return f"⚠️ Öneri uygulanamadı: {e}"


def reddet(secim: str = "", db_cursor=None) -> str:
    """Öneriyi kalıcı olarak reddeder — bir daha sorulmaz."""
    try:
        liste = oneriler(db_cursor=db_cursor)
        oneri, hata = _secimi_coz(secim, liste)
        if hata:
            return hata
        _karar_yaz(oneri['id'], 'red')
        return f"👍 Tamam, bir daha sormam: _{oneri['baslik']}_"
    except Exception as e:
        return f"⚠️ Öneri reddedilemedi: {e}"


def durum(db_cursor=None) -> dict:
    """İstatistik sayfası için sayılar."""
    try:
        kararlar = _durum_yukle()['karar']
        return {
            'bekleyen': len(oneriler(db_cursor=db_cursor)),
            'kabul': sum(1 for k in kararlar.values() if k.get('durum') == 'kabul'),
            'red': sum(1 for k in kararlar.values() if k.get('durum') == 'red'),
        }
    except Exception:
        return {'bekleyen': 0, 'kabul': 0, 'red': 0}
