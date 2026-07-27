"""
ULTRON — TEK veri dizini.

SORUN (27 Tem 2026'ya kadar):
  • exe verisini `_internal` içinde tutuyordu, `python main.py` ise proje kökünde.
    Aynı Ultron'un hafızası nereden başlattığına göre değişiyordu.
  • `pyinstaller --noconfirm` COLLECT'ten önce `dist/ULTRON`'u komple siliyor →
    her derleme exe'nin config'ini ve veritabanını yok ediyordu.

ÇÖZÜM:
  İkisi de `%APPDATA%\\ULTRON` kullanır. Derleme veriye dokunamaz, iki başlatma
  yolu aynı hafızayı paylaşır.

GÖÇ:
  İlk çalıştırmada eski konumlardaki dosyalar (proje kökü / exe yanı / _internal)
  yeni dizine bir kez kopyalanır. Eski dosyalar SİLİNMEZ — geri dönüş mümkün kalsın.

TESTLER:
  `ULTRON_DATA_DIR` ortam değişkeni her şeyi geçersiz kılar; testler izole geçici
  dizin verip gerçek veriye dokunmadan çalışır.
"""

import os
import shutil
import sys

# Bu dosya core/ içinde → kod kökü bir üst klasör
_KOD_KOKU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Veri dizinine taşınan dosyalar. Yeni bir kalıcı dosya eklersen buraya da ekle,
# yoksa göç sırasında geride kalır.
VERI_DOSYALARI = (
    'config.json',
    'bilgiler.db',
    'file_index.db',
    'user_data.json',
    'app_cache.json',
    'capability_cache.json',
)


def _varsayilan_dizin() -> str:
    appdata = os.environ.get('APPDATA')
    if appdata:
        return os.path.join(appdata, 'ULTRON')
    # APPDATA yoksa (nadire) ev dizinine düş
    return os.path.join(os.path.expanduser('~'), '.ultron')


def _eski_konumlar() -> list:
    """Göç için taranacak eski dizinler — öncelik sırasıyla."""
    yerler = []
    if getattr(sys, 'frozen', False):
        # exe'nin yanı (config.json burada tutuluyordu)
        yerler.append(os.path.dirname(sys.executable))
    # _internal (frozen) veya proje kökü (python)
    yerler.append(_KOD_KOKU)
    return yerler


def _goc_et(hedef: str) -> None:
    """Hedefte olmayan her veri dosyasını eski konumlardan bir kez kopyalar."""
    for ad in VERI_DOSYALARI:
        hedef_yol = os.path.join(hedef, ad)
        if os.path.exists(hedef_yol):
            continue
        for eski_dizin in _eski_konumlar():
            kaynak = os.path.join(eski_dizin, ad)
            if os.path.abspath(kaynak) == os.path.abspath(hedef_yol):
                continue
            if os.path.exists(kaynak):
                try:
                    shutil.copy2(kaynak, hedef_yol)
                except Exception as e:
                    print(f"[ULTRON Paths] {ad} kopyalanamadi: {e}")
                else:
                    # NOT: mesajda ASCII disi karakter (ok isareti vb.) KULLANMA —
                    # Windows konsolu cp1254 ve print patlarsa basarili kopyalama
                    # "kopyalanamadi" gibi gorunur.
                    print(f"[ULTRON Paths] Goc edildi: {ad} <- {eski_dizin}")
                break


_dizin_cache = None


def veri_dizini() -> str:
    """Kalıcı veri dizini. İlk çağrıda oluşturulur ve göç bir kez çalışır."""
    global _dizin_cache
    if _dizin_cache is not None:
        return _dizin_cache

    hedef = os.environ.get('ULTRON_DATA_DIR') or _varsayilan_dizin()
    try:
        os.makedirs(hedef, exist_ok=True)
    except Exception as e:
        # Dizin açılamıyorsa kod köküne düş — uygulama yine de ayağa kalksın
        print(f"[ULTRON Paths] {hedef} açılamadı ({e}) — kod köküne düşülüyor.")
        _dizin_cache = _KOD_KOKU
        return _dizin_cache

    # ULTRON_DATA_DIR verilmişse test/izolasyon senaryosudur, göç yapma
    if not os.environ.get('ULTRON_DATA_DIR'):
        _goc_et(hedef)

    _dizin_cache = hedef
    return hedef


def veri_yolu(dosya_adi: str) -> str:
    """Veri dizini altındaki bir dosyanın tam yolu."""
    return os.path.join(veri_dizini(), dosya_adi)
