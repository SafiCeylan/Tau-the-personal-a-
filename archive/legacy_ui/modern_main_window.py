import sys
import os
import json
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QUrl, pyqtSlot, QTimer
from PyQt5.QtWebChannel import QWebChannel

# TAU'nun mevcut fonksiyonlarını import et
from database.db_manager import DatabaseManager
from features.reminders import hatirlatma_algila, hatirlatma_kaydet, gecmis_getir
from features.mood import ruh_hali_analiz, ruh_hali_kaydet
from features.reporting import analiz_raporu_olustur
from features.qa import cevapla_guven_skoru_ile
from features.speech import dinle_ve_yaziya_cevir, text_to_speech
# Speech features enabled
# Online/gemini support removed
from features.tau_backend import tau_backend_soru_sor

# Web Bridge sınıfı
class TauBridge(QWidget):
    """PyQt5 ile Web UI arasında köprü"""
    
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
    
    @pyqtSlot(str)
    def sendMessage(self, message):
        """Web UI'dan gelen mesajı işle"""
        if self.parent_window:
            self.parent_window.process_message(message, self.parent_window.mode)
    
    @pyqtSlot(str)
    def receiveMessage(self, message):
        """Web UI'a mesaj gönder (geriye dönük uyumluluk için)"""
        if self.parent_window:
            self.parent_window.send_response_to_web("TAU", message)
    
    @pyqtSlot()
    def toggleMode(self):
        """Mod değiştir"""
        if self.parent_window:
            # Only offline/tau_backend modes are relevant; force offline when toggled
            self.parent_window.set_mode('offline')
    
    @pyqtSlot(str)
    def setMode(self, mode):
        """Belirli bir moda geç (sessiz, mesaj göstermeden)"""
        if self.parent_window:
            # Online mode removed; map any incoming mode to offline
            self.parent_window.mode = 'offline'
    
    @pyqtSlot(str, str, str)
    def addMemory(self, key, value, category="Genel"):
        """Yeni memory kaydı ekle"""
        print(f"🔵 addMemory çağrıldı: key={key}, value={value[:50]}..., category={category}")
        
        if not self.parent_window:
            print("❌ parent_window yok!")
            return False
            
        try:
            # Veritabanına ekle
            cursor = self.parent_window.cursor
            conn = self.parent_window.conn
            
            if not cursor:
                print("❌ cursor yok!")
                return False
            if not conn:
                print("❌ conn yok!")
                return False
            
            print(f"✅ Cursor ve conn hazır")
            
            # Önce aynı key var mı kontrol et
            cursor.execute("SELECT id FROM memory WHERE key = ?", (key,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"📝 Mevcut kayıt bulundu, güncelleniyor...")
                # Güncelle
                cursor.execute("""
                    UPDATE memory 
                    SET value = ?, category = ?, created_at = ?
                    WHERE key = ?
                """, (value, category, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), key))
                conn.commit()
                print(f"✅ Kayıt güncellendi: {key}")
                self.parent_window.send_response_to_web("TAU", f"✅ Kayıt güncellendi: {key}")
            else:
                print(f"➕ Yeni kayıt ekleniyor...")
                # Yeni kayıt ekle
                cursor.execute("""
                    INSERT INTO memory (key, value, category, created_at)
                    VALUES (?, ?, ?, ?)
                """, (key, value, category, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                conn.commit()
                print(f"✅ Kayıt eklendi: {key}")
                self.parent_window.send_response_to_web("TAU", f"✅ Kayıt eklendi: {key}")
            
            # Kaydın gerçekten eklendiğini doğrula
            cursor.execute("SELECT * FROM memory WHERE key = ?", (key,))
            verify = cursor.fetchone()
            if verify:
                print(f"✅ Kayıt doğrulandı: {key} = {value[:30]}...")
            else:
                print(f"⚠️ Kayıt doğrulanamadı: {key}")
            
            # Memory listesini hemen güncelle
            print(f"🔄 Memory listesi güncelleniyor...")
            self.getMemories()
            print(f"✅ Memory listesi güncellendi")
            
            return True
        except Exception as e:
            error_msg = f"❌ Hata: {str(e)}"
            print(f"❌ Memory ekleme hatası: {e}")
            import traceback
            traceback.print_exc()
            if self.parent_window:
                self.parent_window.send_response_to_web("TAU", error_msg)
            return False
    
    @pyqtSlot()
    def getMemories(self):
        """Tüm memory kayıtlarını getir"""
        if self.parent_window:
            try:
                cursor = self.parent_window.cursor
                # Category kolonunu kontrol et
                try:
                    cursor.execute("""
                        SELECT key, value, category, created_at 
                        FROM memory 
                        ORDER BY created_at DESC
                    """)
                    memories = cursor.fetchall()
                    memories_data = [
                        {
                            'key': m[0],
                            'value': m[1],
                            'category': m[2] if len(m) > 2 and m[2] else 'Genel',
                            'created_at': m[3] if len(m) > 3 else ''
                        }
                        for m in memories
                    ]
                except:
                    # Category kolonu yoksa
                    cursor.execute("""
                        SELECT key, value, created_at 
                        FROM memory 
                        ORDER BY created_at DESC
                    """)
                    memories = cursor.fetchall()
                    memories_data = [
                        {
                            'key': m[0],
                            'value': m[1],
                            'category': 'Genel',
                            'created_at': m[2] if len(m) > 2 else ''
                        }
                        for m in memories
                    ]
                
                # JavaScript'e gönder
                import json
                memories_json = json.dumps(memories_data)
                
                js_code = f"updateMemories({memories_json});"
                self.parent_window.web_view.page().runJavaScript(js_code)
            except Exception as e:
                print(f"Memory getirme hatası: {e}")
    
    @pyqtSlot()
    def getModules(self):
        """Tüm modülleri getir"""
        if self.parent_window:
            try:
                cursor = self.parent_window.cursor
                # Modüller tablosu yoksa oluştur
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS modules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            description TEXT,
                            enabled INTEGER DEFAULT 1,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    self.parent_window.conn.commit()
                except:
                    pass
                
                cursor.execute("""
                    SELECT id, name, description, enabled 
                    FROM modules 
                    ORDER BY created_at DESC
                """)
                modules = cursor.fetchall()
                modules_data = [
                    {
                        'id': m[0],
                        'name': m[1],
                        'description': m[2] if m[2] else '',
                        'enabled': bool(m[3])
                    }
                    for m in modules
                ]
                
                # JavaScript'e gönder
                import json
                modules_json = json.dumps(modules_data)
                js_code = f"updateModules({modules_json});"
                self.parent_window.web_view.page().runJavaScript(js_code)
            except Exception as e:
                print(f"Modül getirme hatası: {e}")
                import traceback
                traceback.print_exc()
    
    @pyqtSlot(str, str)
    def addModule(self, name, description=""):
        """Yeni modül ekle"""
        if self.parent_window:
            try:
                cursor = self.parent_window.cursor
                cursor.execute("""
                    INSERT INTO modules (name, description, enabled)
                    VALUES (?, ?, 1)
                """, (name, description))
                self.parent_window.conn.commit()
                self.getModules()  # Listeyi yenile
                self.parent_window.send_response_to_web("TAU", f"✅ Modül eklendi: {name}")
            except Exception as e:
                print(f"Modül ekleme hatası: {e}")
                self.parent_window.send_response_to_web("TAU", f"❌ Modül eklenirken hata: {e}")
    
    @pyqtSlot(int, bool)
    def toggleModule(self, module_id, enabled):
        """Modülü aktif/pasif yap"""
        if self.parent_window:
            try:
                cursor = self.parent_window.cursor
                cursor.execute("""
                    UPDATE modules 
                    SET enabled = ? 
                    WHERE id = ?
                """, (1 if enabled else 0, module_id))
                self.parent_window.conn.commit()
                self.getModules()  # Listeyi yenile
            except Exception as e:
                print(f"Modül toggle hatası: {e}")
    
    @pyqtSlot(int)
    def deleteModule(self, module_id):
        """Modülü sil"""
        if self.parent_window:
            try:
                cursor = self.parent_window.cursor
                cursor.execute("DELETE FROM modules WHERE id = ?", (module_id,))
                self.parent_window.conn.commit()
                self.getModules()  # Listeyi yenile
                self.parent_window.send_response_to_web("TAU", "✅ Modül silindi")
            except Exception as e:
                print(f"Modül silme hatası: {e}")
                self.parent_window.send_response_to_web("TAU", f"❌ Modül silinirken hata: {e}")
    
    @pyqtSlot(int)
    def editModule(self, module_id):
        """Modülü düzenle (şimdilik sadece bilgi göster)"""
        if self.parent_window:
            try:
                cursor = self.parent_window.cursor
                cursor.execute("SELECT name, description FROM modules WHERE id = ?", (module_id,))
                result = cursor.fetchone()
                if result:
                    self.parent_window.send_response_to_web("TAU", f"📝 Modül: {result[0]} - {result[1]}")
                else:
                    self.parent_window.send_response_to_web("TAU", "❌ Modül bulunamadı")
            except Exception as e:
                print(f"Modül düzenleme hatası: {e}")

    @pyqtSlot(str, str)
    def learnQA(self, question, answer):
        """Web UI'dan gelen öğrenme isteğini işle"""
        print(f"🧠 Öğrenme isteği: Soru='{question}', Cevap='{answer}'")
        if self.parent_window and self.parent_window.cevap_ogren_func:
            cursor = self.parent_window.cursor
            conn = self.parent_window.conn
            
            # Veritabanına kaydet
            # cevap_ogren_func: (cursor, conn, soru, cevap, kategori) -> bool
            if self.parent_window.cevap_ogren_func(cursor, conn, question, answer, "Öğrenilen"):
                print("✅ Bilgi veritabanına eklendi.")
            else:
                print("❌ Bilgi eklenirken hata oluştu.")

    @pyqtSlot()
    def voiceCommand(self):
        """Sesli komut başlat"""
        if self.parent_window:
            self.parent_window.handle_voice_command()

class ModernMainWindow(QMainWindow):
    """Modern web arayüzü ile TAU ana penceresi"""
    
    def __init__(self, cursor, conn, cevapla_func, cevap_ogren_func):
        super().__init__()
        self.cursor = cursor
        self.conn = conn
        self.cevapla_func = cevapla_func
        self.cevap_ogren_func = cevap_ogren_func
        self.mode = "offline"  # "offline", "gemini", "tau_backend"
        self.last_api_call = 0  # Rate limit için zaman sakla
        
        self.setup_ui()
        self.setup_web_channel()
        
        # Hatırlatma kontrol zamanlayıcısı (her 10 saniyede bir)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(10000)
        
    def check_reminders(self):
        """Süresi gelen hatırlatmaları kontrol et"""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.cursor.execute("""
                SELECT id, metin, hedef_tarih 
                FROM hatirlatmalar 
                WHERE durum = 'bekliyor' AND hedef_tarih <= ?
            """, (now,))
            
            reminders = self.cursor.fetchall()
            
            for rem_id, metin, tarih in reminders:
                # Kullanıcıya bildir
                bildirim_metni = f"⏰ **HATIRLATMA!**\n\n{metin}\n\n(Zamanı: {tarih})"
                self.send_response_to_web("TAU", bildirim_metni)
                
                # Sesli uyarı
                from features.speech import text_to_speech
                from threading import Thread
                try:
                    Thread(target=text_to_speech, args=(f"Hatırlatma vakti: {metin}",)).start()
                except Exception as e:
                    print(f"Sesli hatırlatma hatası: {e}")
                
                # Durumu güncelle
                self.cursor.execute("""
                    UPDATE hatirlatmalar 
                    SET durum = 'tamamlandi' 
                    WHERE id = ?
                """, (rem_id,))
                
            if reminders:
                self.conn.commit()
                
        except Exception as e:
            print(f"Hatırlatma kontrol hatası: {e}")
        
    def setup_ui(self):
        """Arayüzü kur"""
        self.setWindowTitle("TAU - Kişisel Asistan (Modern Arayüz)")
        self.setGeometry(100, 100, 1400, 900)
        
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Web view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        
        # HTML dosyasının yolunu al
        html_path = os.path.join(os.path.dirname(__file__), 'web_interface.html')
        html_url = QUrl.fromLocalFile(os.path.abspath(html_path))
        
        print(f"HTML dosyası yolu: {html_url.toString()}")
        
        # Web sayfasını yükle
        self.web_view.load(html_url)
        
    def setup_web_channel(self):
        """QWebChannel ile web arayüzü bağlantısı kur"""
        # Web bridge oluştur
        self.bridge = TauBridge(self)
        
        # QWebChannel oluştur ve bridge'i kaydet
        self.channel = QWebChannel()
        self.channel.registerObject("pyqtBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        # Sayfa yüklendiğinde JavaScript'e global erişim sağla
        self.web_view.page().loadFinished.connect(self.on_page_loaded)
        
    def on_page_loaded(self):
        """Sayfa yüklendiğinde çalışır"""
        print("✅ Web sayfası yüklendi!")
        # JavaScript'e window.external objesi ekle (geriye dönük uyumluluk için)
        js_code = """
        if (!window.external) {
            window.external = {
                sendMessage: function(message, isOnline) {
                    if (window.pyqtBridge) {
                        var mode = isOnline ? 'gemini' : 'offline';
                        window.pyqtBridge.setMode(mode);
                        window.pyqtBridge.sendMessage(message);
                    }
                }
            };
        }
        """
        self.web_view.page().runJavaScript(js_code)
            
    def process_message(self, message, mode=None):
        """Mesajı işle"""
        if mode is None:
            mode = self.mode
            
        try:
            # Offline-only: use local TAU responder
            response, confidence = self.cevapla_func(self.cursor, message)
            
            # Cevabı soruyla birlikte gönder (feedback için)
            self.send_response_to_web("TAU", response, question=message)
            
            # Sesli yanıt
            from threading import Thread
            Thread(target=text_to_speech, args=(response,)).start()
            
        except Exception as e:
            self.send_response_to_web("TAU", f"Bir hata oluştu: {e}")
    
    def set_mode(self, mode):
        """Mod değiştir: 'offline', 'gemini', 'tau_backend'"""
        # Online modes removed — always set to offline
        self.mode = 'offline'
        self.send_response_to_web("TAU", "🔄 Mod değiştirildi: Offline Mod (TAU Local)")
            
    def send_response_to_web(self, sender, message, question=None):
        """Python'dan web arayüzüne mesaj gönder"""
        # Sender'ı "assistant" olarak değiştir (CSS için)
        if sender == "TAU" or sender == "assistant":
            sender = "assistant"
        
        # Mesajı JSON string olarak escape et (güvenli)
        import json
        escaped_message = json.dumps(message)
        
        # Soruyu da escape et (feedback için)
        if question:
            escaped_question = json.dumps(question)
        else:
            escaped_question = "null"
        
        # JavaScript kodunu oluştur
        js_code = f"addMessage('{sender}', {escaped_message}, {escaped_question});"
        self.web_view.page().runJavaScript(js_code)
        
    def handle_voice_command(self):
        """Sesli komutu işle ve onayla"""
        # Arayüzü dondurmamak için processEvents
        QApplication.processEvents()
        import time
        
        try:
            # 1. Adım: Komutu Dinle
            komut = dinle_ve_yaziya_cevir()
            
            if not komut:
                self.web_view.page().runJavaScript("setListeningState(false);")
                self.send_response_to_web("TAU", "Sesini duyamadım. 🙉")
                return

            # 2. Adım: Onay İste
            # Overlay metnini güncelle
            safe_komut = komut.replace("'", "\\'")
            js_code = f"document.querySelector('.listening-text').innerText = 'Algılanan: {safe_komut}\\nDoğru mu? (Evet/Hayır)';"
            self.web_view.page().runJavaScript(js_code)
            
            # Kullanıcıya sormak için kısa bir es verip tekrar dinle
            QApplication.processEvents()
            time.sleep(1.5) 
            
            onay = dinle_ve_yaziya_cevir()
            
            # Dinleme bitti, overlay'i kapat
            self.web_view.page().runJavaScript("setListeningState(false);")
            
            if onay and any(x in onay.lower() for x in ['evet', 'doğru', 'yes', 'onayla', 'tamam']):
                # Web arayüzünde kullanıcının mesajı olarak göster
                self.send_response_to_web("user", komut)
                # Mesajı işle
                self.process_message(komut)
            else:
                self.send_response_to_web("TAU", "İşlem iptal edildi. ❌")
                
        except Exception as e:
            self.web_view.page().runJavaScript("setListeningState(false);")
            self.send_response_to_web("TAU", f"Ses hatası: {e}")

def main():
    """Ana fonksiyon"""
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
    window = ModernMainWindow(cursor, conn, cevapla, cevap_ogren)
    window.show()
    
    # Uygulamayı çalıştır
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
