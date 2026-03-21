import re
from datetime import datetime, timedelta

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
        'yarın': timedelta(days=1),
        'bugün': timedelta(days=0),
        'bu akşam': timedelta(hours=4),
        'bu gece': timedelta(hours=6),
        'haftaya': timedelta(weeks=1),
        'gelecek hafta': timedelta(weeks=1),
    }
    
    hedef_tarih = None
    detay_metni = ""

    # Sayısal zaman ifadelerini ara (örn: "10 dakika sonra", "2 saatlik")
    for unit, delta_func in time_units.items():
        # "10 saniye sonra", "10 saniyelik", "10 saniyede" gibi çeşitli ekleri kapsar
        match = re.search(r'(\d+)\s*'+unit, mesaj_lower)
        if match:
            sayi = int(match.group(1))
            hedef_tarih = datetime.now() + delta_func(sayi)
            detay_metni = f"{sayi} {unit} sonra"
            break
            
    # Özel zaman kelimelerini ara (eğer sayısal ifade bulunmadıysa)
    if not hedef_tarih:
        for word, delta in special_times.items():
            if word in mesaj_lower:
                hedef_tarih = datetime.now() + delta
                detay_metni = word
                break

    # Eğer bir hatırlatma komutu veya zaman ifadesi varsa, işlemi gerçekleştir
    if is_reminder_command and hedef_tarih:
        # Hatırlatma metnini temizle
        # Zaman ifadelerini ve anahtar kelimeleri metinden çıkar
        hatirlatma_metni = re.sub(r'(\d+)\s*(saniye|dakika|saat|gün|hafta|sn|dk)\w*', '', mesaj_lower)
        for keyword in hatirlatma_keywords + list(special_times.keys()):
            hatirlatma_metni = hatirlatma_metni.replace(keyword, '')
        
        # Gereksiz kelimeleri temizle
        hatirlatma_metni = hatirlatma_metni.replace('içinde', '').replace('sonra', '').strip()
        # Çift boşlukları tek boşluğa indir
        hatirlatma_metni = re.sub(r'\s+', ' ', hatirlatma_metni).strip()
        
        if not hatirlatma_metni:
            hatirlatma_metni = "belirtilmedi"

        return {
            'tip': 'hatirlatma',
            'metin': hatirlatma_metni,
            'tarih': hedef_tarih.strftime('%Y-%m-%d %H:%M:%S'),
            'detay': detay_metni
        }

    # Diğer komutları kontrol et
    if any(kelime in mesaj_lower for kelime in ['dün ne yaptım', 'geçen hafta', 'geçmiş', 'önceki']):
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