-- Bilgiler tablosu
CREATE TABLE IF NOT EXISTS bilgiler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soru TEXT NOT NULL,
    cevap TEXT NOT NULL,
    kategori_id INTEGER,
    dogru_sayisi INTEGER DEFAULT 0,
    yanlis_sayisi INTEGER DEFAULT 0,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    son_guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kategori_id) REFERENCES kategoriler(id)
);

-- Kategoriler tablosu
CREATE TABLE IF NOT EXISTS kategoriler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kategori_adi TEXT UNIQUE NOT NULL,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sohbet geçmişi tablosu
CREATE TABLE IF NOT EXISTS sohbet_gecmisi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    soru_id INTEGER,
    kullanici_girisi TEXT NOT NULL,
    sistem_cevabi TEXT NOT NULL,
    dogru_mu BOOLEAN,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (soru_id) REFERENCES bilgiler(id)
);

-- Öğrenme metrikleri tablosu
CREATE TABLE IF NOT EXISTS ogrenme_metrikleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kategori_id INTEGER,
    dogru_sayisi INTEGER NOT NULL,
    toplam_soru INTEGER NOT NULL,
    aciklama TEXT,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kategori_id) REFERENCES kategoriler(id)
);

-- Memory tablosu
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'Genel',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- İndeksler
CREATE INDEX IF NOT EXISTS idx_bilgiler_soru ON bilgiler(soru);
CREATE INDEX IF NOT EXISTS idx_bilgiler_kategori ON bilgiler(kategori_id);
CREATE INDEX IF NOT EXISTS idx_sohbet_tarih ON sohbet_gecmisi(tarih);
CREATE INDEX IF NOT EXISTS idx_metrikler_kategori ON ogrenme_metrikleri(kategori_id);

-- Hatırlatmalar Tablosu
CREATE TABLE IF NOT EXISTS hatirlatmalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metin TEXT NOT NULL,
    hedef_tarih TIMESTAMP,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    durum TEXT DEFAULT 'bekliyor'
);

-- Özel Otonom Rutinler / Modlar Tablosu
CREATE TABLE IF NOT EXISTS custom_routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    trigger_keyword TEXT NOT NULL UNIQUE,
    description TEXT,
    actions_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ruh Hali Geçmişi Tablosu
CREATE TABLE IF NOT EXISTS ruh_hali_gecmisi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruh_hali TEXT NOT NULL,
    mesaj TEXT,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zamanlanmış Görevler (her gün belirtilen saatte otomatik çalışır)
CREATE TABLE IF NOT EXISTS zamanli_gorevler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saat TEXT NOT NULL,            -- 'HH:MM'
    komut TEXT NOT NULL,           -- engine'den geçirilecek komut
    son_calisma TEXT,              -- 'YYYY-MM-DD' (aynı gün iki kez çalışmasın)
    aktif INTEGER DEFAULT 1,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
); 