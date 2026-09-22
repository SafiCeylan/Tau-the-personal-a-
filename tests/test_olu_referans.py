# -*- coding: utf-8 -*-
"""
ÖLÜ REFERANS KİLİDİ — sınıfta TANIMLANMAMIŞ `self._metot` çağrısı yakalanır.

NEDEN VAR: Bu hata sınıfı projede iki kez, ikisinde de haftalarca fark
edilmeden yaşadı. İkisinde de uygulama çökmedi çünkü çağrı bir Qt slot'u /
QTimer geri çağrısı içindeydi ve Qt istisnayı YUTTU:

  • `settings_view.save_settings` → `self._pozitif_sayi` (5 Ağu – 15 Eyl):
    "Kaydet" hiçbir ayarı kaydetmedi.
  • `tau_window._konusma_bitince_duplex_devam` → `self._on_wake_word`
    (13 Ağu – 16 Eyl): canlı sesli sohbet ilk cevaptan sonra dinlemeye hiç
    dönmedi.

Birim testleri ikisini de göremezdi — kimse o yolu çağırmıyordu. Bu test
kodu ÇALIŞTIRMADAN okur (AST): her sınıf için `self._x` biçimindeki erişimleri
toplar, sınıfta (ve aynı dosyadaki üst sınıflarında) tanımlı ya da atanmış
mı diye bakar.

Kapsam bilerek alt çizgili adlarla sınırlı: `self.show()` gibi Qt'den miras
gelen genel metotları bu yöntemle ayırt etmek mümkün değil; projenin kendi
yardımcıları ise alt çizgiyle başlıyor.
"""
import ast
import unittest
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent
TARANAN_KLASORLER = ('ui', 'features', 'core')


def _sinif_tanimlari(sinif: ast.ClassDef) -> set:
    """Sınıf gövdesindeki metotlar + sınıf değişkenleri + herhangi bir yerde
    `self.ad = ...` / `setattr(self, 'ad', ...)` ile atanan adlar."""
    adlar = set()
    for dugum in sinif.body:
        if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
            adlar.add(dugum.name)
        elif isinstance(dugum, ast.Assign):
            for hedef in dugum.targets:
                if isinstance(hedef, ast.Name):
                    adlar.add(hedef.id)
        elif isinstance(dugum, ast.AnnAssign) and isinstance(dugum.target, ast.Name):
            adlar.add(dugum.target.id)

    for dugum in ast.walk(sinif):
        hedefler = []
        if isinstance(dugum, ast.Assign):
            hedefler = dugum.targets
        elif isinstance(dugum, (ast.AugAssign, ast.AnnAssign)):
            hedefler = [dugum.target]
        elif isinstance(dugum, (ast.For, ast.With)):
            hedefler = [getattr(dugum, 'target', None)] + [
                o.optional_vars for o in getattr(dugum, 'items', [])]
        for hedef in hedefler:
            for alt in ast.walk(hedef) if hedef is not None else []:
                if (isinstance(alt, ast.Attribute) and isinstance(alt.value, ast.Name)
                        and alt.value.id == 'self'):
                    adlar.add(alt.attr)
        if (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name)
                and dugum.func.id == 'setattr' and len(dugum.args) >= 2
                and isinstance(dugum.args[1], ast.Constant)):
            adlar.add(dugum.args[1].value)
    return adlar


def _self_erisimleri(sinif: ast.ClassDef):
    """[(ad, satır)] — `self._ad` okumaları (dunder hariç)."""
    for dugum in ast.walk(sinif):
        if (isinstance(dugum, ast.Attribute) and isinstance(dugum.ctx, ast.Load)
                and isinstance(dugum.value, ast.Name) and dugum.value.id == 'self'
                and dugum.attr.startswith('_') and not dugum.attr.startswith('__')):
            yield dugum.attr, dugum.lineno


def _getattr_varsayilanli_okumalar(agac: ast.AST) -> set:
    """`getattr(self, '_x', varsayilan)` — bilinçli "yoksa" okuması, ölü değil."""
    satirlar = set()
    for dugum in ast.walk(agac):
        if (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name)
                and dugum.func.id in ('getattr', 'hasattr')):
            satirlar.add(dugum.lineno)
    return satirlar


def olu_referanslari_bul(kaynak: str, dosya_adi: str = '<kaynak>'):
    """[(sınıf, ad, satır)] — tanımı bulunamayan `self._ad` erişimleri."""
    agac = ast.parse(kaynak, filename=dosya_adi)
    siniflar = {d.name: d for d in ast.walk(agac) if isinstance(d, ast.ClassDef)}

    def tum_tanimlar(sinif, gorulen=None):
        gorulen = gorulen or set()
        if sinif.name in gorulen:
            return set()
        gorulen.add(sinif.name)
        adlar = _sinif_tanimlari(sinif)
        for taban in sinif.bases:
            taban_adi = getattr(taban, 'id', None) or getattr(taban, 'attr', None)
            if taban_adi in siniflar:
                adlar |= tum_tanimlar(siniflar[taban_adi], gorulen)
        return adlar

    def disaridan_miras_var_mi(sinif):
        """Aynı dosyada OLMAYAN bir proje sınıfından miras alıyorsa emin olamayız."""
        for taban in sinif.bases:
            taban_adi = getattr(taban, 'id', None) or getattr(taban, 'attr', None)
            if taban_adi in siniflar:
                if disaridan_miras_var_mi(siniflar[taban_adi]):
                    return True
            elif taban_adi and not (taban_adi.startswith('Q') or taban_adi in (
                    'object', 'Exception', 'RuntimeError', 'ValueError', 'dict',
                    'BaseHTTPRequestHandler', 'ThreadingHTTPServer', 'HTTPServer',
                    'Thread')):
                return True
        return False

    bulunan = []
    for sinif in siniflar.values():
        if disaridan_miras_var_mi(sinif):
            continue
        tanimli = tum_tanimlar(sinif)
        for ad, satir in _self_erisimleri(sinif):
            if ad not in tanimli:
                bulunan.append((sinif.name, ad, satir))
    return bulunan


class OluReferansTaramasiTest(unittest.TestCase):

    def test_projede_olu_self_referansi_yok(self):
        hatalar = []
        for klasor in TARANAN_KLASORLER:
            for yol in sorted((PROJE_KOKU / klasor).rglob('*.py')):
                kaynak = yol.read_text(encoding='utf-8')
                for sinif, ad, satir in olu_referanslari_bul(kaynak, str(yol)):
                    goreli = yol.relative_to(PROJE_KOKU)
                    hatalar.append(f'  • {goreli}:{satir}  {sinif}.{ad} tanımlı değil')
        if hatalar:
            self.fail('Sınıfta TANIMLANMAMIŞ metot/özellik çağrılıyor (Qt slot içindeyse '
                      'hata sessizce yutulur):\n' + '\n'.join(hatalar))


class TarayicininKendisiTest(unittest.TestCase):
    """Tarayıcı hiçbir şey bulmadığında yeşil yanmak kolay — gerçekten yakalıyor mu?"""

    def test_16_eyl_duplex_hatasini_yakalar(self):
        kaynak = (
            "class Pencere(QMainWindow):\n"
            "    def _konusma_bitince(self):\n"
            "        QTimer.singleShot(600, self._on_wake_word)\n"
            "    def _on_wake_detected(self):\n"
            "        pass\n"
        )
        self.assertEqual(olu_referanslari_bul(kaynak),
                         [('Pencere', '_on_wake_word', 3)])

    def test_15_eyl_ayarlar_hatasini_yakalar(self):
        kaynak = (
            "class Ayarlar(QWidget):\n"
            "    def save_settings(self):\n"
            "        return self._pozitif_sayi('8899', 8899)\n"
        )
        self.assertEqual(olu_referanslari_bul(kaynak),
                         [('Ayarlar', '_pozitif_sayi', 3)])

    def test_atanan_ozellik_ve_miras_ölü_sayilmaz(self):
        kaynak = (
            "class Taban(QWidget):\n"
            "    def _ortak(self):\n"
            "        pass\n"
            "class Cocuk(Taban):\n"
            "    def __init__(self):\n"
            "        self._sayac = 0\n"
            "    def calis(self):\n"
            "        self._ortak()\n"
            "        return self._sayac\n"
        )
        self.assertEqual(olu_referanslari_bul(kaynak), [])


if __name__ == '__main__':
    unittest.main()
