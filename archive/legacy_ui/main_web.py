import sys
import sqlite3
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QUrl, QTimer, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel
from database.db_manager import DatabaseManager
from features.reminders import hatirlatma_algila, hatirlatma_kaydet, gecmis_getir
from features.mood import ruh_hali_analiz, ruh_hali_kaydet
from features.reporting import analiz_raporu_olustur
from features.qa import cevapla_guven_skoru_ile
from features.ollama import ollama_generate
import json
from datetime import datetime, timedelta
import re
from rapidfuzz import fuzz
import threading
import socket
import socketserver
from http.server import SimpleHTTPRequestHandler
import functools

class TauWebBridge(QWidget):
    """PyQt5 ile Web UI arasında köprü"""
    
    def __init__(self, cursor, conn, cevapla_func, cevap_ogren_func):
        super().__init__()
        self.cursor = cursor
        self.conn = conn
        self.cevapla_func = cevapla_func
        self.cevap_ogren_func = cevap_ogren_func
        self.mode = "offline"  # "offline", "gemini", "tau_backend"
        self.last_api_call = 0  # Rate limit için zaman sakla
        # Load optional Ollama config from config.json
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(cfg_path, 'r', encoding='utf-8') as cf:
                cfg = json.load(cf)
            self.use_ollama = cfg.get('use_ollama', False)
            self.ollama_url = cfg.get('ollama_url', 'http://127.0.0.1:11434')
            self.ollama_model = cfg.get('ollama_model', None)
        except Exception:
            self.use_ollama = False
            self.ollama_url = 'http://127.0.0.1:11434'
            self.ollama_model = None
        
    @pyqtSlot(str)
    def sendMessage(self, message):
        """Web UI'dan gelen mesajı işle"""
        try:
            print(f"[TauWebBridge] sendMessage called. use_ollama={getattr(self, 'use_ollama', False)} message='{message[:120]}'")
            # If Ollama is enabled in config, prefer it for generating responses
            if getattr(self, 'use_ollama', False):
                try:
                    resp = ollama_generate(message, ollama_url=self.ollama_url, model=self.ollama_model)
                    print(f"[TauWebBridge] Ollama response (type={type(resp)}): {str(resp)[:200]}")
                    # If Ollama returned an error string, fall back to local TAU
                    if isinstance(resp, str) and resp.startswith('Ollama bağlantı hatası'):
                        print("[TauWebBridge] Ollama error detected, falling back to local TAU")
                        response, confidence = self.cevapla_func(self.cursor, message)
                        print(f"[TauWebBridge] TAU fallback response: {response[:200]}")
                        self.receiveMessage(response)
                    else:
                        self.receiveMessage(resp)
                except Exception as ex:
                    print(f"[TauWebBridge] Ollama call exception: {ex}")
                    response, confidence = self.cevapla_func(self.cursor, message)
                    print(f"[TauWebBridge] TAU fallback response after exception: {response[:200]}")
                    self.receiveMessage(response)
            else:
                response, confidence = self.cevapla_func(self.cursor, message)
                print(f"[TauWebBridge] TAU offline response: {response[:200]}")
                self.receiveMessage(response)
        except Exception as e:
            print(f"[TauWebBridge] sendMessage unexpected error: {e}")
            self.receiveMessage(f"Bir hata oluştu: {e}")
    
    @pyqtSlot(str)
    def receiveMessage(self, message):
        """Web UI'a mesaj gönder"""
        # JavaScript'e mesaj gönder
        js_code = f"window.pyqtBridge.receiveMessage('{message.replace(chr(39), chr(92)+chr(39))}');"
        self.web_view.page().runJavaScript(js_code)
    
    @pyqtSlot()
    def toggleMode(self):
        """Mod değiştir: offline -> gemini -> tau_backend -> offline"""
        # Online modes removed — keep user informed only about offline mode
        self.mode = "offline"
        self.receiveMessage("🔄 Mod değiştirildi: Offline Mod (TAU Local)")
    
    @pyqtSlot(str)
    def setMode(self, mode):
        """Belirli bir moda geç: 'offline', 'gemini', 'tau_backend'"""
        # Only offline mode supported now
        self.mode = "offline"
        self.receiveMessage("🔄 Mod değiştirildi: Offline Mod (TAU Local)")
    
    @pyqtSlot(str, str)
    def addMemory(self, key, value):
        """Yeni hafıza ekle"""
        try:
            self.cursor.execute("INSERT INTO memory (key, value) VALUES (?, ?)", (key, value))
            self.conn.commit()
            self.receiveMessage(f"Hafıza eklendi: {key}")
        except Exception as e:
            self.receiveMessage(f"Hafıza eklenirken hata: {e}")
    
    @pyqtSlot(str, str)
    def addReminder(self, text, time):
        """Yeni hatırlatma ekle"""
        try:
            self.cursor.execute("""
                INSERT INTO hatirlatmalar (metin, hedef_tarih, olusturma_tarihi, durum)
                VALUES (?, ?, ?, ?)
            """, (text, time, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'bekliyor'))
            self.conn.commit()
            self.receiveMessage(f"Hatırlatma eklendi: {text}")
        except Exception as e:
            self.receiveMessage(f"Hatırlatma eklenirken hata: {e}")
    
    @pyqtSlot()
    def generateReport(self):
        """Analiz raporu oluştur"""
        try:
            report = analiz_raporu_olustur(self.cursor)
            self.receiveMessage(report)
        except Exception as e:
            self.receiveMessage(f"Rapor oluşturulurken hata: {e}")
    
    @pyqtSlot()
    def loadUserData(self):
        """Kullanıcı verilerini yükle"""
        try:
            with open('user_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                name = data.get('name', 'Kullanıcı')
                js_code = f"document.getElementById('userGreeting').textContent = 'Merhaba {name}!';"
                self.web_view.page().runJavaScript(js_code)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Kullanıcı verisi yüklenirken hata: {e}")

class TauWebMainWindow(QMainWindow):
    """Tau Web UI Ana Pencere"""
    
    def __init__(self, cursor, conn, cevapla_func, cevap_ogren_func):
        super().__init__()
        self.cursor = cursor
        self.conn = conn
        self.cevapla_func = cevapla_func
        self.cevap_ogren_func = cevap_ogren_func
        
        self.setWindowTitle("TAU - Kişisel Asistan (Web UI)")
        self.setGeometry(100, 100, 1400, 900)
        
        # Web view oluştur
        self.web_view = QWebEngineView()
        
        # Web bridge oluştur
        self.bridge = TauWebBridge(cursor, conn, cevapla_func, cevap_ogren_func)
        self.bridge.web_view = self.web_view
        
        # Web channel kurulumu
        self.channel = QWebChannel()
        self.channel.registerObject("pyqtBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        # Serve the project root over a lightweight local HTTP server so
        # external CDN fonts (FontAwesome) can be loaded without CORS errors.
        project_root = os.path.abspath(os.path.dirname(__file__))

        def find_free_port(start=8000, end=8999):
            for p in range(start, end + 1):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    try:
                        s.bind(('127.0.0.1', p))
                        return p
                    except OSError:
                        continue
            raise RuntimeError('No free port found')

        try:
            port = find_free_port()
        except Exception:
            port = 8000

        handler = functools.partial(SimpleHTTPRequestHandler, directory=project_root)
        httpd = socketserver.ThreadingTCPServer(('127.0.0.1', port), handler)
        httpd.allow_reuse_address = True

        def serve_forever():
            try:
                httpd.serve_forever()
            except Exception:
                pass

        t = threading.Thread(target=serve_forever, daemon=True)
        t.start()

        # Web page to try (prefer richer UI with qwebchannel)
        candidate_paths = [
            ('ui/web_interface.html', True),
            ('web_ui/index.html', True)
        ]

        loaded = False
        for rel_path, use_http in candidate_paths:
            full_path = os.path.join(project_root, rel_path)
            if os.path.exists(full_path):
                url = f'http://127.0.0.1:{port}/{rel_path}'
                self.web_view.load(QUrl(url))
                loaded = True
                break

        if not loaded:
            # Fallback: basit HTML
            self.web_view.setHtml("""
            <html>
            <head><title>TAU Web UI</title></head>
            <body style="background: #1A1A2E; color: #E0E0E0; font-family: Arial; padding: 20px;">
                <h1>TAU Web UI Yükleniyor...</h1>
                <p>Web UI dosyaları bulunamadı. Lütfen web_ui veya ui klasörünü kontrol edin.</p>
            </body>
            </html>
            """)
        
        # Ana layout
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.web_view)
        self.setCentralWidget(central_widget)
        
        # Hoş geldin mesajı gönder
        QTimer.singleShot(1000, self.sendWelcomeMessage)
    
    def sendWelcomeMessage(self):
        """Hoş geldin mesajı gönder"""
        self.bridge.receiveMessage("Merhaba! Ben TAU, kişisel asistanınız. Size nasıl yardımcı olabilirim? 😊")

# Text-to-speech removed. Kept no-op for compatibility if referenced elsewhere.
def text_to_speech(*args, **kwargs):
    return None

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

def hatirlatma_algila(mesaj):
    """Hatırlatma komutlarını algılar"""
    mesaj_lower = mesaj.lower()
    
    # Detaylı zaman algılama
    zaman_kelimeleri = {
        'yarın': 1,
        'bugün': 0,
        'bu akşam': 0,
        'bu gece': 0,
        'haftaya': 7,
        'gelecek hafta': 7
    }
    
    # Dakika/saat algılama
    dakika_patterns = [
        (r'(\d+)\s*dakika\s*sonra', lambda x: timedelta(minutes=int(x))),
        (r'(\d+)\s*saat\s*sonra', lambda x: timedelta(hours=int(x))),
        (r'(\d+)\s*saniye\s*sonra', lambda x: timedelta(seconds=int(x))),
        (r'(\d+)\s*gün\s*sonra', lambda x: timedelta(days=int(x))),
        (r'(\d+)\s*dk\s*sonra', lambda x: timedelta(minutes=int(x))),
        (r'(\d+)\s*sa\s*sonra', lambda x: timedelta(hours=int(x))),
        (r'(\d+)\s*sn\s*sonra', lambda x: timedelta(seconds=int(x))),
    ]
    
    # Önce dakika/saat algılamayı dene
    for pattern, time_func in dakika_patterns:
        match = re.search(pattern, mesaj_lower)
        if match:
            sayi = int(match.group(1))
            if sayi > 0:
                # Hatırlatma metnini çıkar
                hatirlatma_metni = re.sub(pattern, '', mesaj_lower).replace('hatırlat', '').replace('hatırla', '').strip()
                hatirlatma_metni = re.sub(r'\b(yarın|bugün|bu akşam|bu gece|haftaya|gelecek hafta)\b', '', hatirlatma_metni).strip()
                
                if hatirlatma_metni:
                    hedef_tarih = datetime.now() + time_func(sayi)
                    return {
                        'tip': 'hatirlatma',
                        'metin': hatirlatma_metni,
                        'tarih': hedef_tarih.strftime('%Y-%m-%d %H:%M:%S'),
                        'gun': 0,
                        'detay': f"{sayi} {'dakika' if 'dakika' in pattern or 'dk' in pattern else 'saat' if 'saat' in pattern or 'sa' in pattern else 'saniye' if 'saniye' in pattern or 'sn' in pattern else 'gün'} sonra"
                    }
    
    # Günlük zaman algılama
    for kelime, gun in zaman_kelimeleri.items():
        if kelime in mesaj_lower:
            # Hatırlatma metnini çıkar
            hatirlatma_metni = mesaj.replace('hatırlat', '').replace('hatırla', '').strip()
            hatirlatma_metni = re.sub(r'\b(yarın|bugün|bu akşam|bu gece|haftaya|gelecek hafta)\b', '', hatirlatma_metni).strip()
            
            if hatirlatma_metni:
                hedef_tarih = datetime.now() + timedelta(days=gun)
                return {
                    'tip': 'hatirlatma',
                    'metin': hatirlatma_metni,
                    'tarih': hedef_tarih.strftime('%Y-%m-%d %H:%M:%S'),
                    'gun': gun,
                    'detay': kelime
                }
    
    # Geçmiş takibi
    if any(kelime in mesaj_lower for kelime in ['dün ne yaptım', 'geçen hafta', 'geçmiş', 'önceki']):
        return {
            'tip': 'gecmis_takip',
            'metin': mesaj
        }
    
    # Analiz raporu komutu
    if any(kelime in mesaj_lower for kelime in ['analiz', 'rapor', 'özet', 'haftalık', 'aylık']):
        return {
            'tip': 'analiz_raporu',
            'metin': mesaj
        }
    
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
    
    # Gelişmiş cevapla fonksiyonu
    def cevapla(cursor, soru):
        # Komutları ve analizleri işle
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
        return cevapla_guven_skoru_ile(cursor, soru)
    
    def cevap_ogren(cursor, conn, soru, cevap, kategori="Genel"):
        try:
            db_manager.add_question_answer(soru, cevap, kategori)
            return True
        except Exception as e:
            print(f"Cevap öğretilirken hata: {e}")
            return False

    # Uygulama penceresini oluştur
    app = QApplication(sys.argv)
    window = TauWebMainWindow(cursor, conn, cevapla, cevap_ogren)
    window.show()
    
    # Uygulamayı çalıştır
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()