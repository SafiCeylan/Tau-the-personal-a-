from datetime import datetime, timedelta

def analiz_raporu_olustur(cursor):
    """Kişisel analiz raporu oluşturur ve HTML formatında döner."""
    try:
        # Son 7 günün ruh hali verilerini al
        bir_hafta_once = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            SELECT ruh_hali, COUNT(*) as sayi
            FROM ruh_hali_gecmisi
            WHERE tarih >= ?
            GROUP BY ruh_hali
        """, (bir_hafta_once,))
        
        ruh_hali_istatistikleri = cursor.fetchall()
        
        # Son 7 günün hatırlatmalarını al
        cursor.execute("""
            SELECT COUNT(*) as toplam_hatirlatma
            FROM hatirlatmalar
            WHERE olusturma_tarihi >= ?
        """, (bir_hafta_once,))
        
        hatirlatma_sayisi = cursor.fetchone()[0]
        
        # Rapor oluştur
        rapor = "📊 <b>Bu Haftanın Kişisel Analiz Raporu</b><br><br>"
        
        if ruh_hali_istatistikleri:
            rapor += "😊 <b>Ruh Hali Analizi:</b><br>"
            for ruh_hali, sayi in ruh_hali_istatistikleri:
                emoji = "😊" if ruh_hali == "pozitif" else "😔" if ruh_hali == "negatif" else "😐"
                rapor += f"  {emoji} {ruh_hali.title()}: {sayi} kez<br>"
            
            # En yaygın ruh hali
            en_yaygin = max(ruh_hali_istatistikleri, key=lambda x: x[1])
            if en_yaygin[1] > 2:
                if en_yaygin[0] == "negatif":
                    rapor += f"<br>⚠️ <b>Farkındalık:</b> Bu hafta {en_yaygin[1]} kez moralin düşük görünüyordu. Belki biraz dinlenmeye ihtiyacın var?<br>"
                elif en_yaygin[0] == "pozitif":
                    rapor += f"<br>🎉 <b>Harika!</b> Bu hafta {en_yaygin[1]} kez çok pozitif görünüyordun. Bu enerjiyi koru!<br>"
        else:
            rapor += "😊 <b>Ruh Hali Analizi:</b> Henüz yeterli veri yok.<br>"
        
        rapor += f"<br>⏰ <b>Hatırlatmalar:</b> Bu hafta {hatirlatma_sayisi} hatırlatma oluşturdun.<br>"
        
        # Öneriler
        rapor += "<br>💡 <b>Öneriler:</b><br>"
        if hatirlatma_sayisi > 5:
            rapor += "  • Çok fazla hatırlatman var. Belki daha az ama önemli şeylere odaklanabilirsin.<br>"
        elif hatirlatma_sayisi == 0:
            rapor += "  • Hiç hatırlatman yok. Belki önemli şeyleri not almayı deneyebilirsin.<br>"
        
        return rapor
        
    except Exception as e:
        return f"Analiz raporu oluşturulurken hata: {e}" 