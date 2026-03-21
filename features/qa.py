from rapidfuzz import fuzz

def cevapla_guven_skoru_ile(cursor, soru, min_guven=80):
    """Güven skoruna göre cevap verir"""
    try:
        # Veritabanından tüm soru-cevap çiftlerini al
        cursor.execute("SELECT soru, cevap FROM bilgiler")
        tum_kayitlar = cursor.fetchall()
        
        en_iyi_eslesme = None
        en_yuksek_benzerlik = 0
        alternatifler = []
        
        # Her kayıt için benzerlik hesapla
        for kayit_soru, kayit_cevap in tum_kayitlar:
            benzerlik = fuzz.ratio(soru.lower().strip(), kayit_soru.lower().strip())
            
            if benzerlik > en_yuksek_benzerlik:
                en_yuksek_benzerlik = benzerlik
                en_iyi_eslesme = (kayit_soru, kayit_cevap)
            
            # Alternatifler için %30-70 arası benzerlikleri topla
            if 30 <= benzerlik < 70:
                alternatifler.append((kayit_soru, benzerlik))
        
        # Alternatifleri benzerlik sırasına göre sırala (en yüksekten en düşüğe)
        alternatifler.sort(key=lambda x: x[1], reverse=True)
        
        # Güven skoruna göre yanıt ver
        if en_iyi_eslesme and en_yuksek_benzerlik >= min_guven:
            # Yüksek güven - doğrudan cevap ver
            return f"{en_iyi_eslesme[1]}", en_yuksek_benzerlik
        elif en_iyi_eslesme and en_yuksek_benzerlik >= 50:
            # Orta güven - uyarı ile cevap ver
            return f"Emin değilim ama... {en_iyi_eslesme[1]} (Güven: %{en_yuksek_benzerlik})", en_yuksek_benzerlik
        else:
            # Düşük güven - alternatifler sun
            if alternatifler:
                alternatif_metni = "Seni tam anlayamadım. Şunlardan birini mi demek istedin?\n"
                for i, (alt_soru, alt_benzerlik) in enumerate(alternatifler[:3], 1):  # En fazla 3 alternatif
                    alternatif_metni += f"{i}. {alt_soru} (Benzerlik: %{alt_benzerlik})\n"
                alternatif_metni += "\nEğer bunlardan biri değilse, sorunu daha açık yazabilir misin?"
                return alternatif_metni, en_yuksek_benzerlik
            else:
                return f"Üzgünüm, bu konuda hiçbir şey bulamadım. Yeni bir şey öğretmek ister misin?", 0
            
    except Exception as e:
        print(f"cevapla_guven_skoru_ile içinde hata: {e}")
        return f"Bir hata oluştu: {e}", 0 