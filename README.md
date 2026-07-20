# Tau - The Personal AI 🤖

Tau, günlük işlerinizi kolaylaştırmak, sorularınızı yanıtlamak ve size yardımcı olmak için tasarlanmış, gelişmiş yeteneklere sahip kişisel bir yapay zeka asistanıdır. Kendi lokal ortamınızda veya entegre AI sağlayıcılarıyla (Kobold, Ollama, kendi TAU Backend'iniz) çalışabilen araç, tamamen **native bir PyQt5 masaüstü uygulaması**dır — tarayıcı veya web view bileşeni kullanmaz.

## ✨ Öne Çıkan Özellikler

- **🟡 Holografik AI Çekirdeği**: QPainter ile native olarak çizilen, altın/amber tonlarında nabız gibi atan, parçacık efektli bir sci-fi HUD görseli — asistan dinlerken/düşünürken/cevap verirken canlanır.
- **🧠 Gelişmiş Hafıza (Memory)**: Konuşmaları ve kritik bilgileri aklında tutarak kişiselleştirilmiş bir iletişim sunar.
- **⏰ Hatırlatma Sistemi**: Doğal dille yazılan hatırlatmaları ("yarın toplantı", "10 dakika sonra su iç") algılar ve zamanı geldiğinde hatırlatır.
- **🎙️ Sesli Komut Desteği**: Klavyeye dokunmadan, sadece konuşarak iletişim kurabilirsiniz (opsiyonel paketler gerektirir).
- **🔌 Çoklu AI Sağlayıcı**: Kobold, Ollama veya kendi TAU Backend'iniz arasında `config.json` ile seçim yapabilirsiniz.
- **📊 İstatistikler & Ruh Hali**: Kullanım verilerinizi ve son 7 günün duygu durum dağılımını takip edebileceğiniz paneller.
- **🎨 Tutarlı Koyu Tema**: Siyah/lacivert zemin üzerinde altın/amber vurgu rengiyle tek, resmi bir arayüz.

---

## 🚀 Kurulum ve Başlangıç

### 1️⃣ Gereksinimler

```bash
pip install -r requirements.txt
```

*(Detaylı kurulum ve sorun giderme için `KURULUM.md` dosyasına göz atabilirsiniz.)*

### 2️⃣ Çalıştırma

```bash
python main.py
```

Windows'ta `start_tau.bat` dosyasına çift tıklayarak da başlatabilirsiniz.

---

## 🛠 Kullanılan Teknolojiler

- **Çekirdek/Backend**: Python, SQLite
- **Arayüz (GUI)**: PyQt5 — tamamen native widget'lar + QPainter (web/QWebEngine yok)
- **AI Backend**: KoboldCPP, Ollama veya özel TAU Backend API'si

## 📂 Proje Yapısı (Özet)

- `main.py`: Asistanı başlatan tek giriş noktası.
- `ui/tau_window.py`: Ana pencere, sayfalar (sohbet/hatırlatmalar/ruh hali/hafıza/istatistikler) ve backend bağlantısı.
- `ui/ai_core_widget.py`: QPainter tabanlı holografik AI çekirdeği animasyonu.
- `features/`: Hatırlatıcı, ruh hali, AI sağlayıcı entegrasyonları ve diğer yetenek modülleri.
- `database/`: Asistanın hafızasının ve verilerinin tutulduğu SQLite katmanı.
- `archive/legacy_ui/`: Artık kullanılmayan eski arayüz denemeleri (referans amaçlı arşivlenmiştir, uygulama tarafından kullanılmaz).

## 🤝 Katkıda Bulunma

Bu proje, tamamen açık kaynaklı bir formatta geliştirilen kişisel bir asistandır. Dilediğiniz gibi fork edebilir, kendinize özel yeni 'feature'lar ekleyebilirsiniz. Fikirlerinizi Pull Request olarak göndermekten çekinmeyin!

---
> *Tasarım ve geliştirme sürecine dair daha detaylı yapılandırmalar için repo içindeki diğer dokümantasyonlara göz atmayı unutmayın.*
