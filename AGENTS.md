# 🔴 AGENTS.md — ULTRON Neural Core | Proje Hafızası

> Bu dosya, Codex ile her oturuma hızlı başlamak içindir.
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
  context_manager.py         🧭 CONTEXT MANAGER (Faz 2) — "onu gönder" hangi dosya?
  recovery.py                🛟 RECOVERY ENGINE (Faz 4) — başarısızlıkta alternatif üretir
  aliases.py                 🧠 TAKMA ADLAR (Faz 3) — "patronum" → Ahmet Kaya
  world_state.py             🌍 WORLD STATE (Faz 6) — ne açık, pil, internet
  reflection.py              🔍 REFLECTION (Faz 8) — kanıt kontrolü + halüsinasyon freni
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
  chat_learning.py           🧠 ÖĞRENME KATMANI — geçmiş sohbet arşivi (ayrı ogrenme.db):
                             FTS5 geri çağırma · örüntü çıkarımı · düzeltmeden öğrenme
                             · ruh hâli damgası (tur ile aynı satırda)
  suggestions.py             💡 ÖNERİ MOTORU — örüntüyü "kurayım mı?" sorusuna çevirir
                             (zamanlanmış görev / kısayol). Kararlar oneriler.json'da.
  custom_shortcuts.py        Kullanıcının canlı eklediği özel kısayollar (JSON)
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

`PLAY_MUSIC` · `MEDIA_CONTROL` · `SYSTEM_CONTROL` · `SET_VOLUME` · `WEB_SEARCH` · `WEATHER` ·
`CURRENCY` · `CREATE_REMINDER` · `SCHEDULE_TASK` · `WHATSAPP_MESSAGE` · `EMAIL_MESSAGE` ·
`FILE_TRANSFER` · `FILE_INDEX` · `FILE_SEARCH` · `FILE_OPERATION` · `SCREENSHOT` · `CLIPBOARD` ·
`FOCUS_MODE` · `NOTE_TAKE` · `TIMER` · `CALCULATOR` · `TIME_DATE` · `KEYBOARD_INPUT` ·
`MORNING_BRIEFING` · `EVENING_REPORT` · `ANALYSIS_REPORT` · `LEARNING_REPORT` ·
`GENERAL_CONVERSATION`

> **Sıra önemlidir.**
> • `LEARNING_REPORT` ("ne öğrendin", "şunu unut: …", "önerilerin", "1. öneriyi uygula")
>   dosya niyetinden ÖNCE bakılır — "öğrendiklerini göster" cümlesindeki "göster"
>   fiili dosya aramasına benziyor.
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
| **Bağlam ikamesi** | Context Manager referansı METİN İKAMESİYLE çözer ("onu gönder" → "ULTRON.spec dosyasını gönder"), çünkü tüm araçlar ham cümlede regex çalıştırıyor. Dosya ikamesine **"dosyasını" eki şart**: çıplak dosya adı hiçbir dosya aracına gitmiyor, `SYSTEM_CONTROL`'a düşüp "ULTRON.spec adlı uygulamayı aç" sanılıyor (canlı testte görüldü). |
| **Bağlam sessiz olamaz** | Her ikame kullanıcıya bildirilir (`_(bağlamdan: 'onu' → X)_`). Sessiz tahmin, yanlış dosyanın fark edilmeden gönderilmesi demektir. Bağlam bayatsa (15 dk) ÇÖZÜLMEZ — sorulur. |
| **"aç" fiili çakışması** | `file_send`'de `ac` işlemi var ama **yalnızca güçlü dosya sinyalinde** üretilir. Bu koşul kalkarsa "chrome aç" indekste chrome.exe bulup dosya açmaya kalkar ve uygulama başlatma bozulur. `tests/test_dosya_ac.py` bunu kilitler. |
| **sadelestir & Türkçe** | `file_send` kalıpları `file_index.sadelestir()` ÇIKTISI üzerinde çalışır: `aç`→`ac`, `göster`→`goster`. **Kalıplara Türkçe harf yazma, eşleşmez.** (`_ARAMA_FIILLERI` içindeki `'göster'` bu yüzden ölü kalıp — düzeltilirse "göster" komutu yeni davranış kazanır, bilerek dokunulmadı.) Çıplak `ac` alt dizisi "ihtiyac"/"acele" içinde geçtiği için kelime sınırı (`\bac\b`) şart. |
| **"başarılı" ≠ "hedefe ulaştı"** | `AracSonuc` üç sinyal taşır: `islendi` (üstlendim mi), `basarili` (düzgün çalıştım mı), `hata_tipi` (hedefe ulaştım mı). **"Dosya bulunamadı" BAŞARILI bir çıktıdır** — `ui/tau_window.py` mesajı sadece `execution_success=True` iken gösterir; başarısız yaparsan mesaj kaybolur ve cevabı LLM üretir → Ultron olmayan dosyayı bulmuş gibi anlatır. Kurtarma `hata_tipi`'ne bakar. Motorda **başarıyı aşağı çekme** (`kurtarma.basarili or ctx.execution_success`). |
| **Kurtarma riskli araç çalıştıramaz** | `core/recovery.py` yalnızca `RISK_GUVENLI` araç çağırır. "Gönderim başarısız, tekrar deneyeyim" aynı dosyayı iki kez göndermektir. Riskli araç başarısızsa kurtarma sadece TEŞHİS yapar (`teshis=True`) — bulur, gösterir, kararı kullanıcıya bırakır. |
| **Yansıma sonucu tersine çevirmez** | `core/reflection.py` yalnızca KESİN kanıtla (dosya diskte yok) başarıyı başarısıza çevirir; belirsizlikte sadece not düşer. Belirsiz kanıtla "aslında olmadı" demek, çalışan işi başarısız göstermektir — hiç kontrol etmemekten kötü. **Doğrulayıcı listesine "belki" niteliğinde kanıt EKLEME.** |
| **Yansıma LLM'e sormaz** | "Gerçekten oldu mu?" sorusunu modele sormak işe yaramaz: eylemi uyduran model kontrolü de uydurur. Deterministik kanıt aranır (dosya var mı, kayıt DB'de mi). |
| **"Zaten açık" komutu iptal etmez** | World State yalnızca MESAJI değiştirir; başlatıcı yine çağrılır (Windows'ta mevcut pencereyi öne getirir). "Zaten açık" deyip hiçbir şey yapmamak kullanıcının komutunu sessizce yutmaktır — yanlış tespitte Ultron bozulmuş görünür. **Şüphedeysen işi yap.** |
| **İnternet kontrolü alan adıyla** | `internet_var_mi` ham IP'ye (8.8.8.8) bağlanmayı DENEMEZ: bu makinede ağ doğrudan IP'yi engelliyor, alan adı 0.05 sn'de geçiyor. İlk sürüm "internet YOK" dedi, oysa vardı. İnternet varken "yok" demek Ultron'un çalışan araçlardan vazgeçmesine yol açar. |
| **Takma adda bulanık eşleşme YASAK** | `core/aliases.py` yalnızca tam eşleşme + Türkçe yönelme eki çözer. Dosyada bulanık eşleşme yanlış dosya gösterir (rahatsız edici); **kişide yanlış insana mesaj gönderir (telafisi yok)**. `patron`, `patronumun`, `patronlar` → çözülmez. |
| **Takma ad sohbetten öğrenilmez** | Sadece açık öğretim ("X Y demek", "X = Y", "X aslında Y", "X Y'dir"). "Bugün patronla tartıştım, Ahmet sinirliydi" cümlesinden patron=Ahmet çıkarmak, bir gün yanlış kişiye mesaj göndermektir. **Kalıp eklerken "kullanıcı bunu kasten mi söyledi?" sorusunu geçmeli.** |
| **Rehber takma addan önce** | `kisi_coz`/`email_coz` önce rehbere bakar; takma ad SON ÇARE. Doğrudan kayıt daha açık bir niyettir. |
| **Kimlik onay kartında görünür** | `kimlik_zinciri()` onay kartına "patronuma → **Ahmet Kaya**" yazar. Bu süs değil güvenlik özelliğidir: kullanıcı onaylamadan önce KİMİN kastedildiğini görmeli. Kartlardan bu satırı kaldırma. |
| **Daraltma sahiplenmesi** | "Hangisi?" sorusuna gelen kısa cevap arama terimi sayılır — ama **yalnızca gerçekten dosya bulunursa**. Bulamazsa cümle sahiplenilmez, LLM'e düşer; yoksa "teşekkürler" arama sanılır ve kullanıcı sohbet edemez. Bayrak (`daraltma_bekliyor`) **başarısız denemede de düşer**: yoksa konuşma boyunca her kısa cümle arama terimi sanılır. |
| **Seçim numarası GENEL sıradır** | Sayfalamada 2. sayfa 11'den başlar. `sonuctan_sec` saklanan `offset`i düşer; düşmezse "12'yi gönder" **yanlış dosyayı gönderir** — sessiz ve tehlikeli. `tests/test_sayfalama.py` bunu kilitler. |
| **Gösterilen ≠ toplam** | `sonuclari_bicimle`'ye `toplam` geçilmezse gösterilen sayıyı toplam sanar. Önceden 26 eşleşmede "10 sonuç" yazıyor, kalan 16'yı gizliyordu. Yeni arama yolu ekleyeceksen `file_index.sonuc_sayisi()` ile toplamı da geçir. |
| **Gevşetmeyi indeks seçer** | Kurtarmanın "adı gevşet" adımı hangi kelimeyle arayacağına **indekse sorarak** karar verir. Saf metin sezgisi ("en uzun kelime") canlıda İKİ KEZ yanlış seçti: önce `dosyasını` (Türkçe ı, ASCII listeyle eşleşmedi), sonra `falan` (dolgu kelimesi, "staj"dan uzun). Zayıf kelime listesi ASCII yazılır, karşılaştırma `sadelestir()` çıktısında yapılır. |
| **indeks_ara neden var** | Kurtarmanın "adı gevşetip tekrar ara" adımı `dosya_ara`yı KULLANAMAZ (o klasör bazlı `file_finder`, indekse gitmez) ve `dosya_gonder`i de kullanamaz (RISK_ONAY). Bu yüzden salt-okunur `indeks_ara` aracı eklendi. |
| **os.startfile = çalıştır** | `.exe/.bat/.ps1/.msi/.lnk` "açmak" onları ÇALIŞTIRIR. `calistirilabilir_mi()` bunları yakalar, güvenlik katmanı CONFIRM verir. Onaylı çağrı `dosya_komutu_isle(..., onaylandi=True)` ile gelmeli — yoksa file_send tekrar onay ister ve **sonsuz onay döngüsü** olur. |
| **Öğrenme arşivi sızıntı yoludur** | `ogrenme.db` içeriği prompt'a, prompt da Telegram'a dönüyor. `SIR_KALIPLARI` (şifre/PIN/token) filtresi bu yüzden var — **zayıflatma**. `level4_input.pin_maskele` ile aynı gerekçe. |
| **Öğrenilen kalıp sessiz olamaz** | Öğrenilmiş bir kalıp niyeti belirlediyse cevabın başına `_(🧠 öğrenilmiş kalıp: …)_` yazılır. Sessiz uygulanan yanlış kalıp, kullanıcının fark edemeyeceği bir hatadır — görürse `şunu unut: …` diyebilir. |
| **Mesaj gönderen niyet öğrenilmez** | `OGRENILEBILIR_INTENTLER` listesinde WhatsApp/mail/dosya/klavye/hatırlatma YOK. Yanlış kalıp burada **yanlış kişiye mesaj** demektir (telafisi yok) — `core/aliases.py` bulanık eşleşme yasağıyla aynı gerekçe. |
| **Tek gözlem alışkanlık değildir** | Kalıp 2 gözlemde aktifleşir, örüntü 3 gözlemde rapora girer. Aynı ifade iki farklı niyete bağlanırsa kalıp **düşürülür** (kararsız kalıp = yanlış komut). |
| **Kanal öneki komutun parçası değil** | Telegram mesajları `[Telegram] ` önekiyle geliyor. `chat_learning.sadelestir` bunu atar; atmazsa aynı komut iki ayrı komut sayılır, "telegram" en sık konu görünür (gerçek ölçümde 66 kez) ve telefonda öğrenilen kalıp masaüstünde eşleşmez. |
| **Testler kalıcı veriyi de kirletir** | `tests/safety.py` artık `chat_learning._db_yolu`'nu geçici dizine yönlendiriyor. Zırhsız çalıştırılan testler kullanıcının GERÇEK öğrenme arşivine test cümlesi yazıyordu (233 KB'lık kirlenme yaşandı). **Zırh yalnızca OS'u değil kalıcı veriyi de korur.** |
| **Geçmiş niyeti tahminidir** | Eski `sohbet_gecmisi` satırlarında niyet/başarı tutulmuyordu; göç sırasında bugünkü regex zinciriyle (`arsiv_niyeti_tahmin_et`, `hafif=True`) tahmin edilir, başarı ise cevaptaki hata izlerinden okunur. Sezgidir — kesin veri gibi sunma. |
| **Planner JSON** | `ollama_json` `format` alanına şema verir (grammar-constrained). Şemasız serbest metinden JSON ayıklamaya DÖNME — "plan üretti ama JSON bozuk" hata sınıfı geri gelir. Sağlayıcı Ollama değilse planner kendini kapatır. |
| **Öneri kendiliğinden uygulanmaz** | `features/suggestions.py` hiçbir şey KURMAZ, sorar. Kullanıcı "uygula" demeden görev/kısayol oluşmaz — sessiz uygulanan yanlış çıkarım, fark edilemeyen hatadır (öğrenilmiş kalıp ve takma ad yasaklarıyla aynı gerekçe). Belirsiz seçimde ("kabul et", 2 öneri var) tahmin YOK, sorulur. |
| **Doğrulanamayan öneri sunulmaz** | Zamanlama önerisi ancak kurulu görevler OKUNABİLDİĞİNDE üretilir. `_mevcut_gorevler` hata hâlinde boş küme değil **None** döner: "bilmiyorum" ile "hiç yok" karıştırılırsa kullanıcıya ikinci kopya kurdurulur. |
| **Öneri numarası GÖSTERİLEN sıradır** | "2. öneriyi uygula" `oneriler.json`'daki `son_liste`'den çözülür. Yeniden üretilen sıraya uygulamak, arşiv değiştiğinde YANLIŞ öneriyi sessizce kurar — `file_send` sayfalamasındaki dersin aynısı. |
| **Reddedilen geri gelmez** | Karar kalıcıdır. Aynı şeyi tekrar sormak asistanı dırdıra çevirir; kabul edilen zaten kurulu olduğu için üretimden de düşer. |
| **Ekrana `sade` basma** | `sik_komut['sade']` ASCII'dir ("hava nasil") ve hem raporda bozuk görünür hem de komut olarak geri oynatılırsa Türkçe harfli niyet regex'lerine EŞLEŞMEZ. Kullanıcıya gösterilen/geri oynatılan metin `ornek` sütunundan gelir — ama **ham `kullanici` sütunu kanal önekini taşır**, bu yüzden `ornek` her zaman `kanalsiz()`'den geçer. Canlı testte (3 Ağu) tam bu yüzden öneriye "[Telegram] Ekran görüntüsü" sızdı; kabul edilseydi hiçbir niyete eşleşmeyen bir kısayol kurulacaktı. |
| **Aynı iş için tek öneri** | "Ekran görüntüsü" (49 kez) ve "ekran görüntüsü al" (17 kez) aynı şeyin iki söyleyişi; ikisini birden sormak listeyi çöpe çevirir. Kısayol önerisi **niyet başına bir tane** (en sık söyleyiş kazanır), zamanlama önerisi varsa kısayol hiç sorulmaz. |
| **Ruh hâli prompt'a girmez** | Arşivdeki duygu damgası RAPORA girer, `profil_satirlari`'na (prompt) girmez. Modele "kullanıcı gergin" demek onu terapiste çevirir; küçük model zaten yoruma hevesli. Yoğunlaşma yoksa (dilim payı <%50) örüntü olarak da sunulmaz. |
| **Zırh JSON'u da korur** | `tests/safety.py` artık `suggestions._dosya_yolu` ve `custom_shortcuts._dosya_yolu` yamalıyor. Öğrenme raporu öneri ürettiği için raporu çağıran her test gösterilen listeyi diske yazıyordu; kısayol önerisini kabul eden bir test kullanıcının menüsüne gerçek buton ekliyordu. |

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

## 📊 Durum (son güncelleme: 5 Ağu 2026)

### ✅ Çalışan ve canlıda doğrulanmış
WhatsApp gönderimi · Gmail gönderimi · Telegram köprüsü (@Ultrontau_bot: metin, sesli mesaj,
ekran görüntüsü, dosya alma, hızlı butonlar + slash komutlar) · uzaktan klavye/tuş emülasyonu ·
özel kısayollar · TTS (edge, erkek ses) + wake word · sabah brifingi + akşam raporu ·
zamanlanmış görevler · otomatik hafıza · dosya bulucu · pano sihirbazı · pomodoro ·
streaming LLM yanıtı · istatistik sayfası · system tray · tek kopya kilidi · installer/exe ·
**öğrenme katmanı (geçmiş sohbet arşivi + alışkanlık + düzeltmeden öğrenme)** ·
**öneri motoru (alışkanlıktan zamanlanmış görev / kısayol)** ·
**👁️ OCR ekran okuma & tıklama (Windows.Media.Ocr)** ·
**📅 Takvim entegrasyonu (Yerel DB + Keysiz ICS aboneliği)**.

⚠️ **exe GÜNCEL DEĞİL** (28 Tem derlemesi): 30–31 Tem, 3 Ağu ve 4-5 Ağu işleri (uzaktan klavye,
Telegram hızlı butonlar, özel kısayollar, öğrenme katmanı, öneri motoru, OCR, Takvim)
yalnızca `python main.py` ile çalışan sürümde. Masaüstü/Başlangıç kısayolları eski
sürüme bakıyor — yeniden derleyip `C:\Users\memoc\UltronApp\ULTRON`'a taşımak gerekiyor.

### 📅 TAKVİM — `features/calendar_tools.py` (5 Ağu 2026)

Üç parçalı takvim altyapısı:
1. **Yerel Takvim:** `takvim_etkinlikleri` SQLite tablosu. İnternetsiz ekle/sil/sorgula.
2. **ICS Aboneliği:** Google Calendar / Outlook "gizli iCal adresi" üzerinden tek yönlü okuma (OAuth/API key gerektirmez). `tau_window.py` içinde 30 dakikada bir otomatik arka plan senkronizasyonu.
3. **ICS Dışa Aktarım:** Yerel etkinlikleri `.ics` dosyası yapıp dışa aktarabilme.
4. **Hatırlatma Köprüsü:** Etkinlik eklenince `hatirlatmalar` tablosuna N dakika öncesine kayıt yazılır — mevcut bildirim/Telegram/toast sistemi doğrudan kullanılır.

### 👁️ OCR EKRAN OKUMA & SEÇME — `features/screen_reader.py`, `screen_context.py`, `level3_ocr.py` (4 Ağu 2026)

Windows yerleşik OCR motoru (`Windows.Media.Ocr`) kullanılarak 0.2 saniyede model indirmesiz ve internetsiz ekran anlama:
- Ultron'un arkasındaki pencereyi yakalar.
- Kelime çöplüğü yerine uzamsal yakınlığa göre numaralı seçilebilir öğe listesi sunar ("ekranda ne var" → "3'ü aç").
- Gizlilik: Ekran içeriği **sadece yerel modellere** (Ollama/Kobold) iletilir, Gemini'ye gönderilmez.
- AIP Level 3 Vision: Düğme koordinatını tespit edip güvenli tıklama sağlar (çakışma/pencere kayması durumunda tıklamayı iptal eder).

### 🧠 ÖĞRENME KATMANI — `features/chat_learning.py` (3 Ağu 2026)

Ultron'un hafızası üç parçaydı ve üçü de kısaydı: `memory` (sadece açıkça öğretilenler),
`recent_context` (son 6 mesaj, pencere kapanınca uçar), `sohbet_gecmisi` (300+ kayıt ama
**hiçbir yerde okunmuyordu**). Artık ayrı bir arşiv (`%APPDATA%\ULTRON\ogrenme.db`) var:

| Sütun | Ne yapar | Nerede devrede |
|-------|----------|----------------|
| **Epizodik geri çağırma** | Mesaja en alakalı geçmiş konuşmaları FTS5 + BM25 ile bulur, prompt'a `[GEÇMİŞ KONUŞMA ARŞİVİ]` bloğu olarak koyar | `MemoryContextLayer` → yalnızca `GENERAL_CONVERSATION` / `WEB_SEARCH` (deterministik komut arşive sorgu atmaz) |
| **Örüntü çıkarımı** | Sık komutlar, saat alışkanlıkları, sık kişi/uygulama, sık konular — saf SQL toplaması, LLM yok | `profil_satirlari()` → prompt'taki `[ULTRON'UN GÖZLEMLERİ]`; `ogrenme_raporu()` → "ne öğrendin" |
| **Düzeltmeden öğrenme** | Anlaşılmayan cümlenin ardından kullanıcı aynı şeyi başka türlü söyleyip başardıysa, eski ifade o niyete bağlanır (2 gözlem şart) | `IntentAnalyzerLayer` → LLM niyet çözücüden ÖNCE |

Kayıt akışı: `engine.process()` her turu `kaydet()` ile yazar (ham cümle + niyet + başarı +
kanal + etiket); masaüstünde cevap streaming olduğu için `AssistantController.log()`
`cevabi_tamamla()` ile cevabı sonradan doldurur. Açılışta `gecmisi_iceri_al()` eski
`sohbet_gecmisi`ni **artımlı** olarak arşive alır (296/304 kayıt; kalanlar sır/kontrol filtresi).

Komutlar: `ne öğrendin` · `hakkımda ne biliyorsun` · `şunu unut: <ifade>` · `öğrendiklerini unut`.

### 💡 ÖNERİ MOTORU — `features/suggestions.py` (3 Ağu 2026, 2. tur)

Öğrenme katmanı alışkanlığı çıkarıyordu ama çıktısı RAPORDA kalıyordu; kullanıcının
onu kendi eliyle göreve çevirmesi gerekiyordu. Öğrenmenin işe dönüştüğü yer burası.

| Öneri tipi | Kaynak örüntü | Kabul edilince |
|-----------|---------------|----------------|
| **Zamanlama** | `oruntuler()['zaman']` — dilim payı ≥%50, **≥5 gözlem**, en yoğun SAAT | `scheduler.gorev_ekle` (her gün HH:00) |
| **Kısayol** | `oruntuler()['sik_komut']` — ≥5 tekrar, ≤60 karakter | `custom_shortcuts.ekle` |

Komutlar: `önerilerin` · `bekleyen öneri var mı` · `1. öneriyi uygula` · `1. öneriyi reddet`.
Öneriler `ne öğrendin` raporunun sonuna da eklenir (keşif tek komuta bağlı kalmasın).

**Güvenlik kapıları (hepsi tuzaklar tablosunda gerekçeli):** kendiliğinden uygulama YOK ·
belirsiz seçimde tahmin YOK · reddedilen bir daha sorulmaz · zaten kurulu olan
önerilmez · doğrulanamıyorsa (cursor yok) öneri üretilmez · beyaz liste
`chat_learning.OGRENILEBILIR_INTENTLER` ile ORTAK (mesaj gönderen niyet öneriye dönüşmez) ·
yanlızca tek komutla geri alınabilir eylemler.

Zamanlanabilir niyetler `ZAMANLANABILIR` sözlüğünde: brifing, akşam raporu, hava, döviz,
analiz raporu. **`PLAY_MUSIC` bilerek YOK** — kullanıcı uyanmadan müzik başlatmak
istenmeyen bir yan etkidir.

### 🔨 Eksik kalanlar / Raftakiler
1. exe'nin yeniden derlenmesi (yukarıdaki uyarı).
2. Öneri motoru sonraki adım: önerinin **proaktif** sunulması (şu an kullanıcı sormalı
   ya da raporu açmalı). Akşam raporuna tek satır iliştirmek doğal yer olur —
   ama dırdır sınırı (aynı öneri kaç günde bir) önce kararlaştırılmalı.

### ✔️ 28 Tem'de kapatılanlar & doğrulananlar
* **Dosya Gönderim Doğrulaması:** Kullanıcı canlıda test etti, WhatsApp/Telegram/Mail dosya gönderiminin sorunsuz çalıştığını onayladı.
* **Veri Yolu Birleştirmesi (`2e4369a`):** Tüm veriler `%APPDATA%\ULTRON` altında toplandı (`user_memory.py` ve `tau_backend.py` dahil). Exe ve Python ortamları tamamen senkronize.
* **Git Sync:** Tüm yerel commit'ler GitHub (`origin/main`) deposuna pushlandı. 345 testin tamamı yeşil.

---

## 📅 Oturum Günlüğü

| Tarih | Yapılan | Sonuç |
|-------|---------|-------|
| 5 Ağu (2) | **📦 GIT SYNC + README:** 4–5 Ağu'nun commit'siz duran tüm işi commit edildi (`cf31002`: takvim, planner revizyonu, pencere odaklama, OCR fiksleri, koyu başlık çubuğu — 26 dosya / +2579 satır) ve `origin/main`'e pushlandı. `README.md` v3.0 durumuna göre baştan yazıldı (`d01897d`): yetenek listesi, 14 katmanlı mimari, AIP fallback zinciri, config tablosu, test talimatı. **NOT: CLAUDE.md ↔ AGENTS.md ikizleri ayrıştı** — bu dosyadaki OCR/Takvim bölümleri ve 4 Ağu satırı CLAUDE.md'de yok; bir sonraki oturumda senkronlanmalı | ✅ Repo temiz, 631 test yeşil |
| 5 Ağu | **🧠 PLANNER MOTORU REVİZYONU, TAKVİM, ODAK & OCR FİKSİ:** `core/planner.py` — `cok_adimli_olabilir` kapısına eylemsel bağlaç (`aç ve`, `yaz ve`, `oku ve`), sıra kelimeleri ve numaralı liste regex'leri eklendi. `PLANNER_ISTEMI` prompt'una 2/3 adımlı few-shot JSON örnekleri entegre edildi. `plan_executor.py` adımlar arası dinamik bağlam aktarımı (`birikmis_veri` → `bulunan_dosya` ikamesi). `features/calendar_tools.py` ICS senkronu. **🖥️ Pencere Odaklama Motoru (`core/world_state.py`):** `acik_pencereleri_listele`, `pencereyi_one_getir`, `uygun_pencereyi_odakla`. **👁️ Vision OCR Fiksi:** `metni_bul` yönelme ekleri ('1'yi aç' → '1'e'/'1') ve rakamlı hedeflerde ilk adaya (`sira=0`) otomatik tıklama kuralı. `KOMUTLAR.md` güncellemesi | ✅ **631 test yeşil** (20 sn) |
| 4 Ağu | **👁️ OCR & ODAK FIX & DOĞAL DİL:** `features/screen_reader.py`, `screen_context.py`, `level3_ocr.py` (Windows.Media.Ocr ile model/internetsiz 0.2sn ekran okuma, "ekranda ne var" numaralı seçim listesi, yerel model gizlilik kuralı, AIP Level 3 Vision tıklama). Odak modu Web Overlay qwebchannel protocol fix + Chromium 83 CSS uyumu. Doğal dil niyet regex'leri & araç içi ayrıştırma düzeltmeleri (%75 → %100 niyet routing) | ✅ 455+ test yeşil + canlı doğrulandı |
| 3 Ağu (2) | **💡 ÖĞRENME KATMANI FAZ 2:** `features/suggestions.py` — örüntüden zamanlanmış görev / kısayol önerisi (sorar, kurmaz; reddedilen geri gelmez; numara gösterilen sıradan çözülür). Arşive **ruh hâli damgası** + rapora ruh hâli bölümü (prompt'a girmez). İstatistik sayfasına 3 öğrenme kartı. `chat_learning`'e `ornek`/`saat` alanları — rapor artık ASCII değil kullanıcının kendi cümlesini gösteriyor. Zırha JSON durum dosyaları eklendi. `tests/test_suggestions.py` (26 test) + 6 ruh hâli testi. **Kullanıcının canlı testinde iki hata çıktı ve düzeltildi:** (1) `[Telegram] ` kanal öneki `ornek` üzerinden öneriye sızıyordu → `kanalsiz()`; (2) aynı iş için iki kısayol öneriliyordu → niyet başına tek. İkisi de teste bağlandı | ✅ **455 test yeşil** + canlı: alışkanlık → öneri → kabul → görev kuruldu, kurulan tekrar sorulmadı, "film önerilerin var mı" komuta dönüşmedi |
| 3 Ağu | **🧠 ÖĞRENME KATMANI:** `features/chat_learning.py` — ayrı `ogrenme.db` (FTS5+BM25 geri çağırma, örüntü çıkarımı, düzeltmeden öğrenme, sır filtresi). Motor/niyet/prompt/UI entegrasyonu, `LEARNING_REPORT` niyeti + `ogrenme_raporu` aracı, `IntentAnalyzerLayer(hafif=)` ile geçmiş sınıflandırma, `tests/safety.py`'ye kalıcı veri koruması, `tests/test_chat_learning.py` (53 test) | ✅ **423 test yeşil** + canlı: 296 geçmiş konuşma arşive alındı (0.6 sn), geri çağırma 1-3 ms, qwen2.5:7b "kedinin adı Pamuk"/"Dark dizisini seviyorsunuz" diye HATIRLADI |
| 31 Tem (3) | **🔊 Akıllı Ses Kontrolü & Yazım/Kalıp İyileştirmesi:** `system_control.py` + `pipeline_layers.py`; `yao`→`yap`, `yüksel`→`yükselt`, `arttir`→`artır` yazım hataları ve `en yüksek`, `fulle`, `kökle`, `son ses` seviye ifadeleri eklendi (Codex oturumu) | ✅ 352 test yeşil + canlı doğrulandı |
| 31 Tem (2) | **⭐ Dinamik Özel Kısayol Yöneticisi:** `features/custom_shortcuts.py` (%APPDATA%\ULTRON\custom_shortcuts.json), `kısayol ekle/sil` komutları, dinamik Telegram menüsü (Codex oturumu) | ✅ 351 test yeşil |
| 31 Tem | **📱 Telegram Hızlı Erişim Butonları & Slash Komutlar:** `hizli_klavye` + `set_bot_commands`, `/ekran` `/enter` `/brifing` `/menu` … (Codex oturumu) | ✅ 348 test yeşil |
| 30 Tem | **⌨️ Uzaktan Klavye / Tuş Emülasyonu:** `level4_input.send_keyboard_input` (pywinauto + ctypes fallback), `klavye_tusu` aracı, `KEYBOARD_INPUT` niyeti ve güvenlik seviyesi (Codex oturumu) | ✅ 348 test yeşil |
| 28 Tem | Proje baştan sona analiz edildi · Tüm commit'ler GitHub'a pushlandı (`846a100`) · `user_memory.py` ve `tau_backend.py` veri yolları `%APPDATA%\ULTRON` olarak güncellendi (`2e4369a`) · `AGENTS.md` güncellendi | ✅ 345 test yeşil, repo temiz ve güncel |
|-------|---------|-------|
| 22 Tem | Backend/thread/onay fixleri, UWP açma, tray, saat parser'ı, AIP kuruldu, WhatsApp gönderimi, sohbet kalıcılığı, brifing, e-posta, istatistikler, Telegram köprüsü, TTS+wake word, halüsinasyon frenleri, STT insanileştirme, internet/hava/döviz düzeltmeleri | ✅ Canlı doğrulandı |
| 23 Tem | Otonom üçlü (zamanlanmış görevler + otomatik hafıza + dosya bulucu), tek kopya kilidi, mikrofon fallback, streaming, pano, pomodoro, tema cilası, **installer (371MB exe)**, Telegram süper paketi (ekran görüntüsü/sesli mesaj/dosya), KOMUTLAR.md | ✅ Commit `ef7cd79`'a kadar |
| 24–25 Tem | `llm_gateway` (LLM UI'dan söküldü — Telegram/görevler artık LLM cevabı alıyor), `llm_intent` (LLM niyet sınıflandırıcı), `memory_rag` (alakaya göre hafıza), `confirmed_executor` (onaylı WA/mail gönderilmiyordu — fix), `quick_tools` (hesap/saat/sayaç/not), `mood.py` yeniden yazıldı, engine'e canlı config, chat_view (girdi geçmişi, kod bloğu, hızlı öneriler, medya butonları) | ⚠️ **Commit edilmedi** |
| 27 Tem | CLAUDE.md yazıldı · 24–25 Tem'in işi commit edildi (`43e0103`) · KOMUTLAR.md'ye 5 yeni bölüm · **`tests/safety.py` güvenlik zırhı** — testler artık Chrome kapatmıyor/ses değiştirmiyor, zırhı kilitleyen 3 test eklendi | ✅ 52 test yeşil (2.9 sn) |
| 27 Tem (13) | **🔍 Faz 8 — REFLECTION:** `core/reflection.py`. İki deterministik kontrol: (1) kanıt — ekran görüntüsü diskte mi, kayıt DB'de mi; (2) **halüsinasyon freni** — hiçbir araç çalışmamışken LLM "açtım/gönderdim" diyorsa uyarı eklenir. `CLAUDE.md`'de yasak vardı ama doğrulayan yoktu. `tests/test_reflection.py` (21 test) | ✅ **345 test yeşil** |
| 27 Tem (12) | **🌍 Faz 6 — WORLD STATE:** `core/world_state.py`. Çalışan uygulama tespiti (temkinli eşleşme, 3 sn önbellek), pil, internet. "Spotify aç" → "zaten açıktı, öne getiriyorum". `tests/test_world_state.py` (23 test) | ✅ **324 test yeşil** + canlı: WhatsApp açık tespit edildi, internet kontrolü düzeltildi |
| 27 Tem (11) | **🧠 Faz 3 — TAKMA ADLAR:** `core/aliases.py`. "patronum Ahmet Kaya demek" → `kisi_coz`/`email_coz` rehberde bulamazsa takma ada sorar. Bulanık eşleşme YOK, sohbetten çıkarım YOK, rehber önce gelir, kimlik onay kartında görünür. `tests/test_aliases.py` (25 test) | ✅ **301 test yeşil** + canlı: açık öğretim kaydedildi, sohbet cümlesi kaydedilmedi, `patron` bulanık çözülmedi |
| 27 Tem (10) | **🔒 Gizli dosya filtresi kilitlendi:** `tests/test_gizli_dosyalar.py` (21 test). İki savunma hattı (indeksleme + gönderim), yanlış pozitif kontrolü, liste zayıflatma koruması. Öğrenilen: `.env` iki bağımsız mekanizmayla korunuyormuş | ✅ 276 test yeşil |
| 27 Tem (9) | **📄 Sayfalama + daraltma:** `sonuc_sayisi()`, `ara(offset=)`, sayfa başına 10, "devamını göster" komutu, sayfalar arası doğru seçim (offset düşülür). Kullanıcı geri bildirimi: "daha fazla dosya bulduysa diğerlerine bakmak isterdim". `tests/test_sayfalama.py` (19 test) | ✅ **246 test yeşil** + canlı: "rapor dosyalarını bul" → 26 dosya, 1-10 arası, "devamını göster" → 11-20 |
| 27 Tem (8) | **🛟 Faz 4 — RECOVERY ENGINE:** `core/recovery.py`. Başarısızlıkta deterministik alternatif zinciri (LLM yok, ~ms). Dosya bulunamadı → adı gevşetip tekrar ara → indeks bayatsa yenile → kullanıcıya sor. Ağ hatasında tek tekrar. `AracSonuc.hata_tipi` eklendi ("başarılı ama hedefe ulaşmadı"). Salt-okunur `indeks_ara` aracı. `tests/test_recovery.py` (31 test) | ✅ **214 test yeşil** + canlı: "ULTRON yedek spec bul" → bulunamadı → `ultron` diye gevşetip 10 dosya listeledi |
| 27 Tem (7) | **📂 Dosya açma:** `file_send`'e `ac` işlemi + `dosya_ac` aracı + `calistirilabilir_mi`. Belge sorusuz açılır, program onay kartından geçer (skor 80). "onu aç" artık çalışıyor. `tests/test_dosya_ac.py` (18 test) | ✅ **183 test yeşil** + canlı: "onu ac" doğru dosyayı açtı, "chrome ac" etkilenmedi |
| 27 Tem (6) | **🧭 Faz 2 — CONTEXT MANAGER:** `core/context_manager.py`. Kanal başına son dosya/kişi/uygulama/konu takibi (15 dk TTL), deiktik referans çözümü ("onu", "ona", çıplak "dosyayı"). Niyet analizinden ÖNCE çalışır. Sadece BAŞARILI komutlar bağlamı günceller. `tests/test_context_manager.py` (27 test, çoğu "çözMEMEsi gereken" durumlar) | ✅ **165 test yeşil** + canlı test: "ULTRON.spec bul" → "onu bana gönder" doğru dosyaya bağlandı |
| 27 Tem (5) | **🧠 Faz 1 — PLANNER:** `core/planner.py` (şemaya zorlanmış plan üretimi, doğrulama, kapı) + `core/plan_executor.py` (görev kuyruğu, koşullar, onay bekletme) + `ollama_json` (grammar-constrained JSON). Motor entegrasyonu: planner yürütmeden ÖNCE, sadece çok adımlı cümlede. Kanal başına onay akışı (evet/iptal/konu değişince düş). `tests/test_planner.py` (38 test) | ✅ **138 test yeşil** + canlı 7b testi: "önce hava, sonra döviz" → 2 adımlı plan, ikisi de yürüdü (24.5 sn); "chrome aç" planner'ı görmedi (2.5 sn) |
| 27 Tem (4) | **🧰 Faz 0 — ARAÇ DEFTERİ:** `core/tools.py` + `core/builtin_tools.py`. `ExecutionEngineLayer`'ın ~260 satırlık if/elif zinciri 24 isimli araca bölündü; katman artık sadece intent→araç dağıtımı yapıyor. Üç durumlu `AracSonuc` (islenmedi / hata / ok) eski zincirin iki ayrı başarısızlık anlamını koruyor. `tests/test_tools.py` (37 test) | ✅ **98 test yeşil** + uçtan uca duman testi (saat, hesap, not, odak, chrome aç, ses kıs) |
| 27 Tem (3) | **🖥️ Gerçek uygulama haline getirildi:** exe yeniden derlendi (dosya gönderimi dahil), `main.py`'ye `--tray` bayrağı (açılışta pencere değil tepsi), uygulama OneDrive dışına `C:\Users\memoc\UltronApp\ULTRON`'a taşındı, **3 kısayol** kuruldu (Masaüstü / Başlat menüsü / Başlangıç klasörü), veri dosyaları exe tarafına kopyalandı | ✅ Tepsi modunda çalıştığı doğrulandı (PID canlı, pencere açılmadı) |
| 27 Tem (2) | **📎 Telefondan dosya bul & gönder:** `file_index.py` (134k dosya, 12 sn, alt klasörler dahil, sır filtresi), `file_send.py` (ayrıştırma + Telegram/mail/WhatsApp), `sendDocument`, mail eki (MIMEMultipart), WhatsApp'a pano CF_HDROP + odak korumalı Ctrl+V, `FILE_TRANSFER`/`FILE_INDEX` intent'leri, başkasına gönderimde onay kartı, kanal ayrımı (`ctx.kanal`), 6 saatlik otomatik indeks tazeleme | ✅ **Kullanıcı canlıda doğruladı — "hepsi mis gibi çalışıyor"** (WhatsApp pano yolu dahil). Testler sonraya. |

---

*Bu dosyayı her gün sonunda güncelle — yarın buradan devam edeceğiz.*
