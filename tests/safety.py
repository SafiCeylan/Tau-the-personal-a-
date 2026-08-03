# -*- coding: utf-8 -*-
"""
Test Güvenlik Zırhı — testler GERÇEK yan etki üretmesin.

Sorun: bu paketteki testler `sistem_komutu_algila` gibi gerçek yürütücüleri
doğrudan çağırıyor. Zırh olmadan `python -m pytest tests/` komutu:
  • açık Chrome'u GERÇEKTEN kapatır (taskkill + psutil.kill),
  • sistem ses seviyesini GERÇEKTEN değiştirir (pycaw),
  • uygulama açar, tarayıcı sekmesi açar, medya tuşu gönderir,
  • bilgisayarı kilitler,
  • ⌨️ AKTİF PENCEREYE TUŞ BASAR (Ctrl+Enter, "1234"+Enter…),
  • 🧠 kullanıcının GERÇEK öğrenme arşivine test cümleleri yazar.

⚠️ ZIRH MODÜL BAZLIDIR. `system_control` içindeki `ctypes`'ı taklitlemek
`level4_input`'u KORUMAZ — o kendi `ctypes`'ını import eder. Klavye testleri
eklenince bu delik açıldı ve testler gerçekten tuş basmaya başladı. Yeni bir
modül OS'a doğrudan dokunuyorsa buraya da bir satır eklenmeli.

Çözüm: yürütmenin EN DİBİNDEKİ işletim sistemi çağrıları taklitle değiştirilir.
Üstteki iş mantığı (regex, niyet, mesaj üretimi) gerçek kalır — yani testler
hâlâ gerçek kodu sınar, sadece OS'a dokunan son adım kesilir.

Kullanım (test modülünün başında):

    from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir

    def setUpModule():
        guvenlik_zirhi_kur()

    def tearDownModule():
        guvenlik_zirhi_kaldir()

`CAGRI_KAYDI` listesinden hangi OS çağrısının denendiği doğrulanabilir.
"""

import os
import sys
import ctypes as _gercek_ctypes
from unittest import mock

# Zırh sırasında yakalanan OS çağrıları: [("subprocess.run", "taskkill /F /IM chrome.exe"), ...]
CAGRI_KAYDI = []

_patcher_listesi = []
_kurulu = False


# ---------------------------------------------------------------------------
# Sahte subprocess — taskkill, powershell, explorer hiç çalışmaz
# ---------------------------------------------------------------------------
class _SahteSonuc:
    """subprocess.run dönüşünün taklidi. returncode=0 → 'başarılı' yolu sınanır."""
    returncode = 0
    stdout = b""
    stderr = b""


class _SahteSubprocess:
    DEVNULL = -3
    PIPE = -1
    STDOUT = -2
    CREATE_NO_WINDOW = 0x08000000

    @staticmethod
    def run(cmd, *args, **kwargs):
        CAGRI_KAYDI.append(("subprocess.run", cmd))
        return _SahteSonuc()

    @staticmethod
    def Popen(cmd, *args, **kwargs):
        CAGRI_KAYDI.append(("subprocess.Popen", cmd))
        return None

    @staticmethod
    def call(cmd, *args, **kwargs):
        CAGRI_KAYDI.append(("subprocess.call", cmd))
        return 0


# ---------------------------------------------------------------------------
# Sahte pycaw — ses seviyesi okunur ama YAZILMAZ
# ---------------------------------------------------------------------------
class _SahteVolume:
    def GetMasterVolumeLevelScalar(self):
        return 0.5  # testler sabit %50'den yola çıksın

    def SetMasterVolumeLevelScalar(self, deger, _=None):
        CAGRI_KAYDI.append(("volume.set", deger))

    def SetMute(self, deger, _=None):
        CAGRI_KAYDI.append(("volume.mute", deger))


class _SahteHoparlor:
    EndpointVolume = _SahteVolume()


class _SahteAudioUtilities:
    @staticmethod
    def GetSpeakers():
        return _SahteHoparlor()


# ---------------------------------------------------------------------------
# Sahte ctypes — keybd_event (ses/medya tuşları) ve LockWorkStation susturulur
# ---------------------------------------------------------------------------
class _SahteUser32:
    def __getattr__(self, ad):
        def _yut(*args, **kwargs):
            CAGRI_KAYDI.append((f"user32.{ad}", args))
            return 0
        return _yut


class _SahteWindll:
    user32 = _SahteUser32()

    def __getattr__(self, ad):
        return _SahteUser32()


class _SahteCtypes:
    """windll dışındaki her şeyi gerçek ctypes'a devreder (yapılar bozulmasın)."""
    windll = _SahteWindll()

    def __getattr__(self, ad):
        return getattr(_gercek_ctypes, ad)


# ---------------------------------------------------------------------------
# Kurulum / söküm
# ---------------------------------------------------------------------------
def guvenlik_zirhi_kur():
    """OS'a dokunan tüm çıkışları taklitle değiştirir. İki kez çağrılırsa yok sayar."""
    global _kurulu
    if _kurulu:
        return
    CAGRI_KAYDI.clear()

    import features.actions.system_control as sc

    hedefler = [
        # Süreç/komut çalıştırma (taskkill, powershell Get-StartApps, explorer)
        mock.patch.object(sc, 'subprocess', _SahteSubprocess),
        # Ses donanımı
        mock.patch.object(sc, 'ctypes', _SahteCtypes()),
        # Uygulama açma
        mock.patch.object(os, 'startfile', _kaydet('os.startfile'), create=True),
        mock.patch.object(os, 'system', _kaydet('os.system')),
        # Tarayıcı sekmesi açma (şarkı başlatma vb.)
        mock.patch('webbrowser.open', _kaydet('webbrowser.open')),
        mock.patch('webbrowser.open_new_tab', _kaydet('webbrowser.open_new_tab')),
        # Süreç öldürme — açık uygulamalar kapanmasın
        mock.patch('psutil.Process.kill', _kaydet('psutil.kill')),
        mock.patch('psutil.Process.terminate', _kaydet('psutil.terminate')),
        # Cache dosyası testte diske yazılmasın
        mock.patch.object(sc, '_save_app_cache', _kaydet('app_cache.save')),
    ]

    # pycaw kuruluysa ses API'sini de kes
    if getattr(sc, 'PYCAW_AVAILABLE', False):
        hedefler.append(mock.patch.object(sc, 'AudioUtilities', _SahteAudioUtilities))

    # ⌨️ AIP Level 4 — klavye emülasyonu. İki ayrı çıkış var:
    #   • keybd_event / MapVirtualKeyW  → level4_input'un KENDİ ctypes'ı
    #   • pywinauto.keyboard.send_keys  → fonksiyon içinde import ediliyor,
    #     bu yüzden kaynak modülde yamalanır (yerel isim değil).
    try:
        from core.interaction import level4_input as _l4
        hedefler.append(mock.patch.object(_l4, 'ctypes', _SahteCtypes()))
    except Exception as e:  # pywinauto/pencere ortamı yoksa modül yüklenmeyebilir
        print(f"[Zırh] level4_input yamalanamadı: {e}")

    try:
        import pywinauto.keyboard  # noqa: F401
        hedefler.append(mock.patch('pywinauto.keyboard.send_keys',
                                   _kaydet('keyboard.send_keys')))
    except Exception as e:
        print(f"[Zırh] pywinauto.keyboard yamalanamadı: {e}")

    # 🧠 ÖĞRENME ARŞİVİ — testler GERÇEK `%APPDATA%\ULTRON\ogrenme.db` dosyasına
    # yazmasın. Zırhsız hâlde niyet katmanından geçen her test cümlesi kullanıcının
    # gerçek arşivine düşüyor ve "ne öğrendin" raporunu test verisiyle kirletiyordu.
    # (Zırh yalnızca OS'u değil, KALICI VERİYİ de korumalı.)
    try:
        from features import chat_learning as _cl
        hedefler.append(mock.patch.object(_cl, '_db_yolu',
                                          lambda: _gecici_ogrenme_db()))
    except Exception as e:
        print(f"[Zırh] chat_learning yamalanamadı: {e}")

    # 💡 ÖNERİ KARARLARI ve ⚡ ÖZEL KISAYOLLAR — ikisi de kullanıcının gerçek
    # `%APPDATA%\ULTRON` klasörüne JSON yazar. Öğrenme raporu artık öneri
    # ürettiği için, raporu çağıran HER test gösterilen listeyi diske
    # işaretliyor; kısayol önerisini kabul eden bir test ise kullanıcının
    # menüsüne gerçek bir buton ekler.
    for _modul_adi in ('suggestions', 'custom_shortcuts'):
        try:
            _modul = __import__(f'features.{_modul_adi}', fromlist=[_modul_adi])
            hedefler.append(mock.patch.object(
                _modul, '_dosya_yolu',
                lambda _ad=_modul_adi: _gecici_veri_dosyasi(f'{_ad}.json')))
        except Exception as e:
            print(f"[Zırh] {_modul_adi} yamalanamadı: {e}")

    for p in hedefler:
        p.start()
        _patcher_listesi.append(p)

    _kurulu = True


def guvenlik_zirhi_kaldir():
    """Zırhı söker — gerçek OS çağrıları geri gelir."""
    global _kurulu
    while _patcher_listesi:
        try:
            _patcher_listesi.pop().stop()
        except Exception:
            pass
    _kurulu = False


_gecici_ogrenme_yolu = None


def _gecici_ogrenme_db() -> str:
    """Zırh süresince kullanılacak tek kullanımlık öğrenme veritabanı yolu."""
    global _gecici_ogrenme_yolu
    if _gecici_ogrenme_yolu is None:
        import tempfile
        _gecici_ogrenme_yolu = os.path.join(
            tempfile.mkdtemp(prefix='ultron_test_ogrenme_'), 'ogrenme.db')
    return _gecici_ogrenme_yolu


_gecici_veri_dizini = None


def _gecici_veri_dosyasi(dosya_adi: str) -> str:
    """Zırh süresince JSON durum dosyaları için tek kullanımlık dizin."""
    global _gecici_veri_dizini
    if _gecici_veri_dizini is None:
        import tempfile
        _gecici_veri_dizini = tempfile.mkdtemp(prefix='ultron_test_veri_')
    return os.path.join(_gecici_veri_dizini, dosya_adi)


def _kaydet(etiket):
    """Çağrıyı kaydedip 0 dönen no-op üretir."""
    def _sahte(*args, **kwargs):
        CAGRI_KAYDI.append((etiket, args))
        return 0
    return _sahte


def cagri_yapildi_mi(etiket_parcasi: str) -> bool:
    """Zırhın belirli bir OS çağrısını yakalayıp yakalamadığını söyler."""
    return any(etiket_parcasi in str(e) for e, _ in CAGRI_KAYDI)
