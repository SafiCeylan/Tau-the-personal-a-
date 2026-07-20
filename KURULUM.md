# TAU Kurulum Talimatları

TAU tamamen native bir PyQt5 masaüstü uygulamasıdır — tarayıcı veya web view bileşeni **kullanmaz**.

## Gerekli Paketler

```bash
pip install -r requirements.txt
```

Bu, çekirdek bağımlılıkları (PyQt5, rapidfuzz, requests) ve isteğe bağlı sesli
komut paketlerini (gTTS, pygame, SpeechRecognition) kurar. Sesli komut
paketleri kurulu olmasa da uygulama sorunsuz çalışır; sadece mikrofon
butonu "kurulu değil" mesajı gösterir.

## Çalıştırma

```bash
python main.py
```

Windows'ta kolay başlatma için `start_tau.bat` dosyasına da çift tıklayabilirsiniz
(paketleri otomatik kurup uygulamayı başlatır).

## AI Sağlayıcısı Seçimi

`config.json` içindeki `ai_provider` alanı hangi AI motorunun kullanılacağını belirler:

- `"kobold"` — Yerel KoboldCPP (varsayılan adres: `http://localhost:5001`, `kobold_url` ile değiştirilebilir)
- `"ollama"` — Yerel Ollama (varsayılan adres: `http://127.0.0.1:11434`, `ollama_url`/`ollama_model` ile değiştirilebilir)
- `"tau_backend"` — Kendi barındırdığınız TAU Backend API'si (`tau_backend_url`, `tau_api_key`)

Seçilen sağlayıcı çalışmıyorsa (bağlantı hatası vb.) TAU otomatik olarak
veritabanındaki en yakın eşleşen cevaba döner.

## Sorun Giderme

- **PyQt5 kurulum sorunu (Windows):** `pip install PyQt5`
- **Sesli komut çalışmıyor:** `pip install SpeechRecognition pygame` ve mikrofon izinlerini kontrol edin.
- **AI cevap vermiyor:** `config.json`'daki `ai_provider` alanının çalışan bir sunucuyu (Kobold/Ollama) işaret ettiğinden emin olun.
