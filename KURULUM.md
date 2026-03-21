# TAU Modern Arayüz Kurulum Talimatları

## Gerekli Paketler

Modern web arayüzünü kullanabilmek için aşağıdaki paketlerin kurulu olması gerekiyor:

### 1. PyQt5 WebEngine Kurulumu

```bash
pip install PyQtWebEngine
```

veya

```bash
pip install PyQt5-WebEngine
```

### 2. Alternatif: PyQt6 WebEngine (Daha Modern)

```bash
pip install PyQt6-WebEngine
```

## Kurulum Sonrası

1. Paketleri kurduktan sonra `main.py` dosyasını çalıştırın
2. "1" seçeneğini seçerek modern web arayüzünü kullanın
3. Eğer WebEngine kurulu değilse, otomatik olarak klasik arayüze geçecektir

## Özellikler

### Modern Web Arayüzü:
- ✅ WhatsApp benzeri modern tasarım
- ✅ Responsive ve animasyonlu arayüz
- ✅ Sidebar navigasyon
- ✅ Memory yönetimi
- ✅ Hatırlatma sistemi
- ✅ İstatistikler paneli
- ✅ Sesli komut desteği
- ✅ Online/Offline mod geçişi
- ✅ Koyu/açık tema desteği

### Klasik PyQt5 Arayüzü:
- ✅ Mevcut tüm özellikler korunmuş
- ✅ Tab-based navigasyon
- ✅ Daha hızlı başlatma

## Sorun Giderme

### WebEngine Kurulum Sorunu:
```bash
# Windows için
pip install PyQt5-WebEngine

# Linux için
sudo apt-get install python3-pyqt5.qtwebengine

# macOS için
brew install pyqt5-webengine
```

### Alternatif Çözüm:
WebEngine kurulumu başarısız olursa, klasik arayüzü kullanmaya devam edebilirsiniz.

## Test Etme

Kurulum sonrası test etmek için:

```bash
python main.py
```

Seçenek 1'i seçin ve modern arayüzün açıldığını kontrol edin.
