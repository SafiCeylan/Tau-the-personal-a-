# 🔴 CLAUDE.md — ULTRON Neural Core | Proje Hafızası

> Bu dosya, Claude ile her oturuma hızlı başlamak içindir.
> **Her gün sonunda "Oturum Günlüğü" + "Durum" bölümleri güncellenir.**

---

## 📌 Kimlik

| | |
|---|---|
| **Proje** | ULTRON Neural Core v3.0 (eski adı TAU) — native PyQt5 masaüstü AI asistanı |
| **Yol** | `C:\Users\memoc\OneDrive\Desktop\Projeler\tau` |
| **Geliştirici** | Mehmet Safi Ceylan (SafiCeylan / memoc) |
| **Yığın** | Python + PyQt5 (QPainter, web view YOK) + SQLite + Ollama |
| **Varsayılan model** | Ollama `qwen2.5:3b` (küçük model — halüsinasyona meyilli, prompt kuralları sıkı) |
| **Çalıştırma** | `python main.py` · `start_tau.bat` · exe: `C:\Users\memoc\UltronApp\ULTRON\ULTRON.exe` |
| **Diğer dokümanlar** | `KOMUTLAR.md` (kullanıcı kopya kağıdı) · `KURULUM.md` · `README.md` |

---

## 🏗️ Mimari

```
main.py  ── tek-kopya kilidi (QLocalServer) → DatabaseManager → TauMainWindow
   │
   ▼
ui/tau_window.py  ── pencere + tray + TÜM worker thread'ler
   │   AIWorkerThread / StreamWorkerThread / EngineWorkerThread
   │   WakeWordThread / ListenWorkerThread / TelegramWorkerThread / FuncWorkerThread
   │   AssistantController  ← UI ile çekirdek arasındaki köprü
   ▼
core/engine.py  UltronCoreEngine.process()  ── 14 KATMANLI ARDIŞIK BORU HATTI
   │
   L1 InputCapture → L2 Normalization → L3 IntentAnalyzer → L4 EntityExtraction
   → L5 MemoryContext (RAG) → L6 SecurityAnalyzer → L7 TaskPlanner → L8 ToolSelection
   → L12 ExecutionEngine → L9 PromptGenerator → L10 LLMCore → L11 ActionPlanner
   → L13 ResultChecker → L14 ResponseBuilder
   │
   ▼
features/*  ── yetenek modülleri (aşağıdaki haritaya bak)
database/bilgiler.db (SQLite)
```

**Akışın iki modu var:**
- **Masaüstü:** `process(allow_llm=False)` → `enriched_prompt` bırakılır, UI `StreamWorkerThread` ile cevabı akıtır (streaming imleç).
- **Telegram / zamanlanmış görev:** `process(allow_llm=True)` → LLM cevabı engine içinde üretilir, `final_output` hazır gelir.

**Deterministik önce, LLM sonra:** Bir komut regex/execution katmanında karşılanıyorsa LLM'e HİÇ gitmez. Regex kaçırırsa `features/llm_intent.py` devreye girer (LLM sınıflandırıcı). O da bulamazsa serbest sohbet.

---

## 📁 Dosya Haritası

```
main.py                      Giriş noktası + tek kopya kilidi (ULTRON_NEURAL_CORE_SINGLE_INSTANCE)
core/
  engine.py                  14 katmanı sırayla çalıştırır; update_config() ile canlı ayar
  context.py                 UltronContext — katmanlar arası taşınan tek veri nesnesi
  layers/pipeline_layers.py  14 katmanın tamamı (intent regex'leri + execution burada)
  layers/routine_engine.py   Modlar/rutinler (çalışma modu, dinlenme modu…)
  layers/self_reflection.py  Öz-değerlendirme
  interaction/               AIP — ULTRON Interaction Engine (fare/klavye SON çare)
    decision_engine.py       Fallback zinciri + capability_cache.json
    level1_native.py         URI / AppID ile doğrudan (en makbul yol)
    level2_uia.py            pywinauto UI Automation
    level4_input.py          ODAK KORUMALI klavye (en son çare)
features/
  llm_gateway.py             LLM sağlayıcı seçimi — TEK KAPI (UI'dan bağımsız)
  llm_intent.py              Regex'in kaçırdığını LLM ile sınıflandırır (Ollama yoksa None)
  memory_rag.py              Mesaja EN ALAKALI hafızaları getirir (offline skor + ops. embedding)
  confirmed_executor.py      Onaylanan komutu DOĞRU modüle yönlendirir (WA/mail/sistem)
  quick_tools.py             Hesap makinesi (AST, eval YOK) · saat/tarih · sayaç · notlar
  actions/system_control.py  Ses, uygulama aç/kapat, süreç, telemetri, UWP (shell:AppsFolder)
  actions/whatsapp_control.py  whatsapp://send + UIA "Gönder" + odak korumalı Enter + doğrulama
  email_control.py           Gmail SMTP + email_kisiler rehberi
  telegram_bridge.py         Saf requests long-polling (kütüphanesiz), whitelist, inline onay
  speech.py                  TTS (edge-tts tr-TR-AhmetNeural varsayılan) + STT + wake word (Vosk)
  briefing.py                Sabah brifingi (hava + döviz + hatırlatmalar)
  scheduler.py               zamanli_gorevler tablosu + akşam raporu
  auto_memory.py             "en sevdiğim dizi Dark" gibi cümlelerden otomatik hafıza
  file_finder.py             Klasör+tür+isim ile dosya bulma (registry'den gerçek klasör yolları)
  clipboard_tools.py         Pano oku/özetle/çevir/açıkla
  web_search.py              Wikipedia + DDG Instant Answer + Google News RSS
  screenshot_tool.py         mss ile ekran görüntüsü
  mood.py                    Ağırlıklı TR duygu sözlüğü + olumsuzlama + emoji
  ollama.py / gemini.py / kobold.py / tau_backend.py   LLM sağlayıcıları
ui/
  tau_window.py              Ana pencere + tüm thread'ler + AssistantController (~70 KB, en büyük dosya)
  components/                chat_view, sidebar, settings_view, stats_view, mood_view,
                             memory_view, reminders_view, modes_view, ultron_focus_view
  styles/theme.py            ULTRON kırmızı tema (#ff1a26 / #060305)
  ai_core_widget.py          QPainter holografik çekirdek animasyonu
database/schema.sql          bilgiler · kategoriler · sohbet_gecmisi · ogrenme_metrikleri ·
                             memory · hatirlatmalar · custom_routines · ruh_hali_gecmisi ·
                             zamanli_gorevler · notlar
archive/                     Ölü modüller ve eski web-view arayüzler (kullanılmıyor)
```

---

## 🎯 Intent Listesi (`pipeline_layers.py`)

`PLAY_MUSIC` · `MEDIA_CONTROL` · `SYSTEM_CONTROL` · `WEB_SEARCH` · `WEATHER` · `CURRENCY` ·
`CREATE_REMINDER` · `SCHEDULE_TASK` · `WHATSAPP_MESSAGE` · `EMAIL_MESSAGE` · `FILE_SEARCH` ·
`FILE_OPERATION` · `SCREENSHOT` · `CLIPBOARD` · `FOCUS_MODE` · `NOTE_TAKE` · `TIMER` ·
`CALCULATOR` · `TIME_DATE` · `MORNING_BRIEFING` · `EVENING_REPORT` · `ANALYSIS_REPORT` ·
`GENERAL_CONVERSATION`

> **Sıra önemlidir.** `FILE_SEARCH`, `SYSTEM_CONTROL`'dan ÖNCE gelmeli (yoksa "pdf aç" uygulama açmaya çalışır).

---

## ⚙️ Config (`config.json` — git'te YOK, `config.example.json`'dan kopyalanır)

`ai_provider` · `ollama_url` · `ollama_model` · `gemini_api_key` · `tau_backend_url` ·
`smtp_user` / `smtp_pass` · `telegram_token` / `telegram_chat_id` ·
`tts_enabled` / `tts_engine` (edge|gtts|sapi) · `wake_enabled` · `mic_device_index` ·
`llm_intent_enabled` · `reminder_lead_minutes`

Git izlemesinde OLMAYAN dosyalar: `config.json`, `user_data.json`, `app_cache.json`,
`capability_cache.json`, `bilgiler.db`, `models/` (Vosk TR modeli ~50MB), `dist/`, `build/`.

---

## 🚨 ÖNEMLİ TUZAKLAR (acı çekerek öğrenildi — tekrar düşme)

| Konu | Kural |
|------|-------|
| **Testler** | `tests/test_all_features.py` **MOCK'SUZ — gerçek yan etki üretir.** "chrome kapat" testi Chrome'u GERÇEKTEN kapatır, ses seviyesini GERÇEKTEN değiştirir. Kullanıcıya sormadan çalıştırma. |
| **PyInstaller** | **OneDrive içinde derleme YAPMA** — dist kilitlenir, PermissionError. `--distpath C:\Users\memoc\UltronApp --workpath C:\Users\memoc\ultron_build_tmp` |
| **PyInstaller excludes** | sklearn/scipy/pandas/networkx ortamdan sızıp 1GB yapıyordu → excludes. Ama **setuptools DIŞLANAMAZ** (pygame pkg_resources → jaraco çöker). |
| **exe verisi** | exe kendi `_internal` klasöründe yaşar — config/DB python sürümüyle **paylaşılmaz**. |
| **aiodns** | `aiodns 4.0.0` Windows'ta "Could not contact DNS servers" ile edge-tts'i kırar. **requirements'a EKLEME.** |
| **Klasör yolları** | Masaüstü/Belgeler/Resimler OneDrive'da ve **yerelleştirilmiş adlı** ("Belgeler"). Ev dizini varsayma → registry `User Shell Folders`'tan çöz. |
| **Türkçe kesme işareti** | Tek tırnak alıntı SAYILMAZ ("pdf'i", "masaüstündeki'deki") — alıntı regex'ini kandırır. |
| **Wake word** | Vosk sözlüğünde "ultron" YOK → gramer `["hey ultra","ultra","[unk]"]` ile fonetik komşudan yakalanıyor. |
| **Mikrofon** | BT kulaklık "Invalid number of channels" (PaError -9998) verebilir → sistem varsayılanına fallback, dinleyici çökmemeli. |
| **Tek kopya** | Tray'de yaşayan eski kopya + yeni kopya aynı Telegram botunu dinleyince "Conflict: terminated by other getUpdates". Kilit `main.py`'de. |
| **PowerShell commit** | Çok satırlı commit mesajında here-string bozulur → `git commit -F dosya` kullan. |
| **Küçük model** | qwen2.5:3b eylemi yapmış gibi rol yapar. PromptGenerator'daki katı kurallar ("ASLA yapmış gibi anlatma") silinmemeli. |

---

## 📏 Geliştirme Kuralları

1. **Deterministik yol her zaman LLM'den önce gelir.** Yeni bir yetenek eklerken önce regex/intent, sonra LLM fallback.
2. **Fare/klavye son çaredir** (AIP felsefesi): URI/AppID → UIA → odak korumalı klavye.
3. **Riskli her eylem onay kartından geçer** (SecurityAnalyzer skoru, tam eşleşme + 60sn timeout). Onaylanan komut **`confirmed_executor`** üzerinden yürütülür.
4. **SQLite thread'ler arası paylaşılamaz** — her çağrı kendi bağlantısını açar.
5. Yeni özellik → `features/` altında ayrı modül, `pipeline_layers.py`'de intent, `KOMUTLAR.md`'de satır.
6. Değişiklikten sonra **bu dosyayı ve `KOMUTLAR.md`'yi güncelle.**

---

## 📊 Durum (son güncelleme: 27 Tem 2026)

### ✅ Çalışan ve canlıda doğrulanmış
WhatsApp gönderimi · Gmail gönderimi · Telegram köprüsü (@Ultrontau_bot: metin, sesli mesaj,
ekran görüntüsü, dosya alma) · TTS (edge, erkek ses) + wake word · sabah brifingi + akşam raporu ·
zamanlanmış görevler · otomatik hafıza · dosya bulucu · pano sihirbazı · pomodoro ·
streaming LLM yanıtı · istatistik sayfası · system tray · tek kopya kilidi · installer/exe.

### 🔨 Eksik kalanlar
1. **Commit yok** — 24–25 Tem'in tüm işi (5 yeni modül + 21 değişmiş dosya) çalışma ağacında duruyor.
2. **exe eski** (23 Tem build'i) — yeni modüller exe'de yok, yeniden derlenmeli.
3. **KOMUTLAR.md eksik** — hesap makinesi, notlar, sayaç, saat komutları rehberde yok.
4. **Testler mock'suz** — gerçek yan etki üretiyor, izole edilmeli.
5. Raftakiler: takvim entegrasyonu, Vision/OCR (RAM yetersiz).

---

## 📅 Oturum Günlüğü

| Tarih | Yapılan | Sonuç |
|-------|---------|-------|
| 22 Tem | Backend/thread/onay fixleri, UWP açma, tray, saat parser'ı, AIP kuruldu, WhatsApp gönderimi, sohbet kalıcılığı, brifing, e-posta, istatistikler, Telegram köprüsü, TTS+wake word, halüsinasyon frenleri, STT insanileştirme, internet/hava/döviz düzeltmeleri | ✅ Canlı doğrulandı |
| 23 Tem | Otonom üçlü (zamanlanmış görevler + otomatik hafıza + dosya bulucu), tek kopya kilidi, mikrofon fallback, streaming, pano, pomodoro, tema cilası, **installer (371MB exe)**, Telegram süper paketi (ekran görüntüsü/sesli mesaj/dosya), KOMUTLAR.md | ✅ Commit `ef7cd79`'a kadar |
| 24–25 Tem | `llm_gateway` (LLM UI'dan söküldü — Telegram/görevler artık LLM cevabı alıyor), `llm_intent` (LLM niyet sınıflandırıcı), `memory_rag` (alakaya göre hafıza), `confirmed_executor` (onaylı WA/mail gönderilmiyordu — fix), `quick_tools` (hesap/saat/sayaç/not), `mood.py` yeniden yazıldı, engine'e canlı config, chat_view (girdi geçmişi, kod bloğu, hızlı öneriler, medya butonları) | ⚠️ **Commit edilmedi** |
| 27 Tem | CLAUDE.md yazıldı | ✅ |

---

*Bu dosyayı her gün sonunda güncelle — yarın buradan devam edeceğiz.*
