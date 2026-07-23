import os

SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.c', '.cpp',
    '.h', '.hpp', '.sql', '.log', '.csv', '.xml', '.bat', '.sh', '.ini', '.json'
}

def dosya_oku_ve_analiz_et(dosya_yolu: str, max_chars: int = 4000):
    """
    Verilen yoldaki dosyayı güvenli bir şekilde okur ve içeriğini döner.
    """
    dosya_yolu = dosya_yolu.strip().strip('"').strip("'")
    
    if not os.path.isabs(dosya_yolu):
        # Göreli yol ise mevcut çalışma dizinine bağla
        dosya_yolu = os.path.abspath(dosya_yolu)

    if not os.path.exists(dosya_yolu):
        return False, f"❌ Dosya bulunamadı: `{dosya_yolu}`"

    if os.path.isdir(dosya_yolu):
        # Klasör içeriğini listele
        try:
            files = os.listdir(dosya_yolu)
            file_list = "\n".join([f"• {f}" for f in files[:30]])
            return True, f"📁 **KLASÖR İÇERİĞİ (`{dosya_yolu}`):**\n\n{file_list}"
        except Exception as e:
            return False, f"Klasör okuma hatası: {e}"

    _ext = os.path.splitext(dosya_yolu)[1].lower()

    # PDF Desteği
    if _ext == '.pdf':
        try:
            import pypdf
            reader = pypdf.PdfReader(dosya_yolu)
            text_pages = []
            for i, page in enumerate(reader.pages[:10]):
                t = page.extract_text()
                if t:
                    text_pages.append(f"--- SAYFA {i+1} ---\n{t}")
            full_pdf_text = "\n".join(text_pages)[:max_chars]
            return True, f"📄 **PDF DOSYASI OKUNDU (`{os.path.basename(dosya_yolu)}`):**\n\n{full_pdf_text}"
        except ImportError:
            return False, "PDF okumak için `pypdf` kütüphanesi gerekli. `pip install pypdf` çalıştırabilirsiniz."
        except Exception as e:
            return False, f"PDF okuma hatası: {e}"

    # Metin & Kod Dosyaları Okuma
    try:
        with open(dosya_yolu, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(max_chars)
        
        filename = os.path.basename(dosya_yolu)
        truncated_note = "\n\n*(İçerik ilk 4000 karakter ile sınırlandırılmıştır)*" if len(content) >= max_chars else ""
        
        return True, f"📄 **DOSYA İÇERİĞİ (`{filename}`):**\n```\n{content}\n```{truncated_note}"
    except Exception as e:
        return False, f"Dosya okuma hatası: {e}"


def dosya_okuma_niyeti_algila(mesaj: str):
    """
    Mesajda dosya okuma niyetini algılar.
    Dönen değer: (DosyaOkunmalıMı, DosyaYolu)
    """
    mesaj_lower = mesaj.lower().strip()
    
    prefixes = ["oku:", "dosya oku:", "dosya incele:", "kod oku:", "pdf oku:"]
    for p in prefixes:
        if mesaj_lower.startswith(p):
            path = mesaj[len(p):].strip()
            return True, path

    if "dosyasını oku" in mesaj_lower or "dosyasını incele" in mesaj_lower:
        words = mesaj.split()
        for w in words:
            if "." in w and not w.startswith("http"):
                return True, w.strip()

    return False, None
