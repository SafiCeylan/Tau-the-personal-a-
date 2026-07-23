"""
Dosya Bulucu — "indirilenler'deki son pdf'i bul/aç" gibi komutlar.

Klasörler: indirilenler, masaüstü, belgeler, resimler, müzikler, videolar
Türler: pdf, resim, video, müzik, excel, word, zip... veya doğrudan uzantı
"son ..." → değişiklik tarihine göre en yenisi; "aç" geçiyorsa ilk sonuç açılır.
"""

import os
import re
import sys
from datetime import datetime

KLASORLER = {
    'indirilenler': 'Downloads', 'i̇ndirilenler': 'Downloads', 'downloads': 'Downloads',
    'masaüstü': 'Desktop', 'masaustu': 'Desktop', 'desktop': 'Desktop',
    'belgeler': 'Documents', 'dokümanlar': 'Documents', 'documents': 'Documents',
    'resimler': 'Pictures', 'fotoğraflar': 'Pictures', 'pictures': 'Pictures',
    'müzikler': 'Music', 'müzik klasörü': 'Music',
    'videolar': 'Videos', 'videolarım': 'Videos',
}

TUR_UZANTILARI = {
    'pdf': ['.pdf'],
    'resim': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
    'fotoğraf': ['.jpg', '.jpeg', '.png', '.heic'],
    'video': ['.mp4', '.mkv', '.avi', '.mov', '.webm'],
    'müzik': ['.mp3', '.wav', '.flac', '.m4a'],
    'ses': ['.mp3', '.wav', '.m4a'],
    'excel': ['.xlsx', '.xls', '.csv'],
    'word': ['.docx', '.doc'],
    'sunum': ['.pptx', '.ppt'],
    'zip': ['.zip', '.rar', '.7z'],
    'arşiv': ['.zip', '.rar', '.7z'],
    'metin': ['.txt', '.md'],
    'kurulum': ['.exe', '.msi'],
}


def dosya_arama_niyeti(mesaj: str) -> bool:
    """Bu mesaj bir dosya arama komutu mu?"""
    ml = mesaj.lower()
    klasor_var = any(k in ml for k in KLASORLER)
    if not klasor_var:
        return False
    return any(k in ml for k in ['bul', 'dosya', ' aç', 'son ', 'listele', 'göster', 'var mı'])


# Windows kayıt defterindeki gerçek klasör konumları (OneDrive yönlendirmesini de çözer:
# ör. Masaüstü çoğu sistemde C:\Users\X\Desktop DEĞİL, C:\Users\X\OneDrive\Desktop'tadır)
_REG_ADLARI = {
    'Desktop': 'Desktop',
    'Documents': 'Personal',
    'Pictures': 'My Pictures',
    'Music': 'My Music',
    'Videos': 'My Video',
    'Downloads': '{374DE290-123F-4565-9164-39C4925E467B}',
}


def _gercek_yol(klasor_std: str):
    """Klasörün GERÇEK yolunu döner (registry → OneDrive → klasik ev dizini)."""
    if sys.platform == 'win32':
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            ) as k:
                val, _ = winreg.QueryValueEx(k, _REG_ADLARI.get(klasor_std, klasor_std))
                yol = os.path.expandvars(val)
                if os.path.isdir(yol):
                    return yol
        except Exception:
            pass
    home = os.path.expanduser('~')
    for aday in (os.path.join(home, 'OneDrive', klasor_std),
                 os.path.join(home, klasor_std)):
        if os.path.isdir(aday):
            return aday
    return None


def _klasor_bul(ml: str):
    for anahtar, klasor in KLASORLER.items():
        if anahtar in ml:
            yol = _gercek_yol(klasor)
            if yol:
                return yol, anahtar
    return None, None


def _uzantilar_bul(ml: str):
    for tur, uzantilar in TUR_UZANTILARI.items():
        if tur in ml:
            return uzantilar, tur
    m = re.search(r'\.(\w{2,5})\b', ml)   # ".pdf" gibi doğrudan uzantı
    if m:
        return ['.' + m.group(1)], m.group(1)
    return None, None


def dosya_bul_ve_islet(mesaj: str):
    """Dosya arar; 'aç' istenmişse en uygununu açar, değilse listeler.
    Dönen değer: (başarılı_mı, yanıt)"""
    ml = mesaj.lower()

    klasor, klasor_adi = _klasor_bul(ml)
    if not klasor:
        return False, "⚠️ Hangi klasörde arayacağımı anlayamadım (indirilenler, masaüstü, belgeler...)."

    uzantilar, tur_adi = _uzantilar_bul(ml)

    # İsim anahtar kelimeleri: tırnaklı ifade, "X adlı" kalıbı, ya da cümlede
    # kalan serbest kelimeler ("masaüstündeki safi_cv pdf'i aç" → 'safi_cv')
    isim_tokenlari = []
    # SADECE çift tırnak alıntıdır — tek tırnak Türkçe kesme işaretidir
    # ("pdf'i", "masaüstündeki'deki") ve alıntı sayılamaz!
    m = re.search(r'"(.+?)"', mesaj)
    if m:
        isim_tokenlari = [m.group(1).lower()]
    else:
        m = re.search(r'([\wçğıöşü\-. ]+?)\s+(?:adlı|isimli)\s+dosya', ml)
        if m:
            isim_tokenlari = [m.group(1).strip()]
        else:
            STOP = {'son', 'en', 'yeni', 'dosya', 'dosyayı', 'dosyasını', 'dosyaları',
                    'dosyalarını', 'aç', 'bul', 'listele', 'göster', 'var', 'mı', 'mi',
                    'i', 'ı', 'deki', 'daki', 'ki', 'bir', 'tane', 'lütfen'}
            for t in re.findall(r"[\wçğıöşü_.\-]+", ml):
                if t in STOP:
                    continue
                if any(t.startswith(k[:8]) for k in KLASORLER):   # klasör kelimeleri
                    continue
                if tur_adi and (t == tur_adi or t.startswith(tur_adi)):  # tür kelimesi (pdf'i dahil)
                    continue
                if t in TUR_UZANTILARI or t.lstrip('.') in {u.lstrip('.') for us in TUR_UZANTILARI.values() for u in us}:
                    continue
                isim_tokenlari.append(t)

    def _tara(tokenlarla: bool):
        bulunan = []
        for f in os.listdir(klasor):
            tam = os.path.join(klasor, f)
            if not os.path.isfile(tam):
                continue
            if uzantilar and os.path.splitext(f)[1].lower() not in uzantilar:
                continue
            if tokenlarla and isim_tokenlari and \
                    not all(t in f.lower() for t in isim_tokenlari):
                continue
            bulunan.append((tam, os.path.getmtime(tam)))
        return bulunan

    try:
        adaylar = _tara(tokenlarla=True)
        isim_notu = ""
        if not adaylar and isim_tokenlari:
            # İsimle eşleşmedi — isimsiz tekrar dene, kullanıcıyı bilgilendir
            adaylar = _tara(tokenlarla=False)
            if adaylar:
                isim_notu = (f"\n\nℹ️ \"{' '.join(isim_tokenlari)}\" adında dosya bulunamadı — "
                             f"klasördeki diğer eşleşmeler listelendi.")
    except Exception as e:
        return False, f"⚠️ Klasör okunamadı: {e}"

    if not adaylar:
        filtre = f" ({tur_adi})" if tur_adi else ""
        return True, (f"🔍 **{klasor_adi.title()}** klasöründe eşleşen dosya{filtre} bulunamadı.\n"
                      f"(Bakılan yol: `{klasor}`)")

    adaylar.sort(key=lambda x: x[1], reverse=True)  # en yeni önce

    # "aç" istenmişse en uygununu başlat — AMA aranan isim bulunamadıysa
    # alakasız dosyayı açma, listeyi göster
    if re.search(r'\baç\b', ml) and not isim_notu:
        hedef = adaylar[0][0]
        try:
            if sys.platform == 'win32':
                os.startfile(hedef)
            return True, (f"📂 **Açılıyor:** `{os.path.basename(hedef)}`\n"
                          f"({klasor_adi.title()} — "
                          f"{datetime.fromtimestamp(adaylar[0][1]).strftime('%d.%m.%Y %H:%M')})")
        except Exception as e:
            return True, f"⚠️ Dosya açılamadı: {e}"

    # Listele (ilk 8)
    lines = []
    for tam, mt in adaylar[:8]:
        boyut_mb = os.path.getsize(tam) / (1024 * 1024)
        lines.append(f"• `{os.path.basename(tam)}` — "
                     f"{datetime.fromtimestamp(mt).strftime('%d.%m %H:%M')} ({boyut_mb:.1f} MB)")
    kalan = f"\n… ve {len(adaylar) - 8} dosya daha" if len(adaylar) > 8 else ""
    return True, (f"🔍 **{klasor_adi.upper()}** içinde bulunanlar (en yeni önce):\n\n"
                  + "\n".join(lines) + kalan + isim_notu +
                  "\n\nAçmak için: `indirilenlerdeki son pdf'i aç` gibi söyleyebilirsin.")
