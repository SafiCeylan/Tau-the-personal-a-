# -*- coding: utf-8 -*-
"""
🤖 AJAN ÖLÇÜMÜ — gerçek konuşma arşiviyle, KURU çalıştırma.

    python scripts/ajan_olcum.py                 # yerel (Ollama), varsayılan örneklem
    python scripts/ajan_olcum.py --saglayici bulut --n 40   # Claude (ÜCRETLİDİR)

NE ÖLÇER:
  A) Bilinen komutlar — arşivde regex'in BAŞARIYLA yürüttüğü cümleler. Beklenen
     araç, o turun niyetine bağlı araçtır. Ajan aynı aracı seçiyor mu?
     (Canlıda bu cümleler ajana hiç gitmez; bu, modelin araç seçme yeteneğinin
     taban çizgisidir.)
  B) Kaçanlar — regex'in anlamadığı / başarısız saydığı kısa cümleler. Doğru
     cevap kayıtlı değil: ajanın ne yaptığı rapora yazılır, ELLE okunur.

GÜVENLİK: hiçbir araç gerçekten çalışmaz — defterdeki her aracın fonksiyonu
"(deneme) tamam" dönen bir kaydediciyle değiştirilir; ayrıca test zırhı kurulur.
Rapor kişisel cümleler içerir → repoya değil %APPDATA%\\ULTRON'a yazılır.
"""
import argparse
import os
import random
import sqlite3
import statistics
import sys
import time
from datetime import datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
os.chdir(KOK)


def _cumleleri_topla(db_yolu, n_a, n_b, tohum=7):
    from features.ses_kapisi import ortam_konusmasi_mi
    from core.tools import DEFTER
    c = sqlite3.connect(f"file:{db_yolu}?mode=ro", uri=True)
    try:
        satirlar = c.execute(
            "SELECT kullanici, intent, basarili FROM konusma "
            "WHERE kaynak = 'canli' ORDER BY id").fetchall()
    finally:
        c.close()

    def temiz(m):
        m = (m or '').strip()
        if m.startswith('['):              # "[Telegram] ", "[Zamanlanmış 08:00] "
            m = m.split('] ', 1)[-1]
        return m

    gorulen, a_havuz, b_havuz = set(), {}, []
    for metin, intent, basarili in satirlar:
        m = temiz(metin)
        anahtar = m.lower()
        if not m or anahtar in gorulen or ortam_konusmasi_mi(m):
            continue
        gorulen.add(anahtar)
        arac = DEFTER.intent_ile(intent) if intent else None
        if basarili and arac and intent != 'GENERAL_CONVERSATION':
            a_havuz.setdefault(intent, []).append((m, arac.ad))
        elif not basarili and len(m.split()) <= 12:
            b_havuz.append((m, intent))

    rnd = random.Random(tohum)
    # A: niyet başına dengeli örneklem (ekran görüntüsü 147 kez tekrar etmesin)
    a = []
    for intent in sorted(a_havuz):
        rnd.shuffle(a_havuz[intent])
        a += [(m, ad, intent) for m, ad in a_havuz[intent][:3]]
    rnd.shuffle(a)
    rnd.shuffle(b_havuz)
    return a[:n_a], b_havuz[:n_b]


def _araclari_kuru_yap():
    from core.tools import DEFTER, AracSonuc
    kayit = []
    for arac in DEFTER.hepsi():
        def sahte(_ad=arac.ad, **kw):
            kayit.append((_ad, kw.get('metin', '')))
            return AracSonuc.ok("(deneme) tamam")
        arac.calistir = sahte
    return kayit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saglayici', choices=('yerel', 'bulut'), default='yerel')
    ap.add_argument('--n', type=int, default=30, help='A kümesi örneklemi')
    ap.add_argument('--nb', type=int, default=15, help='B kümesi örneklemi')
    ap.add_argument('--model', default=None, help='Ollama/Claude model adı (config yerine)')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    from tests.safety import guvenlik_zirhi_kur
    guvenlik_zirhi_kur()
    import core.builtin_tools  # noqa: F401
    from core.paths import veri_yolu
    from core.ajan import Ajan, iz_satiri
    from features import ajan_saglayici as sg

    import json
    with open(veri_yolu('config.json'), encoding='utf-8') as f:
        config = json.load(f)
    if args.model:
        config['ollama_model' if args.saglayici == 'yerel' else 'claude_model'] = args.model

    a, b = _cumleleri_topla(veri_yolu('ogrenme.db'), args.n, args.nb)
    kayit = _araclari_kuru_yap()

    def yeni_saglayici():
        return sg.OllamaSaglayici(config) if args.saglayici == 'yerel' else sg.ClaudeSaglayici(config)

    def calistir(cumle):
        kayit.clear()
        t0 = time.perf_counter()
        sonuc = Ajan(yeni_saglayici(), config, kanal='olcum').calistir(cumle)
        return sonuc, time.perf_counter() - t0, [ad for ad, _ in kayit]

    etiket = yeni_saglayici().etiket
    satirlar = [f"# Ajan ölçümü — {etiket} — {datetime.now():%Y-%m-%d %H:%M}\n"]
    sureler, dogru, hatalar = [], 0, []
    print(f"A kümesi: {len(a)} cümle ({etiket})")
    for i, (cumle, beklenen, intent) in enumerate(a, 1):
        sonuc, sure, cagrilan = calistir(cumle)
        sureler.append(sure)
        secilen = cagrilan[0] if cagrilan else (
            sonuc.adimlar[0]['arac'] if sonuc.adimlar else None)
        tamam = secilen == beklenen
        dogru += tamam
        if sonuc.hata:
            hatalar.append(sonuc.hata)
        isaret = '✓' if tamam else '✗'
        print(f"  {i:2d} {isaret} {sure:5.1f}s  {cumle[:50]!r:52} beklenen={beklenen} secilen={secilen}")
        if not tamam:
            satirlar.append(f"- ✗ `{cumle}` — beklenen **{beklenen}** ({intent}), "
                            f"seçilen **{secilen}** {iz_satiri(sonuc)} {sonuc.hata or ''}")

    ozet_a = (f"A: {dogru}/{len(a)} doğru araç · ort {statistics.mean(sureler):.1f} sn · "
              f"medyan {statistics.median(sureler):.1f} sn · en uzun {max(sureler):.1f} sn"
              if sureler else "A: örneklem boş")
    print(ozet_a)
    satirlar.insert(1, f"**{ozet_a}**\n\n## A — yanlış seçimler\n")

    satirlar.append("\n## B — regex'in kaçırdıkları (elle değerlendir)\n")
    print(f"B kümesi: {len(b)} cümle")
    for cumle, intent in b:
        sonuc, sure, cagrilan = calistir(cumle)
        print(f"  {sure:5.1f}s  {cumle[:50]!r:52} → {cagrilan or '-'}")
        cevap = (sonuc.metin or sonuc.hata or '').replace('\n', ' ')[:160]
        satirlar.append(f"- `{cumle}` (regex: {intent}) → {cagrilan or 'araçsız'} — {cevap}")

    if hatalar:
        satirlar.append(f"\n**Sağlayıcı hataları:** {len(hatalar)} — örnek: {hatalar[0]}")
    rapor = veri_yolu(f"ajan_olcum-{args.saglayici}-{datetime.now():%Y%m%d-%H%M}.md")
    with open(rapor, 'w', encoding='utf-8') as f:
        f.write("\n".join(satirlar) + "\n")
    print(f"Rapor: {rapor}")


if __name__ == '__main__':
    main()
