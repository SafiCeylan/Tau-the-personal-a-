import re
from datetime import datetime, timedelta

# Haftanın günleri (Türkçe karakterli ve karaktersiz yazımlar)
GUN_ADLARI = {
    'pazartesi': 0, 'salı': 1, 'sali': 1, 'çarşamba': 2, 'carsamba': 2,
    'perşembe': 3, 'persembe': 3, 'cuma': 4, 'cumartesi': 5, 'pazar': 6,
}


def _saat_ayikla(mesaj_lower):
    """
    Mesajdan açık saat ifadesini ayıklar.
    Desteklenen biçimler: "14:00", "14.30", "saat 14", "saat 9'da", "14'te", "9da"
    Dönen değer: (saat, dakika, eşleşen_metin) veya None
    """
    # 1) 14:00 / 14.30
    m = re.search(r'\b(\d{1,2})[:.](\d{2})\b', mesaj_lower)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi, m.group(0)

    # 2) "saat 14" / "saat 9"
    m = re.search(r'saat\s+(\d{1,2})\b', mesaj_lower)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return h, 0, m.group(0)

    # 3) "14'te" / "14te" / "9'da" (bitişik ek — "10 dakika" ile karışmaz)
    m = re.search(r"\b(\d{1,2})['’]?(?:te|ta|de|da)\b", mesaj_lower)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return h, 0, m.group(0)

    # 4) Sayı yok ama GÜNÜN BÖLÜMÜ söylenmiş: "yarın sabah ilaç içmeyi hatırlat".
    #    Eskiden bu cümlede saat hiç çözülmüyor ve hatırlatma İÇİNDE BULUNULAN
    #    saate kuruluyordu — yani "yarın sabah" dediğinde akşam 21:23'te çalıyordu.
    for kalip, saat in _GUN_BOLUMLERI:
        m = re.search(kalip, mesaj_lower)
        if m:
            return saat, 0, m.group(0)

    return None


# Günün bölümü → varsayılan saat. Sıra önemli: "öğleden sonra" "öğle"den önce.
_GUN_BOLUMLERI = (
    (r'\böğleden\s+sonra\b', 15),
    (r'\bsabaha\s+karşı\b', 5),
    (r'\bsabah\w*\b', 8),
    (r'\böğle\w*\b', 12),
    (r'\bikindi\w*\b', 16),
    (r'\bakşam\w*\b', 19),
    (r'\bgece\w*\b', 22),
)


def _gun_kaydirma(mesaj_lower, now):
    """
    Mesajdaki gün ifadesini gün sayısına çevirir.
    Dönen değer: (gün_farkı, eşleşen_kelime) veya (None, None)
    """
    # "öbür gün" / "ertesi gün" — 'yarın'dan ÖNCE bakılır, iki gün sonrasıdır
    if re.search(r'\böbür\s+gün\b|\bobur\s+gun\b|\bertesi\s+gün\b', mesaj_lower):
        return 2, 'öbür gün'
    if 'yarın' in mesaj_lower:
        return 1, 'yarın'
    for gun_adi, gun_idx in GUN_ADLARI.items():
        if re.search(rf'\b{gun_adi}\b', mesaj_lower):
            fark = (gun_idx - now.weekday()) % 7
            if fark == 0:
                fark = 7  # "cuma" bugün cumaysa gelecek cumayı kastet
            return fark, gun_adi
    if any(w in mesaj_lower for w in ['bugün', 'bu akşam', 'bu gece']):
        return 0, 'bugün'
    if 'haftaya' in mesaj_lower or 'gelecek hafta' in mesaj_lower:
        return 7, 'haftaya'
    return None, None


def hatirlatma_algila(mesaj):
    """Daha esnek ve doğal dil anlayan hatırlatma komutlarını algılar."""
    mesaj_lower = mesaj.lower()

    # Hatırlatma anahtar kelimeleri
    hatirlatma_keywords = ['hatırlat', 'hatırla', 'kur', 'ayarla', 'oluştur', 'uyandır', 'alarm']
    is_reminder_command = any(keyword in mesaj_lower for keyword in hatirlatma_keywords)

    # Zaman ifadelerini ve karşılık gelen timedelta fonksiyonlarını tanımla
    time_units = {
        'saniye': lambda x: timedelta(seconds=x),
        'dakika': lambda x: timedelta(minutes=x),
        'saat': lambda x: timedelta(hours=x),
        'gün': lambda x: timedelta(days=x),
        'hafta': lambda x: timedelta(weeks=x),
        'sn': lambda x: timedelta(seconds=x),
        'dk': lambda x: timedelta(minutes=x),
    }

    # Özel zaman kelimeleri
    special_times = {
        # 'yarın'dan ÖNCE: saat verilmeyen "öbür gün ... hatırlat" cümlesi
        # ÖNCELİK 3'e düşüyor ve burada karşılığı olmadığı için hiç kurulamıyordu.
        'öbür gün': timedelta(days=2),
        'obur gun': timedelta(days=2),
        'ertesi gün': timedelta(days=2),
        'yarın': timedelta(days=1),
        'bugün': timedelta(days=0),
        'bu akşam': timedelta(hours=4),
        'bu gece': timedelta(hours=6),
        'haftaya': timedelta(weeks=1),
        'gelecek hafta': timedelta(weeks=1),
    }

    now = datetime.now()
    hedef_tarih = None
    detay_metni = ""
    temizlenecekler = []  # metinden çıkarılacak zaman ifadeleri

    # ÖNCELİK 1: Açık saat ifadesi ("yarın 14:00", "cuma saat 9'da", "18:30'da")
    saat_bilgisi = _saat_ayikla(mesaj_lower)
    if saat_bilgisi:
        h, mi, saat_txt = saat_bilgisi
        gun_farki, gun_txt = _gun_kaydirma(mesaj_lower, now)

        # "akşam 8" / "yarın gece 11" → 12 saat ekle (öğleden sonrayı kastediyor)
        if h < 12 and any(w in mesaj_lower for w in ['akşam', 'gece', 'öğleden sonra']):
            h += 12

        hedef = (now + timedelta(days=gun_farki or 0)).replace(
            hour=h, minute=mi, second=0, microsecond=0
        )
        # Gün belirtilmemişse ve saat bugün için geçmişse → yarına kur
        if gun_farki is None and hedef <= now:
            hedef += timedelta(days=1)

        hedef_tarih = hedef
        detay_metni = f"{gun_txt + ' ' if gun_txt else ''}saat {h:02d}:{mi:02d}"
        temizlenecekler.append(saat_txt)
        if gun_txt:
            temizlenecekler.append(gun_txt)

    # ÖNCELİK 2: Göreli sayısal ifadeler ("10 dakika sonra", "2 saatlik")
    if not hedef_tarih:
        for unit, delta_func in time_units.items():
            match = re.search(r'(\d+)\s*'+unit, mesaj_lower)
            if match:
                sayi = int(match.group(1))
                hedef_tarih = now + delta_func(sayi)
                detay_metni = f"{sayi} {unit} sonra"
                break

    # ÖNCELİK 3: Özel zaman kelimeleri tek başına ("yarın", "bu akşam")
    if not hedef_tarih:
        for word, delta in special_times.items():
            if word in mesaj_lower:
                hedef_tarih = now + delta
                detay_metni = word
                break

    # Eğer bir hatırlatma komutu veya zaman ifadesi varsa, işlemi gerçekleştir
    if is_reminder_command and hedef_tarih:
        # Hatırlatma metnini temizle: zaman ifadelerini ve anahtar kelimeleri çıkar
        hatirlatma_metni = re.sub(r'(\d+)\s*(saniye|dakika|saat|gün|hafta|sn|dk)\w*', '', mesaj_lower)
        for parca in temizlenecekler:
            hatirlatma_metni = hatirlatma_metni.replace(parca, '')

        # ⚠️ DÜZ replace() KELİME ORTASINDAN KESER. Eski hâli:
        #     "dolar kuru nedir"  → 'kur' silinir → "dolar u nedir"
        #     "kurabiye yapacağım" → "abiye yapacağım"
        # Kullanıcı hatırlatmasını bozulmuş metinle kaydediyordu.
        #
        # Kısa anahtarlar (kur) TAM KELİME eşleşmeli; uzun olanlar (hatırlat,
        # oluştur) Türkçe çekim eki alabildiği için sonrası serbest bırakılır.
        for keyword in (hatirlatma_keywords + list(special_times.keys()) +
                        ['saat', 'akşam', 'gece', 'öğleden', 'içinde', 'sonra']):
            k = re.escape(keyword)
            kalip = rf'\b{k}\w*\b' if len(keyword) >= 5 else rf'\b{k}\b'
            hatirlatma_metni = re.sub(kalip, ' ', hatirlatma_metni)

        hatirlatma_metni = hatirlatma_metni.strip()
        hatirlatma_metni = re.sub(r"^['’]?(te|ta|de|da)\b", '', hatirlatma_metni).strip()
        hatirlatma_metni = re.sub(r'\s+', ' ', hatirlatma_metni).strip(" ,.'’")

        if not hatirlatma_metni:
            hatirlatma_metni = "belirtilmedi"

        return {
            'tip': 'hatirlatma',
            'metin': hatirlatma_metni,
            'tarih': hedef_tarih.strftime('%Y-%m-%d %H:%M:%S'),
            'detay': detay_metni
        }

    # Reminders List / Query triggers
    if any(kelime in mesaj_lower for kelime in ['hatırlatma', 'hatırlatmalar', 'hatırlatıcı', 'göster', 'listele', 'neler var', 'geçmiş', 'önceki', 'dün ne yaptım']):
        return {'tip': 'gecmis_takip', 'metin': mesaj}
    if any(kelime in mesaj_lower for kelime in ['analiz', 'rapor', 'özet', 'haftalık', 'aylık']):
        return {'tip': 'analiz_raporu', 'metin': mesaj}
        
    return None

def hatirlatma_kaydet(cursor, conn, hatirlatma_bilgisi):
    """Hatırlatmayı veritabanına kaydeder"""
    try:
        cursor.execute("""
            INSERT INTO hatirlatmalar (metin, hedef_tarih, olusturma_tarihi, durum)
            VALUES (?, ?, ?, ?)
        """, (hatirlatma_bilgisi['metin'], hatirlatma_bilgisi['tarih'], 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'bekliyor'))
        conn.commit()
        return True
    except Exception as e:
        print(f"Hatırlatma kaydedilirken hata: {e}")
        return False

def gecmis_getir(cursor):
    """Geçmiş hatırlatmaları getirir"""
    try:
        cursor.execute("""
            SELECT metin, hedef_tarih, olusturma_tarihi, durum 
            FROM hatirlatmalar 
            ORDER BY olusturma_tarihi DESC 
            LIMIT 5
        """)
        return cursor.fetchall()
    except:
        return [] 