import sys
import sqlite3
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from database.db_manager import DatabaseManager
from features.reminders import hatirlatma_algila, hatirlatma_kaydet, gecmis_getir
from features.mood import ruh_hali_analiz, ruh_hali_kaydet
from features.reporting import analiz_raporu_olustur
from features.qa import cevapla_guven_skoru_ile
from features.ollama import ollama_generate
from features.kobold import kobold_generate

# AI Ayarları
AI_PROVIDER = 'kobold'  # Seçenekler: 'ollama', 'kobold'
from features.actions.system_control import sistem_komutu_algila

import json
from datetime import datetime, timedelta
import re
import os
from rapidfuzz import fuzz




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

def analiz_raporu_olustur(cursor):
    """Kişisel analiz raporu oluşturur"""
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
        rapor = "📊 **Bu Haftanın Kişisel Analiz Raporu**\n\n"
        
        if ruh_hali_istatistikleri:
            rapor += "😊 **Ruh Hali Analizi:**\n"
            for ruh_hali, sayi in ruh_hali_istatistikleri:
                emoji = "😊" if ruh_hali == "pozitif" else "😔" if ruh_hali == "negatif" else "😐"
                rapor += f"  {emoji} {ruh_hali.title()}: {sayi} kez\n"
            
            # En yaygın ruh hali
            en_yaygin = max(ruh_hali_istatistikleri, key=lambda x: x[1])
            if en_yaygin[1] > 2:
                if en_yaygin[0] == "negatif":
                    rapor += f"\n⚠️ **Farkındalık:** Bu hafta {en_yaygin[1]} kez moralin düşük görünüyordu. Belki biraz dinlenmeye ihtiyacın var?\n"
                elif en_yaygin[0] == "pozitif":
                    rapor += f"\n🎉 **Harika!** Bu hafta {en_yaygin[1]} kez çok pozitif görünüyordun. Bu enerjiyi koru!\n"
        else:
            rapor += "😊 **Ruh Hali Analizi:** Henüz yeterli veri yok.\n"
        
        rapor += f"\n⏰ **Hatırlatmalar:** Bu hafta {hatirlatma_sayisi} hatırlatma oluşturdun.\n"
        
        # Öneriler
        rapor += "\n💡 **Öneriler:**\n"
        if hatirlatma_sayisi > 5:
            rapor += "  • Çok fazla hatırlatman var. Belki daha az ama önemli şeylere odaklanabilirsin.\n"
        elif hatirlatma_sayisi == 0:
            rapor += "  • Hiç hatırlatman yok. Belki önemli şeyleri not almayı deneyebilirsin.\n"
        
        return rapor
        
    except Exception as e:
        return f"Analiz raporu oluşturulurken hata: {e}"



def cevapla_guven_skoru_ile(cursor, soru, min_guven=80):
    """Güven skoruna göre cevap verir"""
    print("cevapla_guven_skoru_ile başladı.")
    try:
        # Veritabanından tüm soru-cevap çiftlerini al
        cursor.execute("SELECT soru, cevap FROM bilgiler")
        tum_kayitlar = cursor.fetchall()
        print(f"Veritabanından {len(tum_kayitlar)} kayıt çekildi.")
        
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
            print("Yüksek güvenle cevap bulundu.")
            return f"{en_iyi_eslesme[1]}", en_yuksek_benzerlik
        elif en_iyi_eslesme and en_yuksek_benzerlik >= 50:
            # Orta güven - uyarı ile cevap ver
            print("Orta güvenle cevap bulundu.")
            return f"Emin değilim ama... {en_iyi_eslesme[1]} (Güven: %{en_yuksek_benzerlik})", en_yuksek_benzerlik
        else:
            # Düşük güven - alternatifler sun
            if alternatifler:
                alternatif_metni = "Seni tam anlayamadım. Şunlardan birini mi demek istedin?\n"
                for i, (alt_soru, alt_benzerlik) in enumerate(alternatifler[:3], 1):  # En fazla 3 alternatif
                    alternatif_metni += f"{i}. {alt_soru} (Benzerlik: %{alt_benzerlik})\n"
                alternatif_metni += "\nEğer bunlardan biri değilse, sorunu daha açık yazabilir misin?"
                print("Düşük güven, alternatifler sunuluyor.")
                return alternatif_metni, en_yuksek_benzerlik
            else:
                print("Hiçbir sonuç bulunamadı.")
                return f"Üzgünüm, bu konuda hiçbir şey bulamadım. Yeni bir şey öğretmek ister misin?", 0
            
    except Exception as e:
        print(f"cevapla_guven_skoru_ile içinde hata: {e}")
        return f"Bir hata oluştu: {e}", 0

def main():
    # Veritabanı yöneticisini başlat
    db_manager = DatabaseManager('bilgiler.db')
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    # Konuşma bağlamını (context) saklamak için liste
    tau_context = []
    
    # Gelişmiş cevapla fonksiyonu
    def cevapla(cursor, soru):
        nonlocal tau_context
        # 1. Önce aksiyon/sistem komutlarını kontrol et (Eller ve Kollar)
        is_action, action_response = sistem_komutu_algila(soru)
        if is_action:
            return f"⚙️ {action_response}", 100
            
        # 2. Hatırlatma ve diğer özel komutları işle
        hatirlatma = hatirlatma_algila(soru)
        
        if hatirlatma:
            if hatirlatma['tip'] == 'hatirlatma':
                if hatirlatma_kaydet(cursor, conn, hatirlatma):
                    zaman_detayi = hatirlatma.get('detay', '')
                    return f"✅ Hatırlatma kaydedildi! '{hatirlatma['metin']}' konusunda {zaman_detayi} hatırlatacağım.", 100
                else:
                    return "❌ Hatırlatma kaydedilirken bir hata oluştu.", 0
            
            elif hatirlatma['tip'] == 'gecmis_takip':
                gecmis = gecmis_getir(cursor)
                if gecmis:
                    gecmis_metni = "📅 Geçmiş hatırlatmaların:\n"
                    for i, (metin, hedef_tarih, olusturma_tarihi, durum) in enumerate(gecmis, 1):
                        gecmis_metni += f"{i}. {metin} ({durum})\n"
                    return gecmis_metni, 100
                else:
                    return "📅 Henüz hatırlatman yok.", 100
            
            elif hatirlatma['tip'] == 'analiz_raporu':
                return analiz_raporu_olustur(cursor), 100
        
        # Ruh hali analizi
        ruh_hali, skor = ruh_hali_analiz(soru)
        if ruh_hali != 'belirsiz':
            ruh_hali_kaydet(cursor, conn, ruh_hali, soru)
        
        # Normal cevap arama
        # Normal cevap arama
        veritabani_cevap, skor = cevapla_guven_skoru_ile(cursor, soru)
        
        # Eğer veritabanı güven skoru düşükse AI'ya sor
        if skor < 70:
            print(f"Veritabanında yeterli eşleşme yok, {AI_PROVIDER} devreye giriyor...")
            
            ai_cevap = ""
            yeni_context = None
            
            if AI_PROVIDER == 'kobold':
                ai_cevap, yeni_context = kobold_generate(soru, context=tau_context)
            else:
                # Ollama modundaysa ve context Kobold formatındaysa (dict listesi), sıfırla
                # Çünkü Ollama sadece int listesi (token ID'leri) kabul eder
                if tau_context and isinstance(tau_context, list) and len(tau_context) > 0 and isinstance(tau_context[0], dict):
                    tau_context = []
                    
                # Context ile birlikte çağır
                ai_cevap, yeni_context = ollama_generate(soru, model='gemma3:4b', context=tau_context)
            
            # Context'i güncelle (hafıza devamlılığı)
            if yeni_context:
                tau_context = yeni_context
            
            # Hata durumunda (bağlantı hatası vs) veritabanı cevabını veya hata mesajını dön
            if any(ai_cevap.startswith(prefix) for prefix in ["Hata", "Bağlantı Hatası", "Ollama hatası", "KoboldCPP"]):
                 # Eğer veritabanı bir şey bulduysa (düşük skorlu da olsa) onu gösterelim, yoksa hatayı
                 return (veritabani_cevap, skor) if skor > 30 else (ai_cevap, 0)
            
            return f"🧠 {ai_cevap}", 85 # AI cevabı
            
        return veritabani_cevap, skor
    
    def cevap_ogren(cursor, conn, soru, cevap, kategori="Genel"):
        try:
            db_manager.add_question_answer(soru, cevap, kategori)
            return True
        except Exception as e:
            print(f"Cevap öğretilirken hata: {e}")
            return False

    # Qt ayarlarını yap (WebEngine için gerekli)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    
    # Uygulama penceresini oluştur
    app = QApplication(sys.argv)
    
    # Modern arayüzü deneyelim
    try:
        from ui.modern_main_window import ModernMainWindow
        print("Modern web arayuzu yukleniyor...")
        window = ModernMainWindow(cursor, conn, cevapla, cevap_ogren)
        print("Modern arayuz basariyla yuklendi!")
    except ImportError as e:
        print(f"Modern arayuz yuklenemedi: {e}")
        print("Klasik PyQt5 arayuzune geciliyor...")
        window = MainWindow(cursor, conn, cevapla, cevap_ogren)
    except Exception as e:
        print(f"Modern arayuz hatasi: {e}")
        print("Klasik PyQt5 arayuzune geciliyor...")
        window = MainWindow(cursor, conn, cevapla, cevap_ogren)
    
    window.show()
    
    # Uygulamayı çalıştır
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()