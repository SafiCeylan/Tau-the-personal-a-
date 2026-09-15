# -*- coding: utf-8 -*-
"""
AÇILIŞ HIZI REGRESYON TESTİ.

NEDEN SÜRE ÖLÇMÜYOR: "açılış 1 sn'den kısa olmalı" gibi bir eşik makineye,
diske ve o anki yüke göre değişir; CI'da ya sürekli kırmızı olur ya da eşiği
o kadar gevşetirsin ki hiçbir şey yakalamaz. Onun yerine SEBEBİ ölçüyoruz:
ağır kütüphaneler açılışta import EDİLİYOR MU? Bu deterministiktir.

Ölçülen (15 Eyl 2026): `ui.tau_window` importu soğukta 2.784 ms sürüyordu,
1.737 ms'si `features.speech`, 1.671 ms'si tek başına `pygame` (numpy +
pkg_resources zincirini çekiyor). Üçü de yalnızca fonksiyon içinde kullanılıyor.
Tembel import sonrası: 678 ms.

Yeni bir ağır bağımlılık üst seviyeye sızarsa bu test onu yakalar.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent

# Açılışta YÜKLENMEMESİ gereken ağır kütüphaneler ve ölçülen maliyetleri.
YASAKLI = {
    'pygame': 'mp3 çalmak için — ilk seslendirmede yüklenir (~660 ms)',
    'gtts': 'yedek TTS — yalnız edge-tts başarısız olursa (~377 ms)',
    'speech_recognition': 'mikrofon — ilk dinlemede yüklenir (~184 ms)',
    'numpy': 'pygame üzerinden sızıyordu (~670 ms)',
    'pkg_resources': 'pygame üzerinden sızıyordu (~350 ms)',
}


def _yuklenen_modulleri_al(import_edilecek: str) -> set:
    """Temiz bir yorumlayıcıda modülü import eder, sys.modules'ü geri döner.

    Ayrı süreçte çalışır: bu test dosyasının kendisi (ve diğer testler) pygame'i
    çoktan yüklemiş olabilir, aynı süreçte ölçmek yanıltıcı olurdu.
    """
    kod = (
        'import sys, json;'
        f'__import__("{import_edilecek}");'
        'print(json.dumps(sorted(sys.modules)))'
    )
    sonuc = subprocess.run(
        [sys.executable, '-c', kod],
        cwd=str(PROJE_KOKU), capture_output=True, text=True, timeout=180,
    )
    if sonuc.returncode != 0:
        raise AssertionError(
            '%s import edilemedi:\n%s' % (import_edilecek, sonuc.stderr[-2000:])
        )
    # Bazı kütüphaneler stdout'a banner basıyor (pygame gibi) — son satırı al.
    son_satir = [s for s in sonuc.stdout.strip().split('\n') if s.strip()][-1]
    return set(json.loads(son_satir))


class AcilisHiziTest(unittest.TestCase):

    def test_agir_kutuphaneler_acilista_yuklenmez(self):
        """Ana pencere modülü ağır ses/görüntü bağımlılıklarını çekmemeli."""
        yuklu = _yuklenen_modulleri_al('ui.tau_window')

        sizanlar = {ad: neden for ad, neden in YASAKLI.items() if ad in yuklu}
        if sizanlar:
            satirlar = '\n'.join(
                '  • %s — %s' % (ad, neden) for ad, neden in sorted(sizanlar.items())
            )
            self.fail(
                'Şu ağır kütüphaneler AÇILIŞTA yükleniyor:\n%s\n\n'
                'Bunları üst seviye `import` yerine kullanıldıkları fonksiyonun '
                'içine taşı (bkz. features/speech.py `_pg()` / `_sr()`). '
                'Ölçüm için: python -X importtime -c "import ui.tau_window"'
                % satirlar
            )

    def test_speech_modulu_tek_basina_da_hafif(self):
        """features.speech import edilmek TTS yığınını yüklememeli."""
        yuklu = _yuklenen_modulleri_al('features.speech')

        for ad in ('pygame', 'gtts', 'speech_recognition'):
            self.assertNotIn(
                ad, yuklu,
                '`features.speech` import edilirken %s de yükleniyor — '
                'tembel import bozulmuş.' % ad,
            )

    def test_tembel_yukleyiciler_gercekten_calisiyor(self):
        """`_pg()` / `_sr()` çağrıldığında modül gerçekten geliyor mu?

        Tembel import'un ucuz olması yetmez; çağrıldığında ÇALIŞMASI gerekir.
        Yoksa açılış hızlanır ama ses tamamen bozulur.
        """
        from features import speech

        self.assertEqual(speech._pg().__name__, 'pygame')
        self.assertEqual(speech._sr().__name__, 'speech_recognition')
        # Gerçekten kullanılan alt modüller de erişilebilir olmalı
        self.assertTrue(hasattr(speech._pg(), 'mixer'))
        self.assertTrue(hasattr(speech._sr(), 'Recognizer'))


if __name__ == '__main__':
    unittest.main()
