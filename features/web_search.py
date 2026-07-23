import html
import re
import urllib.parse
try:
    import requests
except ImportError:
    requests = None

def canli_web_ara(sorgu: str, max_results: int = 4):
    """
    DuckDuckGo HTML ve Wikipedia REST API üzerinden canlı Türkçe web araması yapar.
    API anahtarına ihtiyaç duymaz.
    """
    if requests is None:
        return False, "Hata: 'requests' kütüphanesi eksik."

    sorgu_temiz = sorgu.strip()
    results = []

    # 1. Wikipedia Türkçe Summary dene (özellikle kimdir, nedir soruları için)
    try:
        # "atatürk kimdir" → "atatürk" (soru kalıbı sayfa adında yer almaz)
        wiki_sorgu = re.sub(r'\b(kimdir|nedir|kim|ne demek|hakkında bilgi|hakkında)\b', '',
                            sorgu_temiz, flags=re.IGNORECASE).strip(' ?')
        wiki_q = urllib.parse.quote(wiki_sorgu or sorgu_temiz)
        wiki_url = f"https://tr.wikipedia.org/api/rest_v1/page/summary/{wiki_q}"
        wiki_res = requests.get(wiki_url, headers={'User-Agent': 'Ultron-AI/1.0'}, timeout=3)
        if wiki_res.status_code == 200:
            w_data = wiki_res.json()
            extract = w_data.get('extract')
            title = w_data.get('title')
            page_url = w_data.get('content_urls', {}).get('desktop', {}).get('page')
            if extract and len(extract) > 40:
                results.append({
                    'title': f"Wikipedia: {title}",
                    'snippet': extract,
                    'link': page_url or ""
                })
    except Exception:
        pass

    # 2. DuckDuckGo Instant Answer API (RESMİ API — kazıma değil, anahtarsız)
    #    NOT: html.duckduckgo.com kazıması bot korumasına takıldığı için kaldırıldı.
    try:
        res = requests.get(
            'https://api.duckduckgo.com/',
            params={'q': sorgu_temiz, 'format': 'json', 'no_html': 1, 'skip_disambig': 1},
            headers={'User-Agent': 'Ultron-AI/1.0'}, timeout=6
        )
        if res.status_code == 200:
            d = res.json()
            abstract = (d.get('AbstractText') or '').strip()
            if abstract:
                results.append({
                    'title': d.get('Heading') or 'DuckDuckGo Özeti',
                    'snippet': abstract,
                    'link': d.get('AbstractURL') or ''
                })
            for topic in (d.get('RelatedTopics') or [])[:3]:
                t = (topic.get('Text') or '').strip()
                if t:
                    results.append({'title': 'İlgili', 'snippet': t,
                                    'link': topic.get('FirstURL') or ''})
    except Exception as e:
        print(f"[Ultron Web Search] DDG API hatası: {e}")

    # 3. Google News RSS (resmi besleme) — haber sorguları ve son çare için
    if not results or any(k in sorgu_temiz.lower() for k in ['haber', 'son dakika', 'gündem']):
        try:
            rss_url = ("https://news.google.com/rss/search?q=" +
                       urllib.parse.quote(sorgu_temiz) + "&hl=tr&gl=TR&ceid=TR:tr")
            res = requests.get(rss_url, headers={'User-Agent': 'Ultron-AI/1.0'}, timeout=6)
            if res.status_code == 200:
                items = re.findall(r'<item><title>(.*?)</title>', res.text, re.DOTALL)
                for baslik in items[:max_results]:
                    temiz = html.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', baslik)).strip()
                    if temiz:
                        results.append({'title': '📰 Haber', 'snippet': temiz, 'link': ''})
        except Exception as e:
            print(f"[Ultron Web Search] Google News hatası: {e}")

    if not results:
        return False, f"'{sorgu_temiz}' için web araması sonucu bulunamadı."

    # Format Output
    output_lines = [f"🌐 **CANLI WEB ARAMASI SONUÇLARI ('{sorgu_temiz}')**\n"]
    for idx, item in enumerate(results[:max_results], 1):
        output_lines.append(f"**{idx}. {item['title']}**\n{item['snippet']}\n")

    return True, "\n".join(output_lines)


def web_arama_niyeti_algila(mesaj: str):
    """
    Mesajda canlı web araması gerektiren bir niyet var mı algılar.
    Dönen değer: (AramaYapılmalıMı, AramaSorgusu)
    """
    mesaj_lower = mesaj.lower().strip()
    
    # Doğrudan tetikleyiciler
    prefixes = ["ara:", "internet:", "google:", "web:", "arama yap:", "haberler:", "canlı:"]
    for p in prefixes:
        if mesaj_lower.startswith(p):
            query = mesaj[len(p):].strip()
            return True, query

    # Niyet kelimeleri
    trigger_words = ["hava durumu", "dolar kaç", "euro kaç", "haberler", "en son haber", "arama yap", "internette ara"]
    for tw in trigger_words:
        if tw in mesaj_lower:
            return True, mesaj

    return False, None
