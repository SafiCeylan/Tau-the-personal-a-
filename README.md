# Tau - The Personal AI 🤖

Tau, günlük işlerinizi kolaylaştırmak, sorularınızı yanıtlamak ve size yardımcı olmak için tasarlanmış, gelişmiş yeteneklere sahip kişisel bir yapay zeka asistanıdır. Kendi lokal ortamınızda veya entegre AI sağlayıcılarıyla (örn: Kobold) çalışabilen araç, hem modern bir web altyapısına hem de klasik masaüstü arayüzüne (Pyside/PyQt tabanlı) sahip gelişmiş bir projedir.

## ✨ Öne Çıkan Özellikler

- **📱 Modern ve Akıcı Arayüz**: WhatsApp tarzı, animasyonlu sağ/sol mesaj balonları ve şık bir deneyim.
- **🧠 Gelişmiş Hafıza (Memory)**: Konuşmaları ve kritik bilgileri aklında tutarak kişiselleştirilmiş bir iletişim sunar.
- **⏰ Hatırlatma Sistemi**: Önemli görevlerinizi tam zamanında size hatırlatır.
- **🎙️ Sesli Komut Desteği**: Klavyeye dokunmadan, sadece konuşarak iletişim kurabilirsiniz.
- **🔌 Online ve Offline Mod**: İhtiyaca göre çevrimiçi veya lokal çevrimdışı modlar arası hızlı geçiş.
- **📊 İstatistikler**: Kullanım verilerinizi, toplam mesaj sayısını ve detayları takip edebileceğiniz panel.
- **🎨 Dinamik Tema**: Aydınlık ve Karanlık mod (Dark/Light theme) geçiş desteği.

---

## 🚀 Kurulum ve Başlangıç

Projeyi test etmek ve hemen kullanmaya başlamak oldukça basittir:

### 1️⃣ Gereksinimler

Modern web arayüzü ile asistanı başlatabilmek için PyQtWebEngine (veya PyQt5/PyQt6) modüllerinin kurulu olması gerekir:

```bash
pip install PyQtWebEngine
```

*(Windows, Linux veya MacOS kurumları ve oluşabilecek hataların çözümü için `KURULUM.md` dosyasına göz atabilirsiniz.)*

### 2️⃣ Çalıştırma

Projeyi çalıştırmak için ana dizindeyken terminale şu komutu girin:

```bash
python main.py
```

Başladıktan sonra konsol üzerinden arayüz tercihinizi yapmanız istenecektir:

- **`1`** tuşlayarak 👉 **Modern Web Arayüzü**'nü (Önerilen)
- **`2`** tuşlayarak 👉 **Klasik Arayüzü**
seçebilirsiniz. (Eğer sisteminizde WebEngine kurulu değilse, Tau otomatik olarak klasik masaüstü arayüzüne geçiş yapacaktır.)

---

## 🛠 Kullanılan Teknolojiler

- **Çekirdek/Backend**: Python
- **Arayüz (GUI)**: PyQt5 / PyQt6, PyQtWebEngine
- **Modern UI Bileşenleri**: HTML5, CSS3, Modern JavaScript
- **AI Backend**: Lokal LLM desteği (Kobold vb.) ve diğer dinamik zeka modülleri.

## 📂 Proje Yapısı (Özet)

- `main.py` / `main_web.py`: Asistanı başlatan ana dosyalarınız.
- `ui/` & `web_ui/`: Masaüstü ve web arayüzlerini oluşturan görünüm dosyaları.
- `features/`: Hatırlatıcı, Kobold AI modülleri ve spesifik yeteneklerin barındığı modüller.
- `database/`: Asistanın hafızasının ve verilerinin tutulduğu klasör.

## 🤝 Katkıda Bulunma

Bu proje, tamamen açık kaynaklı bir formatta geliştirilen kişisel bir asistandır. Dilediğiniz gibi fork edebilir, kendinize özel yeni 'feature'lar ekleyebilirsiniz. Fikirlerinizi Pull Request olarak göndermekten çekinmeyin!

---
> *Tasarım ve geliştirme sürecine dair daha detaylı yapılandırmalar için repo içindeki diğer dokümantasyonlara göz atmayı unutmayın.*
