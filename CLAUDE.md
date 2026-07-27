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
| **Varsayılan model** | Ollama `qwen2.5:7b` (config.json'da aktif; `qwen2.5:3b` kurulu ama kullanılmıyor. Kod içi varsayılanlar hâlâ küçük modele göre yazılı — prompt kuralları gevşetilmemeli) |
| **Çalıştırma** | `python main.py` · `start_tau.bat` · exe: **`C:\Users\memoc\UltronApp\ULTRON\ULTRON.exe`** (OneDrive DIŞINDA — masaüstü/Başlat menüsü/Başlangıç kısayolları buraya bakar) |
| **Otomatik başlatma** | Başlangıç klasöründeki kısayol `--tray` argümanıyla çalışır → pencere açılmaz, doğrudan sistem tepsisine iner |
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
  paths.py                   📁 TEK veri dizini (%APPDATA%\ULTRON) + eski konumdan göç
  tools.py                   🧰 ARAÇ DEFTERİ — Arac / AracSonuc / DEFTER (Faz 0)
  builtin_tools.py           24 yeteneğin araç kaydı (eski if/elif zinciri buraya taşındı)
  planner.py                 🧠 PLANNER (Faz 1) — cümleyi göreve böler, YÜRÜTMEZ
  plan_executor.py           ▶️ Görev kuyruğunu işler, koşulları çözer, onay bekletir
  layers/pipeline_layers.py  14 katmanın tamamı (intent regex'leri burada; execution
                             artık deftere dağıtım yapıyor, ~260 satır zincir kalktı)
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
  file_finder.py             Klasör+tür+isim ile dosya bulma (SADECE üst seviye, os.listdir)
  file_index.py              📇 Tüm PC'yi indeksler (alt klasörler dahil, ayrı file_index.db)
  file_send.py               📎 "bul ve gönder" beyni: ayrıştırma + Telegram/mail/WhatsApp hedefleri
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
`CREATE_REMINDER` · `SCHEDULE_TASK` · `WHATSAPP_MESSAGE` · `EMAIL_MESSAGE` · `FILE_TRANSFER` ·
`FILE_INDEX` · `FILE_SEARCH` · `FILE_OPERATION` · `SCREENSHOT` · `CLIPBOARD` · `FOCUS_MODE` ·
`NOTE_TAKE` · `TIMER` · `CALCULATOR` · `TIME_DATE` · `MORNING_BRIEFING` · `EVENING_REPORT` ·
`ANALYSIS_REPORT` · `GENERAL_CONVERSATION`

> **Sıra önemlidir.**
> • `FILE_SEARCH`, `SYSTEM_CONTROL`'dan ÖNCE gelmeli (yoksa "pdf aç" uygulama açmaya çalışır).
> • `FILE_TRANSFER`, `WHATSAPP_MESSAGE`/`EMAIL_MESSAGE`'dan ÖNCE bakılır — "staj raporunu
>   anneme mail at" ikisine birden benziyor. Çakışmayı `dosya_niyeti_coz` çözer: cümlede
>   güçlü dosya sinyali yoksa (dosya/tür/numara/klasör kelimesi) karar **indekse** sorulur;
>   eşleşme yoksa niyet ALINMAZ ve mesaj akışı bozulmaz. `:` veya "mesaj" geçen cümleler
>   zaten dosya komutu sayılmaz.

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
| **Testler** | Artık `tests/safety.py` zırhı var (27 Tem): OS'a dokunan son adım (subprocess, pycaw, keybd_event, psutil.kill, startfile, webbrowser) taklitle değiştirilir. **Yeni test modülü açarken `setUpModule`'de zırhı kurmayı unutma** — yoksa test gerçekten Chrome kapatır, ses değiştirir. |
| **PyInstaller** | 23 Tem'de OneDrive içindeki `dist` kilitlenip PermissionError verdi → `--distpath C:\Users\memoc\UltronApp --workpath C:\Users\memoc\ultron_build_tmp` ile dışarı alınmıştı. 25 Tem'de tekrar proje içi `dist/`'e derlendi ve sorun çıkmadı. Kilit hatası alırsan yolu yine dışarı taşı. |
| **Uygulama yeri** | 27 Tem'de exe **OneDrive dışına** taşındı: `C:\Users\memoc\UltronApp\ULTRON` (~371 MB). Sebep: OneDrive "İsteğe Bağlı Dosyalar" exe'yi buluta çekerse açılışta otomatik başlatma kırılır. Derleme hâlâ proje içi `dist/`'e çıkar → **derledikten sonra yeni klasörü UltronApp'e taşımayı unutma**, yoksa kısayollar eski sürüme bakar. |
| **exe verisi taşınması** | `pyinstaller --noconfirm` COLLECT'ten önce `dist/ULTRON`'u **komple siler** — exe'nin `_internal` içindeki `config.json`/`bilgiler.db`/`file_index.db` her derlemede yok olur. Taşıdıktan sonra proje kökünden yeniden kopyala (`config.json` exe'nin YANINA, DB'ler `_internal` içine). Kalıcı çözüm: veriyi `%APPDATA%\ULTRON`'a al — **henüz yapılmadı.** |
| **dist boyutu** | Derleme çıktısı ~375 MB. `build/` (~71 MB) hâlâ OneDrive içinde. Git'te değil (`.gitignore`). |
| **Dosya indeksi** | `file_index.db` (~47 MB, 134k dosya) telefondan erişilebilir. Sır taşıyan dosyalar (`GIZLI_ADLAR`/`GIZLI_UZANTILAR`/`GIZLI_KALIPLAR`) indekse HİÇ girmez — bu listeyi zayıflatma. Yeni kök klasör eklerken AppData/Program Files'ı asla ekleme. |
| **Kanal ayrımı** | Dosya arama sonuçları `kanal` başına tutulur (`desktop` / Telegram chat_id). `engine.process(..., kanal=)` geçilmezse telefondaki "2'yi gönder" masaüstünde yapılmış aramanın dosyasını gönderir. |
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
| **Planner sırası** | Planner, ExecutionEngine'den **ÖNCE** çalışır. Sonraya koymak işe yaramaz: canlı testte "önce hava durumuna bak, sonra dövizi söyle, **en son not al**" cümlesini regex `NOTE_TAKE` sanıp içeriği "al" olan saçma bir not kaydetti ve "başarılı" saydığı için planner kapısı hiç açılmadı. **Çok adımlı cümlede tek intent'in kazanması zaten hatadır.** |
| **Planner gecikmesi** | qwen2.5:7b bir plan için ~25 sn harcıyor. Kapı (`cok_adimli_olabilir`) yalnızca açık sıralama/koşul ifadesinde ("sonra", "bulamazsan", "önce") açılır. **Virgülü tetikleyici yapma** — "iyi günler, nasılsın" planlamaya girer. Plan BİR KEZ üretilir; her adımdan sonra LLM'e dönülmez (4 adım = 2 dakika olurdu). |
| **Planner JSON** | `ollama_json` `format` alanına şema verir (grammar-constrained). Şemasız serbest metinden JSON ayıklamaya DÖNME — "plan üretti ama JSON bozuk" hata sınıfı geri gelir. Sağlayıcı Ollama değilse planner kendini kapatır. |

---

## 📏 Geliştirme Kuralları

1. **Deterministik yol her zaman LLM'den önce gelir.** Yeni bir yetenek eklerken önce regex/intent, sonra LLM fallback.
2. **Fare/klavye son çaredir** (AIP felsefesi): URI/AppID → UIA → odak korumalı klavye.
3. **Riskli her eylem onay kartından geçer** (SecurityAnalyzer skoru, tam eşleşme + 60sn timeout). Onaylanan komut **`confirmed_executor`** üzerinden yürütülür.
4. **SQLite thread'ler arası paylaşılamaz** — her çağrı kendi bağlantısını açar.
5. Yeni özellik → `features/` altında ayrı modül, `pipeline_layers.py`'de intent,
   **`core/builtin_tools.py`'de `@arac_kaydet` ile araç kaydı**, `KOMUTLAR.md`'de satır.
6. **Araç yazarken üç durumu karıştırma:** `AracSonuc.islenmedi()` = üstlenmedim, akış
   LLM'e düşsün · `AracSonuc.hata(mesaj)` = denedim olmadı, mesajım kullanıcıya dönsün.
   İkisini karıştırırsan "dosya bulunamadı" LLM'e düşer ve Ultron cevap uydurur.
7. Değişiklikten sonra **bu dosyayı ve `KOMUTLAR.md`'yi güncelle.**

---

## 📊 Durum (son güncelleme: 27 Tem 2026)

### ✅ Çalışan ve canlıda doğrulanmış
WhatsApp gönderimi · Gmail gönderimi · Telegram köprüsü (@Ultrontau_bot: metin, sesli mesaj,
ekran görüntüsü, dosya alma) · TTS (edge, erkek ses) + wake word · sabah brifingi + akşam raporu ·
zamanlanmış görevler · otomatik hafıza · dosya bulucu · pano sihirbazı · pomodoro ·
streaming LLM yanıtı · istatistik sayfası · system tray · tek kopya kilidi · installer/exe.

### 🔨 Eksik kalanlar
1. **Dosya gönderiminin testleri yazılmadı** (kullanıcı "sonra" dedi, 27 Tem). Yazılacaklar:
   parser kalıpları, zayıf-sinyal devretme (`dosya_niyeti_coz`), gizli dosya filtresi,
   kanal ayrımı, onay akışı. Zırh (`tests/safety.py`) burada da kurulmalı — gönderim
   gerçek mail/Telegram trafiği üretir.
2. ~~**exe eski kaldı**~~ → 27 Tem'de yeniden derlendi (dosya gönderimi artık exe'de var).
3. **Push bekliyor** — `5c44597` yerelde. `--tray` değişikliği de commit edilmedi.
   **exe verisi ile python verisi ayrı** — masaüstünden `python main.py` ile konuştuğun
   Ultron ile tepsideki exe **farklı `bilgiler.db`** kullanıyor (27 Tem'de bir kez
   kopyalandı, bundan sonra ayrışacaklar). Tek kaynağa indirmek için veri yolu
   `%APPDATA%\ULTRON`'a alınmalı.
4. Raftakiler: takvim entegrasyonu, Vision/OCR (RAM yetersiz).
5. `ui/tau_window.py` ~72 KB — thread'ler ve controller ayrı dosyalara bölünebilir.

### ✔️ 27 Tem'de kapatılanlar
Commit `43e0103` (24–25 Tem'in tüm işi) · KOMUTLAR.md'ye notlar/hesap/saat/sayaç/medya bölümleri ·
`tests/safety.py` güvenlik zırhı (52 test yeşil, gerçek yan etki YOK) · CLAUDE.md.

---

## 📅 Oturum Günlüğü

| Tarih | Yapılan | Sonuç |
|-------|---------|-------|
| 22 Tem | Backend/thread/onay fixleri, UWP açma, tray, saat parser'ı, AIP kuruldu, WhatsApp gönderimi, sohbet kalıcılığı, brifing, e-posta, istatistikler, Telegram köprüsü, TTS+wake word, halüsinasyon frenleri, STT insanileştirme, internet/hava/döviz düzeltmeleri | ✅ Canlı doğrulandı |
| 23 Tem | Otonom üçlü (zamanlanmış görevler + otomatik hafıza + dosya bulucu), tek kopya kilidi, mikrofon fallback, streaming, pano, pomodoro, tema cilası, **installer (371MB exe)**, Telegram süper paketi (ekran görüntüsü/sesli mesaj/dosya), KOMUTLAR.md | ✅ Commit `ef7cd79`'a kadar |
| 24–25 Tem | `llm_gateway` (LLM UI'dan söküldü — Telegram/görevler artık LLM cevabı alıyor), `llm_intent` (LLM niyet sınıflandırıcı), `memory_rag` (alakaya göre hafıza), `confirmed_executor` (onaylı WA/mail gönderilmiyordu — fix), `quick_tools` (hesap/saat/sayaç/not), `mood.py` yeniden yazıldı, engine'e canlı config, chat_view (girdi geçmişi, kod bloğu, hızlı öneriler, medya butonları) | ⚠️ **Commit edilmedi** |
| 27 Tem | CLAUDE.md yazıldı · 24–25 Tem'in işi commit edildi (`43e0103`) · KOMUTLAR.md'ye 5 yeni bölüm · **`tests/safety.py` güvenlik zırhı** — testler artık Chrome kapatmıyor/ses değiştirmiyor, zırhı kilitleyen 3 test eklendi | ✅ 52 test yeşil (2.9 sn) |
| 27 Tem (5) | **🧠 Faz 1 — PLANNER:** `core/planner.py` (şemaya zorlanmış plan üretimi, doğrulama, kapı) + `core/plan_executor.py` (görev kuyruğu, koşullar, onay bekletme) + `ollama_json` (grammar-constrained JSON). Motor entegrasyonu: planner yürütmeden ÖNCE, sadece çok adımlı cümlede. Kanal başına onay akışı (evet/iptal/konu değişince düş). `tests/test_planner.py` (38 test) | ✅ **138 test yeşil** + canlı 7b testi: "önce hava, sonra döviz" → 2 adımlı plan, ikisi de yürüdü (24.5 sn); "chrome aç" planner'ı görmedi (2.5 sn) |
| 27 Tem (4) | **🧰 Faz 0 — ARAÇ DEFTERİ:** `core/tools.py` + `core/builtin_tools.py`. `ExecutionEngineLayer`'ın ~260 satırlık if/elif zinciri 24 isimli araca bölündü; katman artık sadece intent→araç dağıtımı yapıyor. Üç durumlu `AracSonuc` (islenmedi / hata / ok) eski zincirin iki ayrı başarısızlık anlamını koruyor. `tests/test_tools.py` (37 test) | ✅ **98 test yeşil** + uçtan uca duman testi (saat, hesap, not, odak, chrome aç, ses kıs) |
| 27 Tem (3) | **🖥️ Gerçek uygulama haline getirildi:** exe yeniden derlendi (dosya gönderimi dahil), `main.py`'ye `--tray` bayrağı (açılışta pencere değil tepsi), uygulama OneDrive dışına `C:\Users\memoc\UltronApp\ULTRON`'a taşındı, **3 kısayol** kuruldu (Masaüstü / Başlat menüsü / Başlangıç klasörü), veri dosyaları exe tarafına kopyalandı | ✅ Tepsi modunda çalıştığı doğrulandı (PID canlı, pencere açılmadı) |
| 27 Tem (2) | **📎 Telefondan dosya bul & gönder:** `file_index.py` (134k dosya, 12 sn, alt klasörler dahil, sır filtresi), `file_send.py` (ayrıştırma + Telegram/mail/WhatsApp), `sendDocument`, mail eki (MIMEMultipart), WhatsApp'a pano CF_HDROP + odak korumalı Ctrl+V, `FILE_TRANSFER`/`FILE_INDEX` intent'leri, başkasına gönderimde onay kartı, kanal ayrımı (`ctx.kanal`), 6 saatlik otomatik indeks tazeleme | ✅ **Kullanıcı canlıda doğruladı — "hepsi mis gibi çalışıyor"** (WhatsApp pano yolu dahil). Testler sonraya. |

---

*Bu dosyayı her gün sonunda güncelle — yarın buradan devam edeceğiz.*
