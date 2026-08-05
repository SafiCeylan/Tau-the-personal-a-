# 🔴 ULTRON Neural Core v3.0 — Tau, The Personal AI

ULTRON (eski adıyla **Tau**), bilgisayarınızda **yerel olarak** çalışan, konuşmayı anlayıp
gerçekten **eylem yapan** bir kişisel yapay zekâ asistanıdır. Tamamen **native bir PyQt5
masaüstü uygulamasıdır** — tarayıcı, Electron veya web view bileşeni kullanmaz.

Bulut zorunluluğu yoktur: varsayılan kurulumda dil modeli **Ollama** ile kendi makinenizde
çalışır, hava/döviz/haber servisleri **API anahtarı istemeyen** kaynaklardan gelir
(open-meteo, wttr.in, er-api, Wikipedia, Google News RSS) ve ekran okuma Windows'un
**yerleşik OCR motorunu** kullanır — dışarıya görüntü gönderilmez.

> **Felsefe:** Deterministik önce, LLM sonra. Bir komut regex/araç katmanında
> karşılanabiliyorsa dil modeline hiç gitmez. Fare ve klavye taklidi **son çaredir**.

---

## ✨ Neler Yapabilir?

### 🗣️ Anlama ve Konuşma
- **14 katmanlı komut boru hattı** — girdi → normalizasyon → niyet → varlık çıkarımı →
  hafıza (RAG) → güvenlik → planlama → araç seçimi → yürütme → cevap.
- **Planner motoru** — "şu dosyayı bul ve anneme gönder" gibi çok adımlı cümleleri
  görevlere böler, adımlar arasında bağlam taşır, riskli adımda onay bekler.
- **Streaming yanıt** — cevap yazılırken canlı akar (Ollama).
- **Sesli komut & sesli yanıt** — "Hey Ultron" wake word (yerel Vosk), Google STT,
  TTS için edge-tts (Türkçe erkek ses) / gTTS / SAPI.

### 🧠 Hafıza ve Öğrenme
- **Öğrenme katmanı** — geçmiş konuşma arşivi (FTS5 + BM25 geri çağırma), alışkanlık
  çıkarımı ve **düzeltmeden öğrenme** (anlaşılmayan ifade, sonradan başarılı olan niyete
  bağlanır). Komutlar: `ne öğrendin`, `şunu unut: …`
- **Öneri motoru** — çıkarılan alışkanlığı "bunu her gün 09:00'da senin için kurayım mı?"
  sorusuna çevirir. Kendiliğinden hiçbir şey uygulamaz.
- **Otomatik hafıza** — "en sevdiğim dizi Dark", "İstanbul'da yaşıyorum" gibi cümleler
  konuşma sırasında sessizce kaydedilir.
- **Takma adlar** — "patronum", "annem" gibi ifadeler gerçek kişilere bağlanır.

### 🖥️ Bilgisayar Kontrolü (AIP — Interaction Engine)
- Uygulama aç/kapat (UWP / Microsoft Store uygulamaları dahil), ses seviyesi, medya
  kontrolü, süreç yönetimi, sistem telemetrisi.
- **Kademeli fallback:** Level 1 URI/AppID → Level 2 UI Automation → Level 3 OCR →
  Level 4 odak korumalı klavye. Başarılı yol `capability_cache.json`'a öğrenilir.
- **Pencere odaklama motoru** — komuttaki uygulama/sekme ipucundan doğru pencereyi bulup
  öne getirir.

### 👁️ Ekran Okuma (OCR)
- Windows'un yerleşik `Windows.Media.Ocr` motoruyla **~0.2 saniyede**, model indirmeden ve
  internetsiz ekran anlama.
- "ekranda ne var" → numaralı seçim listesi; "3'ü aç" → doğrudan tıklama.

### 📅 Takvim ve Zaman
- **Yerel takvim** (`takvim_etkinlikleri`) — internetsiz ekle/sil/sorgula.
- **Keysiz iCal/ICS aboneliği** — Google Calendar / Outlook'un "gizli iCal adresi" ile
  tek yönlü okuma (OAuth yok, API anahtarı yok), 30 dakikada bir arka plan senkronu.
- **ICS dışa aktarım** — yerel etkinlikleri `.ics` olarak dışa aktar.
- **Hatırlatmalar** — doğal dille ("yarın 14:00", "cuma akşam 8'de"), toast bildirimi +
  Telegram + sesli uyarı.
- **Zamanlanmış görevler** — `zamanla: 09:30 X`, "her gün 21:00 X"; varsayılan 08:00 sabah
  brifingi ve 22:00 akşam raporu.

### 📨 İletişim
- **WhatsApp mesajı** — kişi rehberi + onay kartı + gönderim doğrulaması.
- **E-posta** — Gmail SMTP, kendi rehberi.
- **Telegram köprüsü** ([@Ultrontau_bot](https://t.me/Ultrontau_bot)) — telefondan tam
  kontrol: metin komutları, sesli mesaj (STT), uzaktan ekran görüntüsü, dosya alıp verme,
  hızlı butonlar, riskli komutlarda inline ✅/❌ onay.

### 📁 Dosyalar
- **Dosya bulucu** — klasör + tür + isim ile hızlı arama.
- **Tüm PC indeksi** — 134 bin dosya ~12 saniyede ayrı bir veritabanına indekslenir;
  sır taşıyan dosyalar indekse hiç girmez.
- **Bul ve gönder** — "staj raporunu anneme mail at" tek cümlede çözülür.

### 🧰 Günlük Araçlar
Sabah brifingi (hava + döviz + hatırlatmalar) · akşam raporu · pano sihirbazı
(oku/özetle/çevir/açıkla) · pomodoro odak modu (ses kısılır, bitince toast) · hesap
makinesi (AST, `eval` yok) · notlar · sayaç · web arama · ruh hâli takibi · istatistik
paneli · özel kısayollar.

### 🛡️ Güvenlik
- Riskli eylemler **onay kartı** ile sorulur (tam eşleşme + 60 sn zaman aşımı).
- Sır taşıyan dosyalar indekslenmez, gönderilmez.
- Öneri motoru kendiliğinden hiçbir şey kurmaz; yalnızca **tek komutla geri alınabilir**
  eylemleri önerir.
- Test zırhı (`tests/safety.py`): testler gerçekten Chrome kapatmaz, ses değiştirmez.

---

## 🚀 Kurulum

### 1️⃣ Gereksinimler

```bash
pip install -r requirements.txt
```

Çekirdek için yalnızca `PyQt5`, `requests`, `psutil`, `rapidfuzz` yeterlidir. Diğer
paketler **opsiyoneldir** — kurulu değilse ilgili yetenek nazikçe devre dışı kalır,
uygulama çalışmaya devam eder (OCR için `winsdk`, ses için `edge-tts`/`PyAudio`,
wake word için `vosk`, UI Automation için `pywinauto`).

### 2️⃣ Dil modeli (Ollama)

```bash
ollama pull qwen2.5:7b
```

Alternatif olarak Gemini, KoboldCPP veya kendi TAU Backend'inizi kullanabilirsiniz.

### 3️⃣ Yapılandırma

`config.example.json` dosyasını `config.json` olarak kopyalayın ve düzenleyin.
**`config.json` git'e gönderilmez** — API anahtarları, SMTP ve Telegram bilgileri içerir.

| Anahtar | Ne işe yarar |
|---|---|
| `ai_provider` · `ollama_url` · `ollama_model` | Dil modeli seçimi |
| `gemini_api_key` · `tau_backend_url` · `kobold_url` | Alternatif sağlayıcılar |
| `smtp_user` · `smtp_pass` | Gmail ile e-posta gönderimi |
| `telegram_token` · `telegram_chat_id` | Telegram köprüsü (whitelist) |
| `tts_enabled` · `tts_engine` (`edge`/`gtts`/`sapi`) | Sesli yanıt |
| `wake_enabled` · `mic_device_index` | "Hey Ultron" ve mikrofon seçimi |
| `llm_intent_enabled` · `reminder_lead_minutes` | Niyet çözümü ve hatırlatma payı |

Bu alanların tamamı uygulama içindeki **Ayarlar** sayfasından da düzenlenebilir.

### 4️⃣ Çalıştırma

```bash
python main.py
```

Windows'ta `start_tau.bat` dosyasına çift tıklayarak da başlatabilirsiniz.
`--tray` argümanıyla açılırsa pencere görünmez, doğrudan sistem tepsisine iner.

*(Detaylı kurulum ve sorun giderme: `KURULUM.md` · Tüm komutların kopya kâğıdı: `KOMUTLAR.md`)*

---

## 🏗️ Mimari

```
main.py  ── tek-kopya kilidi (QLocalServer) → DatabaseManager → TauMainWindow
   │
   ▼
ui/tau_window.py  ── pencere + tray + tüm worker thread'ler
   │   AIWorker / StreamWorker / EngineWorker / WakeWord / Listen / Telegram / Func
   ▼
core/engine.py  UltronCoreEngine.process()  ── 14 KATMANLI BORU HATTI
   │
   L1 InputCapture → L2 Normalization → L3 IntentAnalyzer → L4 EntityExtraction
   → L5 MemoryContext (RAG) → L6 SecurityAnalyzer → L7 TaskPlanner → L8 ToolSelection
   → L12 ExecutionEngine → L9 PromptGenerator → L10 LLMCore → L11 ActionPlanner
   → L13 ResultChecker → L14 ResponseBuilder
   ▼
features/*  ── yetenek modülleri     database/bilgiler.db (SQLite)
```

**İki çalışma modu:**
- **Masaüstü:** `process(allow_llm=False)` → zenginleştirilmiş prompt üretilir, UI cevabı
  streaming ile akıtır.
- **Telegram / zamanlanmış görev:** `process(allow_llm=True)` → cevap engine içinde üretilir.

## 📂 Proje Yapısı

```
main.py                 Giriş noktası + tek kopya kilidi
core/
  engine.py             14 katmanı sırayla çalıştırır
  layers/               Katmanların tamamı (intent regex'leri burada)
  planner.py            Cümleyi göreve böler (yürütmez)
  plan_executor.py      Görev kuyruğu, koşullar, onay bekletme
  tools.py              Araç defteri  ·  builtin_tools.py  24 yeteneğin kaydı
  context_manager.py    "onu gönder" hangi dosya?      recovery.py  Alternatif üretimi
  world_state.py        Açık pencereler, pil, internet, pencere odaklama
  interaction/          AIP — Level 1 URI → 2 UIA → 3 OCR → 4 klavye fallback zinciri
features/
  chat_learning.py      Öğrenme katmanı      suggestions.py     Öneri motoru
  calendar_tools.py     Takvim + ICS         scheduler.py       Zamanlanmış görevler
  telegram_bridge.py    Telegram köprüsü     speech.py          TTS + STT + wake word
  screen_reader.py      OCR ekran okuma      file_index.py      PC geneli dosya indeksi
  actions/              Sistem kontrolü, WhatsApp                (+ 20'den fazla modül)
ui/
  tau_window.py         Ana pencere + thread'ler + AssistantController
  components/           Sohbet, ayarlar, istatistik, hafıza, hatırlatma, mod sayfaları
  ai_core_widget.py     QPainter holografik çekirdek animasyonu
  styles/theme.py       ULTRON kırmızı teması (#ff1a26 / #060305)
database/schema.sql     SQLite şeması (hafıza, sohbet, hatırlatma, görev, takvim…)
tests/                  631 test — safety.py zırhı gerçek yan etkileri engeller
archive/                Ölü modüller ve eski arayüz denemeleri (kullanılmıyor)
```

---

## 🧪 Testler

```bash
python -m pytest tests/ -q
```

**631 test, ~23 saniye.** Yeni test modülü açarken `setUpModule` içinde
`tests/safety.py` zırhını kurmayı unutmayın — yoksa testler gerçekten uygulama kapatır,
ses seviyesi değiştirir.

## 🛠 Kullanılan Teknolojiler

- **Çekirdek:** Python 3.12, SQLite
- **Arayüz:** PyQt5 — native widget'lar + QPainter (web view yok)
- **Dil modeli:** Ollama (`qwen2.5:7b`), Gemini, KoboldCPP veya özel TAU Backend
- **Ses:** edge-tts · gTTS · SAPI · SpeechRecognition · Vosk (yerel wake word)
- **Otomasyon:** pywinauto (UI Automation) · Windows.Media.Ocr · mss · winotify

## 🤝 Katkıda Bulunma

Bu proje açık kaynak olarak geliştirilen kişisel bir asistandır. Fork edip kendinize özel
yetenekler ekleyebilirsiniz. Fikirlerinizi Pull Request olarak göndermekten çekinmeyin.

---
> *Geliştirme notları, mimari kararlar ve "acı çekerek öğrenilmiş" tuzaklar için depo
> içindeki `CLAUDE.md` dosyasına göz atın.*
