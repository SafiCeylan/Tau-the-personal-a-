from datetime import datetime

def ruh_hali_analiz(mesaj):
    """Mesajdan ruh hali analizi yapar"""
    mesaj_lower = mesaj.lower()
    
    pozitif_kelimeler = ['mutlu', 'güzel', 'harika', 'süper', 'iyi', 'güzel', 'sevindim', 'keyifli', 'neşeli', 'enerjik']
    negatif_kelimeler = ['üzgün', 'kötü', 'kötü', 'yorgun', 'stresli', 'endişeli', 'korkuyorum', 'sıkıldım', 'bıktım', 'depresif']
    nötr_kelimeler = ['normal', 'sakin', 'rahat', 'durgun', 'sessiz']
    
    pozitif_sayisi = sum(1 for kelime in pozitif_kelimeler if kelime in mesaj_lower)
    negatif_sayisi = sum(1 for kelime in negatif_kelimeler if kelime in mesaj_lower)
    nötr_sayisi = sum(1 for kelime in nötr_kelimeler if kelime in mesaj_lower)
    
    if pozitif_sayisi > negatif_sayisi and pozitif_sayisi > nötr_sayisi:
        return 'pozitif', pozitif_sayisi
    elif negatif_sayisi > pozitif_sayisi and negatif_sayisi > nötr_sayisi:
        return 'negatif', negatif_sayisi
    elif nötr_sayisi > 0:
        return 'nötr', nötr_sayisi
    else:
        return 'belirsiz', 0

def ruh_hali_kaydet(cursor, conn, ruh_hali, mesaj):
    """Ruh hali verisini kaydeder"""
    try:
        cursor.execute("""
            INSERT INTO ruh_hali_gecmisi (ruh_hali, mesaj, tarih)
            VALUES (?, ?, ?)
        """, (ruh_hali, mesaj, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ruh hali kaydedilirken hata: {e}")
        return False 