# 🔴 ULTRON — Komut Rehberi (Kopya Kağıdı)

> Tüm komutlar hem masaüstünden hem Telegram'dan çalışır.
> Riskli olanlar (mesaj gönderme, uygulama kapatma) onay kartı ister.

---

## 📱 WHATSAPP

### Kişi ekleme / yönetme
```
whatsapp kişi ekle: annem = 0555 111 22 33
whatsapp kişi ekle: patron = +905551112233
whatsapp kişileri listele
whatsapp kişi sil: annem
```
> Numara biçimleri hepsi kabul: `0555 111 22 33` · `05551112233` · `+905551112233`

### Mesaj gönderme (nasıl yazarsan yaz anlar)
```
anneme whatsapp at yarın gelemeyeceğim        ← fiil ortada, iki nokta yok
anneme whatsapp'tan yaz akşam geliyorum
whatsapp ile anneme geç kalacağım de
whatsapp'tan anneme naber kanka gönder
anneme whatsapptan geliyorum yaz
annem'e whatsapp'tan mesaj gönder: iyi akşamlar
anneme iyi akşamlar yazılı mesaj gönder whatsapp üzerinden
anneme mesaj at: yoldayım                     ← "whatsapp" demeden de olur
```
> **Kesme işareti gerekmez:** "anneme" de "annem'e" kadar geçerli.
> **"whatsapp" demeden** yazarsan kanalı REHBERDEN bulur: alıcı WhatsApp
> rehberindeyse WhatsApp'tan, e-posta rehberindeyse mailden gider.
> İkisinde de yoksa **tahmin yürütmez** — önce `whatsapp kişi ekle:` ile ekle.
> "anneme" yazsan da rehberdeki "annem"i bulur (ek toleransı).
> Rehberde olmayan kişiye ham numarayla da gönderebilirsin:
> `05321234567'ye whatsapp'tan mesaj gönder: selam`

---

## 📱 TELEGRAM HIZLI ERIŞIM BUTONLARI VE SLASH KOMUTLAR

Telegram sohbetinizin altında açılan **Hızlı Buton Takımı** veya Telegram klavyesindeki `/` işaretine basarak kullanabileceğiniz hazır komutlar:

### Hızlı Butonlar & Slash Komutlar
```text
📸 Ekran Görüntüsü    /ekran        ← PC ekranının anlık görüntüsünü fotoğraf olarak atar
↵ Enter               /enter        ← PC'de Enter tuşuna basar
⌨️ Alt+Enter          /alt_enter    ← PC'de Alt+Enter kombinasyonu basar
📋 Ctrl+C             /ctrl_c       ← Kopyalama (Ctrl+C) tuşuna basar
📋 Ctrl+V             /ctrl_v       ← Yapıştırma (Ctrl+V) tuşuna basar
❌ Alt+F4             /alt_f4       ← Aktif pencereyi kapatır (Alt+F4)
☀️ Sabah Brifingi     /brifing      ← Günlük hava, döviz ve hatırlatma brifingi verir
📊 Sistem Durumu                     ← CPU, RAM, Disk kullanımını raporlar
⭐ Özel Kısayollarım  /ozel         ← Kendi eklediğin dinamik kısayol butonları menüsü
🎛️ Menüyü Kapat                      ← Hızlı buton takımını gizler (tekrar açmak için /menu)
```

### ⭐ Canlı Özel Kısayol Ekleme & Silme
```text
kısayol ekle: Photoshop = ctrl+alt+shift+p    ← Menüye yeni özel buton ve tuş ekler
kısayol ekle: VS Code = code                  ← Uygulama çalıştırma kısayolu ekler
kısayol ekle: Terminal = ctrl+alt+t           ← Özel tuş kombinasyonu ekler
kısayol sil: Photoshop                        ← Eklenen özel kısayolu siler
```

---

## 📧 E-POSTA (Gmail)

### Kişi ekleme / yönetme
```
mail kişi ekle: annem = ornek@gmail.com
mail kişileri listele
mail kişi sil: annem
```

### Mail gönderme
```
anneme mail at yarın gelemeyeceğim                   ← iki nokta gerekmez
patronuma mail gönder toplantı ertelendi
hocama mail at konu: staj raporu                     ← "konu:" başlık olur
kendime mail gönder: Toplantı | yarın 14:00'te       ← "|" öncesi KONU, sonrası İÇERİK
annem'e mail gönder: naber nasılsın                  ← konu otomatik olur
x@y.com'a eposta yolla merhaba                       ← rehbersiz, doğrudan adrese
```
> Kesme işareti gerekmez ("anneme" = "annem'e"). `konu:` yazdığın yer başlık
> olur, alıcı sanılmaz.

---

## ⏰ HATIRLATMA
```
yarın 14:00 toplantıyı hatırlat
cuma akşam 8'de maç var hatırlat          ← akşam 8 = 20:00 anlar
pazartesi 10:00 rapor için alarm kur      ← hafta günleri çalışır
saat 23 de ilaç içmeyi hatırlat
10 dakika sonra çay demle hatırlat
yarın sabah ilaç içmeyi hatırlat          ← sabah=08:00 öğlen=12:00 akşam=19:00 gece=22:00
öbür gün doktora gitmeyi hatırlat         ← 2 gün sonrası
hatırlatmalarımı göster
```
> Saat söylemezsen günün bölümünden varsayılan saat kurulur. Açık saat
> verirsen o kazanır: "akşam 8'de" → 20:00.

## 🤖 ZAMANLANMIŞ GÖREVLER (her gün otomatik)
```
zamanla: 08:30 sabah brifingi
her gün 21:00 dolar kaç
zamanlanmış görevler                      ← listele
zamanlama sil: 3
```
> Varsayılanlar: 08:00 sabah brifingi · 22:00 akşam raporu (Telegram'a da gider)

## 🧠 HAFIZA
```
hatırla: araba plakam = 34 ABC 123        ← açık kayıt
en sevdiğim dizi Dark                     ← otomatik öğrenir
benim adım Mehmet / 25 yaşındayım / mesleğim yazılımcı
ankara'da yaşıyorum                       ← hava durumu şehrini de günceller!
```

## 🧠 ÖĞRENME (geçmiş sohbetlerden)
```
ne öğrendin                               ← alışkanlıkların ve öğrenilmiş kalıpların raporu
neler öğrendin
hakkımda ne biliyorsun
şunu unut: biraz kısar mısın              ← yanlış öğrenilmiş bir ifadeyi siler
öğrendiklerini unut                       ← tüm öğrenilmiş kalıpları siler (arşiv kalır)
```
> **Nasıl öğreniyor?**
> • **Hatırlama:** Eski konuşmalar arşivleniyor; bir şey sorduğunda o konuyla ilgili
>   geçmiş konuşmaların cevabıma dahil oluyor. ("kedimin adı neydi" → hatırlar)
> • **Alışkanlık:** Hangi komutu ne sıklıkla, hangi saatte kullandığın sayılıyor.
> • **Düzeltme:** Bir cümlemi anlamazsam ve sen aynı şeyi başka türlü söyleyip
>   başarırsan, o ifadeyi öğrenirim. İkinci kez olunca kalıcı olur ve kullandığımda
>   sana `_(🧠 öğrenilmiş kalıp: …)_` diye bildiririm — yanlışsa `şunu unut:` de.
> • **Ruh hâli:** Sohbet mesajlarının tonu turun yanına yazılıyor; raporda
>   "keyifsiz mesajların çoğu gece saatlerinde" gibi bir satır çıkabiliyor.
> ⚠️ Şifre/PIN/token geçen mesajlar arşive **hiç girmez**.

### 💡 Öneriler (alışkanlıktan otomasyon)
```
önerilerin neler                          ← gözlediğim alışkanlıklardan öneri listesi
bekleyen öneri var mı
1. öneriyi uygula                         ← öneriyi kurar (görev / kısayol)
öneriyi kabul et                          ← tek öneri varsa numara gerekmez
1. öneriyi reddet                         ← bir daha sormam
öneriyi boşver
```
> Aynı şeyi 5+ kez yaptığında sana **sorarım**: "her gün 08:00'de hava durumu
> çalıştırayım mı?" veya "bu komut için kısayol oluşturayım mı?".
> • **Hiçbir şey kendiliğinden kurulmaz** — sen "uygula" demeden olmaz.
> • **Reddettiğin bir daha sorulmaz.**
> • Zaten kurulu bir görev/kısayol için öneri gelmez.
> • Kurduğun şey geri alınabilir: `zamanlanmış görevler` → `zamanlama sil: 3`,
>   kısayol için `kısayol sil: <ad>`.
> • Mesaj gönderen komutlar (WhatsApp/mail/dosya gönderme) **asla** öneriye dönüşmez.
> Öneriler `ne öğrendin` raporunun sonunda da görünür.

## 📂 DOSYA
```
indirilenler'deki son pdf'i aç
masaüstündeki safi_cv pdf'i aç            ← isimle arama
masaüstündeki resimleri listele
belgelerdeki son word dosyasını bul
oku: C:\yol\dosya.pdf                     ← içeriğini okur/özetler
```
> Klasörler: indirilenler, masaüstü, belgeler, resimler, videolar, müzikler
> Türler: pdf, resim, video, müzik, excel, word, sunum, zip, metin, kurulum

## 📝 NOTLAR
```
not al: yarın market listesi lazım
not: kablo almayı unutma
şunu not et bugün hava çok güzeldi
aklımda kalsın: kapıcıya para verilecek
notlarımı göster                          ← son 15 not
notlarımı sil                             ← hepsini temizler
```

## 🧮 HESAP MAKİNESİ
```
125 * 48 kaç eder
17 + 33
yüz yirmi beş çarpı kırk sekiz            ← sözel sayılar da çalışır
340 bölü 4
```
> LLM'e sorulmaz — güvenli matematik motoru hesaplar (yanlış cevap ihtimali yok).

## 🕐 SAAT / TARİH
```
saat kaç
bugün ayın kaçı
bugün günlerden ne
bugünün tarihi ne
```
> Gerçek sistem saatinden okunur, modele sorulmaz.

## ⏱️ SAYAÇ
```
10 dakika sayaç kur
25 dakikaya kur
yarım saat sonra uyar
zamanlayıcı 5 dakika
```
> Sayaç hatırlatma olarak kaydedilir — süre dolunca bildirim + Telegram.

## ⏯️ ÇALAN MÜZİĞİ KONTROL
```
şarkıyı geç / sonraki şarkı
önceki şarkı / başa sar
müziği duraklat / devam ettir
müziği durdur
```
> Sohbet penceresinin altındaki ⏮ ⏯ ⏭ butonları da aynı işi yapar (mesaj yazmadan).

## 🔎 DOSYA BUL & GÖNDER (telefondan da çalışır)
```
staj raporunu bul                         ← alt klasörler dahil TÜM PC'de arar
bilgisayarımda cv ara
son pdf dosyalarını listele
sunum dosyası nerede
```
> Sonuçlar numaralı gelir. Sonra:
```
1'i bana gönder                           ← dosya Telegram'a düşer 📤
2'yi anneme mail at                       ← e-posta EKİ olarak gider (onay ister)
3'ü patrona whatsapp'tan gönder           ← WhatsApp'a ekler (onay ister)
```
> **Çok sonuç varsa:** kaç dosya bulunduğunu söyler, ilk 10'unu gösterir.
```
devamını göster                           ← sonraki 10 (numaralar 11'den devam eder)
diğerlerini göster · gerisini göster · daha fazla
```
> Numaralar genel sıradır: 2. sayfada `12'yi bana gönder` diyebilirsin.
> **Ya da daralt:** "hangisi?" diye sorduğunda adından bir parça yaz —
```
rapor dosyalarını bul        → 26 dosya bulundu, hangisi?
haftalık                     → aramayı daralttım: rapor + haftalık (18 dosya)
staj                         → rapor + haftalık + staj (3 dosya)
```
> Alakasız bir şey yazarsan (`teşekkürler`) arama sanmaz, normal sohbete döner.
> Tek adımda da olur: `staj raporunu anneme mail at`
> — tek eşleşme varsa direkt gönderir, birden fazlaysa "hangisi?" diye sorar.

### Dosyayı açma
```
staj raporu dosyasını aç                  ← varsayılan uygulamayla açar
son pdf'i aç
1'i aç                                    ← listeden seçerek
```
> ⚠️ `.exe` `.bat` `.ps1` `.msi` gibi dosyaları "açmak" onları **çalıştırmaktır** —
> bunlarda onay kartı çıkar. Belge/resim/PDF sorusuz açılır.
> Not: `chrome aç` hâlâ uygulama başlatır, dosya aramaz.

### Takma adlar (kim kimdir)
```
patronum Ahmet Kaya demek                 ← öğretir
annem Ayşe Ceylan'dır
hocam aslında Mehmet Yılmaz
patronum = Ahmet Kaya
```
> Sonra `patronuma whatsapp'tan yaz: selam` diyebilirsin.
> **Onay kartında kimin kastedildiği yazar:** `patronuma → Ahmet Kaya`
> Ultron sohbetten takma ad ÖĞRENMEZ, sadece yukarıdaki gibi açıkça söylersen.
> Benzer isimler (`patron`, `patronlar`) çözülmez — yanlış kişiye gitmesin diye.

### Bağlamdan devam etme
```
staj raporunu bul
onu aç                                    ← "onu" = az önce bulunan dosya
onu anneme gönder
```
> Neyi kastettiğini varsaydığını yazar: _(bağlamdan: 'onu' → staj raporu.pdf)_
> 15 dakika sonra bağlam düşer, tekrar sorar. Telefondaki konuşma masaüstüne karışmaz.

### İndeks yönetimi
```
dosya indeksi durumu                      ← kaç dosya, son tarama ne zaman
dosya indeksini güncelle                  ← yeniden tarar (~15 sn)
```
> İndeks açılışta kurulur, sonra 6 saatte bir kendini yeniler.
> **Güvenlik:** `.env`, `*.pem`, `*.kdbx`, `id_rsa`, `config.json` gibi sır taşıyan
> dosyalar indekse HİÇ girmez — telefondan bulunamaz, gönderilemez.
> Başkasına gönderim her zaman onay kartı ister; "bana gönder" istemez.

## 📋 PANO
```
panoyu oku
panoyu özetle
panoyu çevir                              ← varsayılan İngilizce
panoyu almancaya çevir                    ← 8 dil destekli
panoyu açıkla
panoya yaz: merhaba dünya
```

## 👁️ EKRAN OKUMA VE SEÇME (OCR)

**Ana akış — ekranı anla, numarayla seç:**
```
ekranda ne var                            ← numaralı öğe listesi verir
  →  1. Tarkan - Kuzu Kuzu (Official Video)
     2. Sezen Aksu - Şarkı Söylemek Lazım
     3. Barış Manço - Gülpembe
     Hangisini açayım?
3'ü aç · 2'yi aç · ikinciyi aç · sonuncuyu aç · kuzu kuzu olanı aç
```
> Kelime çöplüğü değil **seçilebilir öğe listesi** döner. Liste 5 dakika
> hatırlanır; ekran değişirse bayatlar ve yeniden okuman istenir.
> Masaüstünden okuyup **Telegram'dan seçebilirsin** — ekran tektir.

**Diğer:**
```
ekranda ne yazıyor · ekranı oku           ← aynı akış
ekrandaki hatayı açıkla                   ← hatayı okur + çözüm önerir
ekranı özetle · ekrandaki metni çevir
ekranda kaydet var mı                     ← bulursa tıklama koordinatını verir
tüm ekranı oku                            ← tek pencere değil, her şey
```
> Telegram'da `/ekran` menüsünden butonlarla da yapabilirsin.
> **Hangi pencere okunur?** Ultron'un kendi penceresi değil — **arkasındaki**
> ilk gerçek pencere. "Ekranda ne yazıyor" derken sohbet kutunu kastetmiyorsun.
>
> **Gizlilik:** Okunan metin **sadece yerel modele** (Ollama/Kobold) gider.
> Sağlayıcı Gemini ise ekran içeriği **gönderilmez**, Ultron bunu söyler.
>
> Windows'un yerleşik OCR'ı kullanılır: model indirmesi yok, internet yok,
> ~0.2 saniye. Kurulu tek dil Türkçe — İngilizce arayüzlerde hata payı artar.

## 🖱️ EKRANDAKİ DÜĞMEYE TIKLAMA
```
ekranda Kaydet'e tıkla
ekranda Tamam butonuna bas
ekranda "İzin Ver"e tıkla                 ← boşluklu adlar için tırnak
Gönder butonuna tıkla
```
> **Önce fareSİZ dener.** Düğmeyi erişilebilirlik ağacında bulursa (Level 2)
> fare hiç oynamaz. Bulamazsa (Electron, oyun, uzak masaüstü) ekranda OCR ile
> görüp koordinatına tıklar (Level 3). Göremezse **hiçbir şey yapmaz** —
> "bir yere kör tıklama" diye bir seçenek yok.
>
> **Tıklamayı iptal eden dört durum:** ① yazı ekranda birden çok yerde geçiyor
> (hangisi olduğu belirsiz) ② hedef pencere ön planda değil ③ pencere okuma ile
> tıklama arasında taşındı ④ o noktanın sahibi başka bir pencere (araya bildirim
> girmiş). Dördünde de sana tıklamadığını söyler.
>
> `enter bas`, `ctrl+s bas` bu komut DEĞİLDİR — onlar ⌨️ tuş komutlarıdır.

## 🎯 ODAK MODU (Pomodoro)
```
25 dakika odaklan                         ← ses %20'ye iner
45 dk pomodoro başlat
odak durumu                               ← kaç dakika kaldı
odaklanmayı iptal et
```

## 🖥️ SİSTEM
```
whatsapp aç / spotify aç / vs code aç     ← Store uygulamaları dahil hepsi
chrome kapat                              ← onay ister
sesi %40 yap / sesi kıs / sessize al
tuğkan dan geber şarkısını çal            ← YouTube Music'te başlatır
ekran görüntüsü al                        ← Masaüstüne PNG
ekran görüntüsü al ve telegrama gönder    ← cebine fotoğraf
bilgisayarı kilitle
sistem durumu nedir                       ← CPU/RAM/disk/pil raporu
```

## 🌍 CANLI BİLGİ
```
hava durumu nasıl                         ← bugün + yarın + ertesi gün
dolar kaç / euro kaç
atatürk kimdir                            ← Wikipedia
teknoloji haberleri                       ← Google News
sabah brifingi                            ← hava + döviz + hatırlatmalar
akşam raporu                              ← gün özeti + yarının işleri
haftalık analiz raporu
```

## 🎙️ SES
```
(mikrofon butonu veya) Hey Ultron...      ← sesli uyanma
sus                                       ← konuşmayı anında keser
```

## 🎛️ MODLAR
```
çalışma modu / oyun modu / dinlenme modu
```
> Kendi modunu Mod & Rutin Yöneticisi'nden kurabilirsin (çok adımlı).

## 📱 TELEGRAM ÖZEL
- 🎙️ **Sesli mesaj** at → yazıya çevirip komut olarak işler
- 📎 **Dosya/fotoğraf** gönder → PC'nin İndirilenler'ine kaydeder
- `/start` → yardım menüsü

## ⌨️ UZAKTAN KLAVYE / TUŞ KOMBİNASYONU (Telegram & Masaüstü)
```
tuş: ctrl+enter               ← Ekrana Ctrl+Enter tuş kombinasyonu basar
tuş: enter                    ← Klavyeden Enter basar
tuş: alt+f4                   ← Aktif pencereyi kapatır (Alt+F4)
1 2 3 4 enter                 ← Ekrana 1 2 3 4 yazıp Enter'a basar
1234 enter'a bas              ← Ekrana 1234 yazıp Enter'a basar
yaz: merhaba dunya enter      ← Metni yazıp Enter basar
enter bas · f5 e bas · escape'e bas · yukarı ok bas
ctrl c yap · alt tab          ← artı işareti yazmak zorunda değilsin
```

### Günlük dille kısayollar (`ctrl+` yazmadan)
```
kopyala           → Ctrl+C          yapıştır          → Ctrl+V
kes               → Ctrl+X          geri al           → Ctrl+Z
ileri al          → Ctrl+Y          hepsini seç       → Ctrl+A
kaydet            → Ctrl+S          yazdır            → Ctrl+P
yenile            → F5              tam ekran         → F11
yeni sekme        → Ctrl+T          sekmeyi kapat     → Ctrl+W
kapanan sekmeyi aç→ Ctrl+Shift+T    görev yöneticisi  → Ctrl+Shift+Esc
alt tab           → Alt+Tab         masaüstüne dön    → Win+D
sayfa başına git  → Ctrl+Home       sayfa sonuna git  → Ctrl+End
sayfa aşağı/yukarı→ PgDn / PgUp     yakınlaştır       → Ctrl++
```
> `sesi kes` bir ses komutudur (Ctrl+X değil), `masaüstünü göster` dosya
> listeleme komutudur — ikisi de bilerek bu tablonun dışında.
> Telegram'dan ekran görüntüsü alıp ekrandaki onay penceresini gördüğünde bu komutlarla uzaktan doğrudan yanıt verebilirsin.

---
*Bu dosya: `KOMUTLAR.md` — proje kökünde durur, yeni özellik eklendikçe güncellenir.*
