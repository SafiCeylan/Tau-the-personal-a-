"""
Ekran Bağlamı — "ekranı oku" komutunu kelime çöplüğünden kurtarır.

SORUN: ham OCR yüzlerce kelime döndürüyor. Kullanıcı bunu okuyamaz, üzerine
konuşamaz. "YouTube aç" deyip sonra "üçüncüyü aç" diyebilmek için ekranın
SEÇİLEBİLİR ÖĞELERE ayrılmış olması gerekir.

ÇÖZÜM: satırlar uzamsal yakınlığa göre bloklara gruplanır. Site/uygulama
özel kuralı YOKTUR — YouTube kartı, Google sonucu, Spotify listesi ve dosya
gezgini satırı aynı geometrik kuralla çıkar:

    • Dikey olarak yakın (satır yüksekliğinin ~1.6 katından az boşluk)
    • Yatay olarak örtüşen satırlar aynı öğedir

Öğeler numaralanır ve kanal başına saklanır (`file_index.son_arama_bilgisi`
kalıbının aynısı). Böylece "3'ü aç" / "ikinciyi aç" / "kuzu kuzu olanı aç"
komutları sonradan çözülebilir.
"""

import re
import time

# Ekran TEKTİR: masaüstünden okuyup Telegram'dan seçmek doğal bir akış.
# Bu yüzden kanal başına değil tek anahtarda saklanır.
VARSAYILAN_KANAL = 'genel'

# kanal → {'ogeler': [...], 'baslik': str, 'zaman': float}
_SON_OKUMA = {}
_OKUMA_OMRU_SN = 300          # 5 dakika: ekran hızla değişir, bayat veri tehlikeli

# Bir öğenin başlık satırı için en az bu kadar karakter (ikon/simge gürültüsü elensin)
_MIN_BASLIK = 3
_MAX_OGE = 20

_SIRA_KELIMELERI = {
    'birinci': 1, 'ilk': 1, 'bir': 1,
    'ikinci': 2, 'iki': 2, 'üçüncü': 3, 'ucuncu': 3, 'üç': 3, 'uc': 3,
    'dördüncü': 4, 'dorduncu': 4, 'dört': 4, 'dort': 4,
    'beşinci': 5, 'besinci': 5, 'beş': 5, 'bes': 5,
    'altıncı': 6, 'altinci': 6, 'altı': 6, 'alti': 6,
    'yedinci': 7, 'yedi': 7, 'sekizinci': 8, 'sekiz': 8,
    'dokuzuncu': 9, 'dokuz': 9, 'onuncu': 10, 'on': 10,
    'sonuncu': -1, 'son': -1,
}

# Öğe olamayacak satırlar: saf simge, saat, tek harf, saf sayı
_GURULTU_RE = re.compile(r'^[\W\d_]{0,4}$|^\d{1,2}:\d{2}$')


def _anlamli_mi(metin: str) -> bool:
    m = (metin or '').strip()
    if len(m) < _MIN_BASLIK or _GURULTU_RE.match(m):
        return False
    # En az bir harf içermeli ("12 3 ..." gibi sayı yığınları öğe değildir)
    return bool(re.search(r'[a-zA-ZçğıöşüÇĞİÖŞÜ]', m))


def _satirlari_bolumle(okuma: dict):
    """Satırları YATAY BOŞLUĞA göre parçalara ayırır.

    Yan yana duran düğmeler ("Hatırlatma Ekle   Google Git") OCR'da TEK satır
    gelir ve tek öğe sanılır. Kelimeler arası boşluk ortalama karakter
    genişliğinin katını aşıyorsa orası ayrı bir öğedir.
    """
    satirlar = okuma.get('satir_kutulari') or []
    kelimeler = okuma.get('kelimeler') or []
    if not kelimeler:
        return list(satirlar)

    parcalar = []
    for satir in satirlar:
        icerdekiler = [k for k in kelimeler
                       if satir['y'] - 2 <= k['y'] <= satir['y'] + satir['h'] + 2
                       and satir['x'] - 2 <= k['x'] <= satir['x'] + satir['w'] + 2]
        if len(icerdekiler) < 2:
            parcalar.append(satir)
            continue

        icerdekiler.sort(key=lambda k: k['x'])
        # Ortalama karakter genişliği → eşik. Sabit piksel kullanılamaz:
        # 4K ekranla 1080p arasında fark var.
        ort_karakter = max(
            6, sum(k['w'] / max(1, len(k['metin'])) for k in icerdekiler) / len(icerdekiler))
        esik = ort_karakter * 6

        grup = [icerdekiler[0]]
        gruplar = [grup]
        for onceki, k in zip(icerdekiler, icerdekiler[1:]):
            if k['x'] - (onceki['x'] + onceki['w']) > esik:
                grup = [k]
                gruplar.append(grup)
            else:
                grup.append(k)

        for g in gruplar:
            sol = min(k['x'] for k in g)
            ust = min(k['y'] for k in g)
            sag = max(k['x'] + k['w'] for k in g)
            alt = max(k['y'] + k['h'] for k in g)
            parcalar.append({'metin': ' '.join(k['metin'] for k in g),
                             'x': sol, 'y': ust, 'w': sag - sol, 'h': alt - ust})
    return parcalar


def ogeleri_cikar(okuma: dict, max_oge: int = _MAX_OGE):
    """OCR sonucunu numaralı, tıklanabilir öğelere çevirir.

    Dönen: [{'sira', 'baslik', 'detay', 'metin', 'x', 'y', 'w', 'h', 'merkez'}]
    """
    satirlar = [s for s in _satirlari_bolumle(okuma) if _anlamli_mi(s.get('metin'))]
    if not satirlar:
        return []

    # Yukarıdan aşağı, soldan sağa
    satirlar.sort(key=lambda s: (s['y'], s['x']))

    bloklar = []
    for satir in satirlar:
        # ⚠️ İLK uyan bloğa değil, EN İYİ uyana eklenir. Çok sütunlu ekranda
        # (solda sohbet, sağda telemetri) satırlar y'ye göre sıralanınca
        # birbirine karışıyor; "ilk uyan" kuralı aynı paragrafı ikiye bölüyordu.
        en_iyi, en_iyi_skor = None, 0
        for blok in bloklar:
            b_sol = min(s['x'] for s in blok)
            b_sag = max(s['x'] + s['w'] for s in blok)
            son = blok[-1]
            dikey_bosluk = satir['y'] - (son['y'] + son['h'])
            if not (-son['h'] * 0.5 <= dikey_bosluk <= son['h'] * 1.6):
                continue
            ortusme = min(satir['x'] + satir['w'], b_sag) - max(satir['x'], b_sol)
            oran = ortusme / max(1, min(satir['w'], b_sag - b_sol))
            if oran > 0.35 and oran > en_iyi_skor:
                en_iyi, en_iyi_skor = blok, oran
        if en_iyi is not None:
            en_iyi.append(satir)
        else:
            bloklar.append([satir])

    ogeler = []
    for blok in bloklar:
        # Başlık = bloğun EN UZUN satırı değil, İLK satırı: kartlarda başlık
        # üstte durur (video adı → kanal → görüntülenme).
        baslik = blok[0]['metin'].strip()
        detay = ' · '.join(s['metin'].strip() for s in blok[1:3])
        sol = min(s['x'] for s in blok)
        ust = min(s['y'] for s in blok)
        sag = max(s['x'] + s['w'] for s in blok)
        alt = max(s['y'] + s['h'] for s in blok)
        ogeler.append({
            'baslik': baslik,
            'detay': detay,
            'metin': ' '.join(s['metin'].strip() for s in blok),
            'x': sol, 'y': ust, 'w': sag - sol, 'h': alt - ust,
            'merkez': (blok[0]['x'] + blok[0]['w'] // 2,
                       blok[0]['y'] + blok[0]['h'] // 2),
            'satir_sayisi': len(blok),
        })

    # Sıralama: ekrandaki konum (yukarıdan aşağı). Kullanıcı gördüğü sırayı sayar.
    ogeler.sort(key=lambda o: (o['y'], o['x']))
    ogeler = ogeler[:max_oge]
    for i, o in enumerate(ogeler, 1):
        o['sira'] = i
    return ogeler


def okumayi_kaydet(kanal, ogeler, baslik=""):
    _SON_OKUMA[str(kanal)] = {'ogeler': ogeler, 'baslik': baslik, 'zaman': time.time()}


def son_okuma(kanal):
    """Taze okumayı döner; bayatsa temizler. Ekran değişmiş olabilir."""
    kayit = _SON_OKUMA.get(str(kanal))
    if not kayit:
        return None
    if time.time() - kayit['zaman'] > _OKUMA_OMRU_SN:
        _SON_OKUMA.pop(str(kanal), None)
        return None
    return kayit


def okumayi_unut(kanal):
    _SON_OKUMA.pop(str(kanal), None)


def ozet_uret(ogeler, baslik="", limit=10):
    """Kullanıcıya gösterilecek NUMARALI özet — kelime çöplüğü değil."""
    if not ogeler:
        return f"👁️ **{baslik or 'Ekran'}** okundu ama seçilebilir bir öğe bulamadım."

    satirlar = [f"👁️ **{baslik or 'Ekran'}** — {len(ogeler)} öğe buldum:"]
    for o in ogeler[:limit]:
        detay = f"  _{o['detay'][:60]}_" if o['detay'] else ""
        satirlar.append(f"**{o['sira']}.** {o['baslik'][:70]}{detay}")
    if len(ogeler) > limit:
        satirlar.append(f"_… ve {len(ogeler) - limit} tane daha_")
    satirlar.append("")
    satirlar.append("Hangisini açayım? `3'ü aç` · `ikinciyi aç` · "
                    "`kuzu kuzu olanı aç` diyebilirsin.")
    return "\n".join(satirlar)


# ---------------------------------------------------------------------------
# Seçim çözümleme — "3'ü aç", "ikinciyi aç", "şu videoyu aç"
# ---------------------------------------------------------------------------
_SECIM_KALIPLARI = (
    # "3'ü aç", "3 numaralı olanı aç", "5. sırayı aç"
    # Ek listesi Türkçe belirtme hâlinin TÜM biçimlerini kapsamalı:
    # 3'ü · 2'yi · 4'ü · 5'i · 6'yı — 'yi/yı/yu/yü' unutulursa "2'yi aç" çözülmez.
    r"\b(\d{1,2})\s*(?:['’]?(?:yi|yı|yu|yü|i|ı|u|ü|nci|ncı|ncu|ncü)"
    r"|\s*\.|\s*numaral[ıi])?\s*"
    r"(?:olan[ıi]|s[ıi]ray[ıi]|videoyu|şark[ıi]y[ıi]|sonucu|linki)?\s*"
    r"(?:aç|ac|tıkla|tikla|seç|sec|başlat|baslat|oynat|git)\b",
)

_FIIL_RE = re.compile(r'\b(aç|ac|tıkla|tikla|seç|sec|başlat|baslat|oynat|git)\b')


def secim_niyeti_algila(mesaj: str) -> bool:
    """Bu cümle 'ekrandaki N'inci öğeyi aç' anlamına mı geliyor?"""
    return secim_referansi_coz(mesaj) is not None


def secim_referansi_coz(mesaj: str):
    """Cümleden seçim referansını çıkarır.

    Dönen: {'tip': 'sira', 'deger': int} | {'tip': 'metin', 'deger': str} | None
    """
    m = (mesaj or '').lower().strip()
    if not m or not _FIIL_RE.search(m):
        return None

    for kalip in _SECIM_KALIPLARI:
        eslesme = re.search(kalip, m)
        if eslesme:
            return {'tip': 'sira', 'deger': int(eslesme.group(1))}

    # "ikinciyi aç", "sonuncuyu aç"
    for kelime, sira in _SIRA_KELIMELERI.items():
        if re.search(rf'\b{kelime}\w{{0,4}}\s*(?:olan[ıi]|videoyu|şark[ıi]y[ıi]|sonucu)?\s*'
                     rf'{_FIIL_RE.pattern}', m):
            return {'tip': 'sira', 'deger': sira}

    # "kuzu kuzu olanı aç" / "tarkan olanı aç" — serbest metinle eşleştirme
    m2 = re.search(r'\b(?:ekranda(?:ki)?\s+)?(.{3,50}?)\s+'
                   r'(?:olan[ıi]|adl[ıi]s[ıi]n[ıi]|isimli(?:ni)?)\s*' + _FIIL_RE.pattern, m)
    if m2:
        return {'tip': 'metin', 'deger': m2.group(1).strip()}
    return None


def ogeyi_sec(referans, kanal):
    """Referansı son okumadaki bir öğeye bağlar.

    Dönen: (oge, hata_mesaji). Biri None'dır.
    """
    kayit = son_okuma(kanal)
    if not kayit or not kayit['ogeler']:
        return None, ("Önce ekranı okumam gerek — `ekranda ne var` de, "
                      "sonra numarayla seçebilirsin.")

    ogeler = kayit['ogeler']

    if referans['tip'] == 'sira':
        sira = referans['deger']
        if sira == -1:
            return ogeler[-1], None
        if 1 <= sira <= len(ogeler):
            return ogeler[sira - 1], None
        return None, (f"Ekranda {len(ogeler)} öğe var, {sira} numara yok. "
                      f"1-{len(ogeler)} arası bir numara söyle.")

    aranan = referans['deger'].lower()
    try:
        from features.screen_reader import _katla
        katla = _katla
    except Exception:
        def katla(s):
            return (s or '').lower()

    hedef = katla(aranan)
    eslesenler = [o for o in ogeler if hedef in katla(o['metin'])]
    if len(eslesenler) == 1:
        return eslesenler[0], None
    if len(eslesenler) > 1:
        liste = ' · '.join(f"{o['sira']}. {o['baslik'][:40]}" for o in eslesenler[:5])
        return None, f"'{aranan}' birden çok öğeyle eşleşti — numara söyle: {liste}"
    return None, (f"Ekranda '{aranan}' diye bir şey göremedim. "
                  f"`ekranda ne var` diyerek listeyi yenileyebilirsin.")
