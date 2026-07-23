import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import logging

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.setup_logging()
        self.initialize_database()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('DatabaseManager')

    def get_connection(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Veritabanı bağlantısı oluşturulamadı: {e}")
            raise

    def initialize_database(self):
        try:
            # PyInstaller ile paketlenirken dosya yolunu dinamik olarak bul
            import os
            import sys
            
            # Eğer PyInstaller ile paketlenmişse
            if getattr(sys, 'frozen', False):
                # PyInstaller ile paketlenmiş uygulama
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            else:
                # Normal Python çalıştırma
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            # Önce mevcut dizinde ara
            schema_path = os.path.join(base_path, 'schema.sql')
            
            # Eğer bulunamazsa, database klasöründe ara
            if not os.path.exists(schema_path):
                schema_path = os.path.join(base_path, 'database', 'schema.sql')
            
            # Hala bulunamazsa, ana dizinde ara
            if not os.path.exists(schema_path):
                schema_path = os.path.join(os.path.dirname(base_path), 'schema.sql')
            
            # Son çare olarak, mevcut çalışma dizininde ara
            if not os.path.exists(schema_path):
                schema_path = 'database/schema.sql'
            
            self.logger.info(f"Schema dosyası aranıyor: {schema_path}")
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema)
                conn.commit()
                
                # Memory tablosuna category kolonu ekle (eğer yoksa)
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(memory)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if 'category' not in columns:
                        cursor.execute("ALTER TABLE memory ADD COLUMN category TEXT DEFAULT 'Genel'")
                        conn.commit()
                        self.logger.info("Memory tablosuna category kolonu eklendi.")
                except sqlite3.Error as e:
                    self.logger.warning(f"Category kolonu eklenirken hata: {e}")

                # bilgiler tablosuna geri bildirim/doğrulama kolonlarını ekle (eğer yoksa)
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(bilgiler)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if 'dogru_cevap' not in columns:
                        cursor.execute("ALTER TABLE bilgiler ADD COLUMN dogru_cevap BOOLEAN")
                        conn.commit()
                        self.logger.info("bilgiler tablosuna dogru_cevap kolonu eklendi.")
                    if 'son_dogrulama' not in columns:
                        cursor.execute("ALTER TABLE bilgiler ADD COLUMN son_dogrulama TIMESTAMP")
                        conn.commit()
                        self.logger.info("bilgiler tablosuna son_dogrulama kolonu eklendi.")
                except sqlite3.Error as e:
                    self.logger.warning(f"bilgiler geri bildirim kolonları eklenirken hata: {e}")
                    
            self.logger.info("Veritabanı başarıyla başlatıldı.")
        except (sqlite3.Error, IOError) as e:
            self.logger.error(f"Veritabanı başlatılamadı: {e}")
            raise

    def _get_or_create_kategori_id(self, conn: sqlite3.Connection, kategori: Optional[str]) -> Optional[int]:
        """Kategori adına karşılık gelen id'yi döner; kategori yoksa oluşturur, boşsa None döner."""
        if not kategori:
            return None
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO kategoriler (kategori_adi)
            VALUES (?)
            ON CONFLICT(kategori_adi) DO NOTHING
        """, (kategori,))
        cursor.execute("SELECT id FROM kategoriler WHERE kategori_adi = ?", (kategori,))
        row = cursor.fetchone()
        return row['id'] if row else None

    def add_question_answer(self, soru: str, cevap: str, kategori: Optional[str] = None) -> int:
        try:
            with self.get_connection() as conn:
                kategori_id = self._get_or_create_kategori_id(conn, kategori)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO bilgiler (soru, cevap, kategori_id)
                    VALUES (?, ?, ?)
                """, (soru, cevap, kategori_id))
                conn.commit()
                result = cursor.lastrowid
                return result if result is not None else 0
        except sqlite3.Error as e:
            self.logger.error(f"Soru-cevap eklenirken hata oluştu: {e}")
            raise

    def get_answer(self, soru: str) -> Optional[dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT b.id, b.cevap, k.kategori_adi AS kategori, b.dogru_cevap
                    FROM bilgiler b
                    LEFT JOIN kategoriler k ON k.id = b.kategori_id
                    WHERE b.soru = ?
                """, (soru,))
                result = cursor.fetchone()

                if result:
                    return {
                        'id': result['id'],
                        'cevap': result['cevap'],
                        'kategori': result['kategori'],
                        'dogru_cevap': result['dogru_cevap']
                    }
                return None
        except sqlite3.Error as e:
            self.logger.error(f"Cevap aranırken hata oluştu: {e}")
            raise

    def log_conversation(self, soru: str, cevap: str, cevap_id: Optional[int] = None) -> Optional[int]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sohbet_gecmisi (soru_id, kullanici_girisi, sistem_cevabi)
                    VALUES (?, ?, ?)
                """, (cevap_id, soru, cevap))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            self.logger.error(f"Sohbet kaydedilirken hata oluştu: {e}")
            raise

    def update_feedback(self, conversation_id: int, feedback: bool) -> None:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Sohbet geçmişindeki geribildirimi güncelle
                cursor.execute("""
                    UPDATE sohbet_gecmisi
                    SET dogru_mu = ?
                    WHERE id = ?
                """, (feedback, conversation_id))

                # İlgili cevabın doğruluğunu güncelle
                cursor.execute("""
                    UPDATE bilgiler
                    SET dogru_cevap = ?,
                        son_dogrulama = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT soru_id
                        FROM sohbet_gecmisi
                        WHERE id = ?
                    )
                """, (feedback, conversation_id))
                conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Geribildirim güncellenirken hata oluştu: {e}")
            raise

    def get_learning_metrics(self, kategori: Optional[str] = None) -> List[Dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if kategori:
                    cursor.execute("""
                        SELECT *
                        FROM ogrenme_metrikleri
                        WHERE kategori = ?
                        ORDER BY test_tarihi DESC
                    """, (kategori,))
                else:
                    cursor.execute("""
                        SELECT *
                        FROM ogrenme_metrikleri
                        ORDER BY test_tarihi DESC
                    """)
                
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Öğrenme metrikleri alınırken hata oluştu: {e}")
            raise

    def add_learning_metric(self, dogru_sayisi: int, toplam_soru: int,
                          kategori: Optional[str] = None, aciklama: Optional[str] = None) -> None:
        try:
            basari_orani = (dogru_sayisi / toplam_soru) * 100 if toplam_soru > 0 else 0
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ogrenme_metrikleri
                    (dogru_sayisi, toplam_soru, basari_orani, kategori, aciklama)
                    VALUES (?, ?, ?, ?, ?)
                """, (dogru_sayisi, toplam_soru, basari_orani, kategori, aciklama))
                conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Öğrenme metriği eklenirken hata oluştu: {e}")
            raise

    def get_categories(self) -> List[str]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT kategori_adi FROM kategoriler")
                return [row['kategori_adi'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Kategoriler alınırken hata oluştu: {e}")
            raise

    def add_category(self, kategori: str) -> None:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO kategoriler (kategori_adi) VALUES (?)", (kategori,))
                conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Kategori eklenirken hata oluştu: {e}")
            raise

    # Basit hafıza sistemi fonksiyonları
    def add_memory(self, key: str, value: str, category: Optional[str] = None) -> None:
        """Belirtilen anahtar ile yeni bir hafıza kaydı ekler veya günceller."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memory (key, value, category)
                    VALUES (?, ?, COALESCE(?, 'Genel'))
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category, created_at=CURRENT_TIMESTAMP
                """, (key, value, category))
                conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Hafıza kaydı eklenirken/güncellenirken hata oluştu: {e}")
            raise

    def get_memory(self, key: str) -> Optional[str]:
        """Anahtara göre hafıza kaydını getirir."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
                result = cursor.fetchone()
                return result['value'] if result else None
        except sqlite3.Error as e:
            self.logger.error(f"Hafıza kaydı getirilirken hata oluştu: {e}")
            raise

    def delete_memory(self, key: str) -> None:
        """Anahtara göre hafıza kaydını siler."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
                conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Hafıza kaydı silinirken hata oluştu: {e}")
            raise

    def list_memory(self) -> list:
        """Tüm hafıza kayıtlarını (key, value, category) olarak listeler."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value, category FROM memory ORDER BY created_at DESC")
                return [(row['key'], row['value'], row['category']) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Hafıza kayıtları listelenirken hata oluştu: {e}")
            raise 