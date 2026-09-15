"""
Derin Medya Entegrasyonu (Media Deep Integration).

Windows WinRT Media Manager API (`GlobalSystemMediaTransportControlsSessionManager`)
üzerinden 0ms gecikmeyle bilgisayarda çalan şarkı bilgilerini okur, Spotify URI protocol
ile şarkı/sanatçı aratıp başlatır ve şarkı sözlerini çeker.
"""

import asyncio
import os
import re
import sys
import subprocess
import urllib.parse
import requests
from typing import Dict, Any, Tuple, Optional


def _get_track_from_window_titles() -> Dict[str, Any]:
    """Window başlıklarını tarayarak Zen Browser/Spotify/YouTube/VLC üzerinde çalan parçayı yakalar."""
    try:
        import ctypes, psutil
        user32 = ctypes.windll.user32

        media_pids = set()
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = (p.info['name'] or '').lower()
                if any(k in name for k in ['zen', 'spotify', 'chrome', 'edge', 'firefox', 'brave', 'opera', 'vlc', 'wmplayer']):
                    media_pids.add(p.info['pid'])
            except Exception:
                pass

        titles = []
        def enum_cb(hwnd, lparam):
            try:
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in media_pids:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 2:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        titles.append(buf.value)
            except Exception:
                pass
            return True

        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        cb = CMPFUNC(enum_cb)
        user32.EnumWindows(cb, 0)

        for title in titles:
            t_lower = title.lower()
            if "spotify" in t_lower:
                clean = re.sub(r'\s*[-—–]\s*spotify.*$', '', title, flags=re.IGNORECASE).strip()
                if clean and clean.lower() not in ["spotify", "spotify free", "spotify premium", "spotify kanalı"]:
                    parts = [p.strip() for p in clean.split(" - ") if p.strip()]
                    artist = parts[0] if len(parts) > 1 else ""
                    s_title = parts[1] if len(parts) > 1 else parts[0]
                    return {"playing": True, "title": s_title, "artist": artist, "album": "Spotify"}

            if any(k in t_lower for k in ["youtube", "music", "zen", "chrome", "edge", "firefox", "brave"]):
                clean = re.sub(r'\s*[-—–]\s*(?:youtube(?:\s+music)?|zen(?:\s+browser)?|google chrome|microsoft edge|mozilla firefox|brave|opera).*$', '', title, flags=re.IGNORECASE).strip()
                if clean and clean.lower() not in ["youtube", "youtube music", "zen", "zen browser", "new tab", "yeni sekme"]:
                    parts = [p.strip() for p in clean.split(" - ") if p.strip()]
                    artist = parts[1] if len(parts) > 1 else ""
                    s_title = parts[0]
                    return {"playing": True, "title": s_title, "artist": artist, "album": "Web Media"}

            if "vlc" in t_lower:
                clean = re.sub(r'\s*[-—–]\s*vlc.*$', '', title, flags=re.IGNORECASE).strip()
                if clean and clean.lower() != "vlc media player":
                    return {"playing": True, "title": clean, "artist": "", "album": "VLC"}

    except Exception as e:
        print(f"[ULTRON MediaDeep] Window title tarama hatası: {e}")

    return {"playing": False, "title": "", "artist": "", "album": ""}


def get_currently_playing_track() -> Dict[str, Any]:
    """
    1. WinRT GlobalSystemMediaTransportControlsSessionManager (tüm oturumlar)
    2. Masaüstü Pencere Başlığı Taraması (Spotify, YouTube, VLC, vb.)
    3. Ekran Okuyucu (OCR) yedeklemesi
    """
    if sys.platform != 'win32':
        return {"playing": False, "title": "", "artist": "", "album": ""}
        
    # 1. Yöntem: WinRT Media Manager
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

        async def _get_media_info():
            manager = await MediaManager.request_async()
            if not manager:
                return None

            sessions_to_check = []
            curr = manager.get_current_session()
            if curr:
                sessions_to_check.append(curr)
            
            try:
                all_s = manager.get_sessions()
                if all_s:
                    for s in all_s:
                        if s not in sessions_to_check:
                            sessions_to_check.append(s)
            except Exception:
                pass

            for s in sessions_to_check:
                try:
                    info = await s.try_get_media_properties_async()
                    pb = s.get_playback_info()
                    if info and (info.title or info.artist):
                        is_playing = (pb.playback_status == 4) if (pb and hasattr(pb, 'playback_status')) else True
                        return {
                            "playing": is_playing,
                            "title": info.title or "",
                            "artist": info.artist or "",
                            "album": info.album_title or "",
                        }
                except Exception:
                    continue
            return None

        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(_get_media_info())
            if res and (res.get("title") or res.get("artist")):
                return res
        finally:
            loop.close()
    except Exception as e:
        print(f"[ULTRON MediaDeep] WinRT okuma uyarısı: {e}")

    # 2. Yöntem: Pencere Başlığı Taraması
    win_res = _get_track_from_window_titles()
    if win_res.get("playing") and (win_res.get("title") or win_res.get("artist")):
        return win_res

    # 3. Yöntem: OCR Ekran Taraması
    try:
        from features import screen_reader
        ocr_sonuc = screen_reader.ekrani_oku(tum_ekran=True)
        if ocr_sonuc.get("ok") and ocr_sonuc.get("metin"):
            metin = ocr_sonuc["metin"]
            m_eslesme = re.search(r'([A-ZÇĞİÖŞÜa-zçğıöşü0-9\s]{3,30})\s*[-–—]\s*([A-ZÇĞİÖŞÜa-zçğıöşü0-9\s]{3,30})', metin)
            if m_eslesme:
                p1, p2 = m_eslesme.group(1).strip(), m_eslesme.group(2).strip()
                return {"playing": True, "title": p2, "artist": p1, "album": "Ekran OCR"}
    except Exception:
        pass

    return {"playing": False, "title": "", "artist": "", "album": ""}


def spotify_cal(query: str) -> Tuple[bool, str]:
    """
    Spotify URI protocol (spotify:search:query) ile Spotify'ı açar ve şarkıyı aratıp oynatır.
    """
    q = (query or "").strip()
    if not q:
        return False, "Çalınacak şarkı veya sanatçı adı belirtilmedi."
    try:
        encoded = urllib.parse.quote(q)
        uri = f"spotify:search:{encoded}"
        subprocess.Popen(["cmd", "/c", "start", uri], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return True, f"🎵 **Spotify Başlatıldı:** `{q}` aranıyor ve oynatılıyor..."
    except Exception as e:
        return False, f"Spotify başlatılamadı: {e}"


def calan_sarki_bilgisi() -> Tuple[bool, str]:
    """Şu an çalan şarkının bilgilerini kullanıcıya sunar."""
    info = get_currently_playing_track()
    if info.get("playing") and (info.get("title") or info.get("artist")):
        title = info.get("title") or "Bilinmeyen Şarkı"
        artist = info.get("artist") or "Bilinmeyen Sanatçı"
        album = f" ({info['album']})" if info.get("album") else ""
        return True, f"🎵 **Şu An Çalıyor:** **{title}** — {artist}{album}"
    return False, "🎶 Şu an bilgisayarda çalan aktif bir medya/şarkı bulunamadı."


def sarki_sozu_bul(query: str = "") -> Tuple[bool, str]:
    """
    Çalan veya aranan şarkının sözlerini lrclib web servisinden çeker.
    """
    q = (query or "").strip()
    if not q:
        info = get_currently_playing_track()
        if info.get("playing") and info.get("title"):
            q = f"{info['title']} {info.get('artist', '')}".strip()
        else:
            return False, "Şu an çalan bir şarkı bulunamadı. Örnek komut: `sözleri bul: Barış Manço Gülpembe`"

    try:
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(q)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and data:
                item = data[0]
                lyrics = item.get("plainLyrics") or item.get("syncedLyrics")
                sarki_adi = item.get("trackName") or q
                sanatci = item.get("artistName") or ""
                if lyrics:
                    kesik = lyrics[:1200]
                    not_ = "\n\n*(Sözlerin devamı kesildi)*" if len(lyrics) > 1200 else ""
                    sanatci_str = f" - {sanatci}" if sanatci else ""
                    return True, f"📜 **{sarki_adi}{sanatci_str} Şarkı Sözleri:**\n\n```\n{kesik}\n```{not_}"
        return False, f"🔍 `{q}` için şarkı sözü bulunamadı."
    except Exception as e:
        return False, f"Şarkı sözü arama hatası: {e}"


def medya_derin_komutu_isle(mesaj: str) -> Optional[Dict[str, Any]]:
    """Derin medya komutunu yürütür."""
    m = (mesaj or "").strip()
    m_lower = m.lower()
    
    # 1. Şu an ne çalıyor? / çalan şarkı ne?
    if any(k in m_lower for k in ["ne çalıyor", "çalan şarkı", "hangi şarkı çalıyor", "çalan parça"]):
        status, res = calan_sarki_bilgisi()
        return {"tip": "direct", "sonuc": res}
        
    # 2. Şarkı sözleri bul
    if any(k in m_lower for k in ["şarkı söz", "sözleri bul", "sözlerini getir", "sözlerini oku"]):
        m_temiz = re.sub(r'^(?:şarkı\s+sözleri[nıe]?\s+bul|sözleri\s+bul|sözlerini\s+getir|sözlerini\s+oku)\s*:?\s*', '', m, flags=re.IGNORECASE).strip()
        status, res = sarki_sozu_bul(m_temiz)
        return {"tip": "direct", "sonuc": res}
        
    # 3. Açıkça Spotify belirtildiyse Spotify'dan çal
    if "spotify" in m_lower:
        m_temiz = re.sub(r'^(?:spotify(?:\'da|\'de|\'den)?\s+)?(?:şarkı\s+|müzik\s+)?', '', m, flags=re.IGNORECASE)
        m_temiz = re.sub(r'\s+(?:çal|oynat|başlat|aç)$', '', m_temiz, flags=re.IGNORECASE).strip()
        if m_temiz:
            status, res = spotify_cal(m_temiz)
            return {"tip": "direct", "sonuc": res}
            
    # 4. Genel Şarkı Çalma (YouTube / Web Oynatıcısı)
    if re.search(r'\b(çal|oynat)\b', m_lower) and not any(k in m_lower for k in ["duraklat", "durdur", "devam", "geç", "önceki"]):
        m_temiz = re.sub(r'^(?:youtube(?:\'da|\'dan)?\s+)?(?:şarkı\s+|müzik\s+)?', '', m, flags=re.IGNORECASE)
        m_temiz = re.sub(r'\s+(?:çal|oynat|başlat|aç)$', '', m_temiz, flags=re.IGNORECASE).strip()
        if m_temiz:
            from features.actions.system_control import sarki_otomatik_baslat
            status, res = sarki_otomatik_baslat(m_temiz)
            return {"tip": "direct", "sonuc": res}
            
    return None
