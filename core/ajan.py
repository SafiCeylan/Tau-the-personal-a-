# -*- coding: utf-8 -*-
"""
🤖 AJAN ÇEKİRDEĞİ (Faz 1, 15 Eki 2026) — dil modeli araçları KENDİSİ çağırır.

NEDEN: Ultron'un beyni regex'ti. Kalıba uyan cümle (≈%80) mükemmel çalışıyor,
uymayan her şey sohbete düşüyordu: canlı kayıtta 329 sohbet turunun 314'ü
"başarısız". Eski LLM yardımcıları (llm_intent sınıflandırıcı, JSON planner)
modeli yalnızca ETİKETÇİ olarak kullanıyordu; eylem yine regex'e kalıyordu.

ÇÖZÜM — hızlı yol aynen kalır, ajan yalnızca regex'in BIRAKTIĞINI alır:

    cümle → regex niyet → araç   (deterministik, ms — değişmedi)
          ↘ sohbete düştüyse ya da çok adımlıysa:
            AJAN: model + defterdeki araçların şeması
                  → araç çağrısı → GÜVENLİK KATMANI → yürüt → sonuç modele
                  → … (en fazla `ajan_max_adim`)

KURALLAR (tuzaklar tablosundaki derslerin ajan karşılığı):
  • Güvenlik kuralı tekrar YAZILMAZ: her çağrının metni `SecurityAnalyzerLayer`
    dan geçer. CONFIRM → ajan DURUR, mevcut onay kartına devreder.
    FORBIDDEN → çağrı reddedilir, model bunu sonuç olarak görür.
  • `RISK_ONAY` araçları (mesaj/dosya gönderme, ekrana tıklama) ajan içinde
    ASLA doğrudan çalışmaz — her zaman onay kartı.
  • Model "yaptım" diyemez: araç sonucu gelmeden eylem anlatmak yasak
    (sistem talimatı) ve reflection katmanı yine çalışır.
  • Bulut modeline (Claude) ekran/pano/dosya İÇERİĞİ okuyan araçlar verilmez —
    "ekran içeriği yalnız yerel modele" kuralının aynısı.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.tools import DEFTER, RISK_ONAY, AracSonuc

# Ajana HİÇ verilmeyen araçlar.
#   ogrenilmis_cevap → sohbet içi yardımcı, eylem değil
#   ogrenme_raporu   → "şunu unut / öneriyi uygula" kalıcı öğrenme kararıdır;
#                      model kendi kendine öneri kuramamalı (öneri motoru kuralı)
AJANA_KAPALI = frozenset({'ogrenilmis_cevap', 'ogrenme_raporu'})

# Bulut modeline verilmeyen araçlar: sonuçları ekranın/panonun/dosyanın
# İÇERİĞİNİ taşır. Bu kural ajan öncesinde de vardı (OCR içeriği Gemini'ye
# gitmez); ajan onu delmemeli. Kullanıcı bunları isterse komut zaten regex
# yolunda (yerel) karşılanır.
BULUTA_KAPALI = frozenset({'ekrani_oku', 'pano_isle', 'dosya_oku', 'ekranda_sec',
                           'ekranda_tikla', 'ekran_takip'})

# Onaydan sonra metin yönlendirmesiyle (confirmed_executor) değil, AYNI araçla
# yürütülecek olanlar: onaylı yürütücünün bunlar için regex dalı yok.
DOGRUDAN_ONAYLI = frozenset({'ekranda_tikla', 'ekranda_sec'})

MAKS_SONUC = 1500          # modele dönen araç çıktısı (küçük modelin bağlamı dar)
VARSAYILAN_MAX_ADIM = 5

SISTEM_TALIMATI = """Sen ULTRON'sun: kullanıcının Windows bilgisayarında çalışan kişisel asistanı. Türkçe, kısa ve net konuşursun.

ARAÇ KULLANIMI
- Kullanıcı bilgisayarda bir İŞ istiyorsa (uygulama, ses, müzik, dosya, hatırlatma, takvim, not, arama, hava, döviz…) METİNLE CEVAP VERME, uygun aracı çağır.
- Sık eşleşmeler: tuşa basma → klavye_tusu · uygulama aç/kapat, ses seviyesi → uygulama_calistir · şarkı çal → medya_derin · duraklat/sonraki şarkı → medya_kontrol · harcama → finans_takip · hatırlatma → hatirlatma_kur · takvim → takvim_yonet · pencereye geç → pencereye_gec · dosya bul → dosya_ara · internette ara → web_ara.
- Her araca `metin` alanında kısa, açık bir Türkçe KOMUT CÜMLESİ ver; araç bu cümleyi kendisi ayrıştırır. Örnekler: "chrome aç", "sesi %30 yap", "yarın 14:00'te toplantıyı hatırlat", "staj raporu dosyasını bul".
- Birden fazla iş varsa sırayla araç çağır. Bir adım başarısız olursa dur ve kullanıcıya söyle.
- Soru ya da sohbetse araç çağırmadan cevap ver.
- Ne istendiğinden emin değilsen tahmin etme, kısa bir soru sor.

DÜRÜSTLÜK
- Araç sonucu gelmeden bir işi yaptığını ASLA söyleme. Sonuç başarısızsa bunu açıkça söyle.
- Mesaj/dosya gönderme ve ekrana tıklama gibi araçlar kullanıcının onayını ister; çağırdığında sistem onay kartı gösterir, sen "gönderdim" deme.
- Sonuçtaki bilgiyi uydurma; araç ne döndürdüyse onu özetle."""


@dataclass
class AjanSonucu:
    metin: str = ""
    adimlar: List[Dict[str, Any]] = field(default_factory=list)  # ajan_izi
    son_arac: Optional[str] = None
    son_arac_argumanlari: Dict[str, Any] = field(default_factory=dict)
    son_arac_sonucu: Any = None
    veri: Dict[str, Any] = field(default_factory=dict)
    # Onay kartı gerekiyorsa:
    onay_gerekli: bool = False
    onay_mesaji: str = ""
    onay_komutu: str = ""
    saglayici: str = ""
    hata: Optional[str] = None       # sağlayıcıya hiç ulaşılamadıysa


# ---------------------------------------------------------------------------
# Araç şemaları — defterden otomatik
# ---------------------------------------------------------------------------
def arac_semalari(bulut: bool = False) -> List[dict]:
    """Defterdeki araçları sağlayıcıdan bağımsız şemaya çevirir.

    Sıra kayıt sırasıdır ve her çağrıda AYNIDIR (bulut önbelleği araç listesini
    önek olarak kullanır; sıra değişirse önbellek kaçar)."""
    semalar = []
    for arac in DEFTER.hepsi():
        if arac.ad in AJANA_KAPALI or (bulut and arac.ad in BULUTA_KAPALI):
            continue
        ozellikler = {"metin": {
            "type": "string",
            "description": arac.parametreler.get('metin')
                           or "Bu araca verilecek kısa Türkçe komut cümlesi",
        }}
        for ad, aciklama in arac.parametreler.items():
            if ad in ('metin', 'kanal'):
                continue
            ozellikler[ad] = {"type": "string", "description": aciklama}
        aciklama = arac.aciklama
        if arac.risk == RISK_ONAY:
            aciklama += " (Kullanıcı onayı gerekir.)"
        semalar.append({"ad": arac.ad, "aciklama": aciklama, "sema": {
            "type": "object", "properties": ozellikler, "required": ["metin"],
        }})
    return semalar


# ---------------------------------------------------------------------------
# Onay bekleyen doğrudan araçlar (DOGRUDAN_ONAYLI)
# ---------------------------------------------------------------------------
_BEKLEYEN: Dict[str, Tuple[str, str, dict, float]] = {}
_BEKLEME_SN = 120


def bekleyen_araci_yurut(komut: str, kanal: str = 'desktop'):
    """Onaylanan komut ajanın bekleyen doğrudan aracıysa onu çalıştırır.
    Dönüş: (True, mesaj) ya da eşleşme yoksa None. Tek kullanımlıktır."""
    kayit = _BEKLEYEN.get(kanal)
    if not kayit or kayit[0] != komut:
        return None
    _BEKLEYEN.pop(kanal, None)
    _komut, arac_ad, argumanlar, zaman = kayit
    if time.time() - zaman > _BEKLEME_SN:
        return True, "⏱️ Onay süresi dolmuş — işlem yapılmadı."
    arac = DEFTER.getir(arac_ad)
    if arac is None:
        return None
    try:
        sonuc = arac.calistir(**argumanlar)
    except Exception as e:
        return True, f"⚠️ {arac_ad} çalıştırılamadı: {e}"
    return True, sonuc.mesaj or "✅ Yapıldı."


# ---------------------------------------------------------------------------
# Ajan döngüsü
# ---------------------------------------------------------------------------
class Ajan:
    def __init__(self, saglayici, config: dict = None, db_cursor=None, db_conn=None,
                 kanal: str = 'desktop', yedek_saglayici=None):
        self.saglayici = saglayici
        self.yedek = yedek_saglayici
        self.config = config or {}
        self.db_cursor = db_cursor
        self.db_conn = db_conn
        self.kanal = kanal or 'desktop'
        try:
            self.max_adim = max(1, int(self.config.get('ajan_max_adim', VARSAYILAN_MAX_ADIM)))
        except (TypeError, ValueError):
            self.max_adim = VARSAYILAN_MAX_ADIM

    # -------------------------------------------------------------- giriş
    def calistir(self, kullanici: str, gecmis: List[dict] = None,
                 hafiza: List[str] = None) -> AjanSonucu:
        from features.ajan_saglayici import SaglayiciHatasi

        baglam = self._baglam(hafiza)
        gecmis = self._gecmisi_temizle(gecmis, kullanici)
        try:
            return self._dongu(self.saglayici, kullanici, gecmis, baglam)
        except SaglayiciHatasi as e:
            # Bulut düştüyse aynı turu yerel modelle bir kez dene. Kalıcı hatada
            # (geçersiz anahtar) da yerel dene ama sebebi kullanıcıya söyle.
            if self.yedek is not None:
                try:
                    sonuc = self._dongu(self.yedek, kullanici, gecmis, baglam)
                    sonuc.metin = f"_({e} — yerel modelle devam edildi)_\n\n{sonuc.metin}"
                    return sonuc
                except SaglayiciHatasi as e2:
                    return AjanSonucu(hata=str(e2), saglayici=self.yedek.etiket)
            return AjanSonucu(hata=str(e), saglayici=self.saglayici.etiket)

    @staticmethod
    def _baglam(hafiza: List[str] = None) -> str:
        # Değişken bağlam (saat, hafıza) sabit SİSTEM_TALIMATI'na yazılmaz
        # (bulut önbelleği). Sağlayıcı onu kendi uygun yerine koyar — kullanıcı
        # cümlesinin önüne DEĞİL (bkz. ajan_saglayici başlığındaki ölçüm).
        simdi = datetime.now().strftime('%d.%m.%Y %A %H:%M')
        satirlar = [f"Şu an: {simdi}."]
        if hafiza:
            satirlar.append("Kullanıcı hakkında bilinenler:\n" +
                            "\n".join(f"- {h}" for h in hafiza[:8]))
        return "\n".join(satirlar)

    @staticmethod
    def _gecmisi_temizle(gecmis, kullanici):
        temiz = []
        for m in (gecmis or [])[-8:]:
            rol = m.get('role')
            metin = (m.get('text') or m.get('content') or '').strip()
            if rol in ('user', 'assistant') and metin and isinstance(metin, str):
                temiz.append({'role': rol, 'text': metin[:1500]})
        # Masaüstü geçmişi bu turun cümlesini zaten içeriyor — iki kez gitmesin.
        if temiz and temiz[-1]['role'] == 'user' and temiz[-1]['text'] == kullanici.strip():
            temiz.pop()
        return temiz

    # -------------------------------------------------------------- döngü
    def _dongu(self, saglayici, kullanici: str, gecmis: List[dict],
               baglam: str = "") -> AjanSonucu:
        bulut = getattr(saglayici, 'ad', '') == 'bulut'
        araclar = arac_semalari(bulut=bulut)
        izinli = {a['ad'] for a in araclar}
        sonuc = AjanSonucu(saglayici=saglayici.etiket)
        duzeltildi = False

        saglayici.baslat(SISTEM_TALIMATI, gecmis, kullanici, baglam)
        for _tur in range(self.max_adim):
            adim = saglayici.uret(araclar)
            if not adim.cagrilar:
                calisan_var = any(a.get('durum') == 'ok' for a in sonuc.adimlar)
                iddia = None if calisan_var else eylem_iddiasi(adim.metin)
                if iddia and not duzeltildi:
                    # Ölçüm (15 Eki): "Tab+1 bas" → araç çağrılmadan "basıldı".
                    # Modele bir kez düzeltme şansı verilir.
                    duzeltildi = True
                    saglayici.kullanici_ekle(DUZELTME_NOTU.format(iddia=iddia))
                    continue
                sonuc.metin = adim.metin or self._ozet(sonuc)
                if iddia:
                    sonuc.metin += (f"\n\n⚠️ **Dikkat:** cevapta \"{iddia}\" deniyor ama "
                                    f"**hiçbir işlem çalıştırılmadı.** Gerçekten yapılmasını "
                                    f"istiyorsan komutu daha açık yazar mısın?")
                return sonuc

            geri_bildirim = []
            for cagri in adim.cagrilar:
                durum, metin = self._cagriyi_isle(cagri, izinli, sonuc)
                if durum == 'onay':
                    # Onay bekleyen işten SONRAKİ adımlar yürütülmez; model
                    # onay sonucunu bilmeden devam ederse "gönderdim" diyebilir.
                    sonuc.metin = self._ozet(sonuc, adim.metin)
                    return sonuc
                geri_bildirim.append((cagri, metin, durum != 'ok'))
            saglayici.sonuclari_ekle(geri_bildirim)

        # Adım tavanı: model hâlâ araç istiyor. Yapılanları dürüstçe raporla.
        sonuc.metin = self._ozet(sonuc) + (
            f"\n\n_(⏹️ {self.max_adim} adım sınırına ulaşıldı — kalan iş yapılmadı.)_")
        return sonuc

    def _cagriyi_isle(self, cagri, izinli, sonuc: AjanSonucu):
        """Tek araç çağrısı → ('ok'|'hata'|'yasak'|'onay', modele dönen metin)."""
        arac = DEFTER.getir(cagri.ad) if cagri.ad in izinli else None
        if arac is None:
            sonuc.adimlar.append({'arac': cagri.ad, 'metin': '', 'durum': 'bilinmeyen'})
            return 'hata', f"HATA: '{cagri.ad}' adında bir araç yok."

        girdi = {k: v for k, v in (cagri.girdi or {}).items()
                 if isinstance(k, str) and k not in ('db_cursor', 'db_conn', 'kanal', 'plan')}
        metin = str(girdi.get('metin') or '').strip()
        if not metin:
            sonuc.adimlar.append({'arac': arac.ad, 'metin': '', 'durum': 'eksik'})
            return 'hata', "HATA: `metin` alanı boş — kısa bir komut cümlesi ver."
        girdi['metin'] = metin

        seviye, guvenlik_mesaji = self._guvenlik(arac, metin)
        if seviye == 'FORBIDDEN':
            sonuc.adimlar.append({'arac': arac.ad, 'metin': metin, 'durum': 'yasak'})
            return 'yasak', f"YASAK: güvenlik katmanı bu işlemi engelledi. {guvenlik_mesaji}"
        if seviye == 'CONFIRM' or arac.risk == RISK_ONAY:
            sonuc.onay_gerekli = True
            sonuc.onay_komutu = metin
            sonuc.onay_mesaji = guvenlik_mesaji or (
                f"🛡️ **[AJAN — ONAY GEREKLİ]**\n• Araç: `{arac.ad}`\n• Komut: `{metin}`\n\n"
                f"Onaylıyor musunuz?")
            if arac.ad in DOGRUDAN_ONAYLI:
                _BEKLEYEN[self.kanal] = (metin, arac.ad, self._argumanlar(arac, girdi), time.time())
            sonuc.adimlar.append({'arac': arac.ad, 'metin': metin, 'durum': 'onay'})
            return 'onay', ''

        argumanlar = self._argumanlar(arac, girdi)
        self._pencereyi_hazirla(arac, metin)
        try:
            arac_sonucu = arac.calistir(**argumanlar)
        except Exception as e:
            print(f"[Ultron Ajan] {arac.ad} çalışırken hata: {e}")
            arac_sonucu = AracSonuc.hata(f"{arac.ad} çalıştırılamadı: {e}")

        sonuc.son_arac = arac.ad
        sonuc.son_arac_argumanlari = {k: v for k, v in argumanlar.items()
                                      if k not in ('db_cursor', 'db_conn')}
        sonuc.son_arac_sonucu = arac_sonucu
        if arac_sonucu.veri:
            sonuc.veri.update(arac_sonucu.veri)

        if not arac_sonucu.islendi:
            durum, cikti = 'hata', "Araç bu komutu anlamadı/üstlenmedi. Komutu daha açık yaz ya da başka araç dene."
        elif not arac_sonucu.basarili:
            durum, cikti = 'hata', f"BAŞARISIZ: {arac_sonucu.mesaj}"
        else:
            durum, cikti = 'ok', arac_sonucu.mesaj or "Tamamlandı."
            if arac_sonucu.hata_tipi:
                cikti = f"(hedefe ulaşılamadı: {arac_sonucu.hata_tipi}) {cikti}"
        sonuc.adimlar.append({'arac': arac.ad, 'metin': metin, 'durum': durum,
                              'cikti': (arac_sonucu.mesaj or '')[:MAKS_SONUC]})
        return durum, cikti[:MAKS_SONUC]

    # ------------------------------------------------------------ yardımcı
    def _argumanlar(self, arac, girdi: dict) -> dict:
        arg = dict(girdi)
        if 'dakika' in arg:
            try:
                arg['dakika'] = int(str(arg['dakika']).strip())
            except ValueError:
                arg.pop('dakika')
        if arac.db_ister:
            arg['db_cursor'] = self.db_cursor
            arg['db_conn'] = self.db_conn
        arg['kanal'] = self.kanal
        return arg

    def _guvenlik(self, arac, metin: str):
        """Tek kaynak: SecurityAnalyzerLayer. → ('', '') | ('CONFIRM', msj) | ('FORBIDDEN', msj)"""
        try:
            from core.context import UltronContext
            from core.layers.pipeline_layers import SecurityAnalyzerLayer
            alt = UltronContext(raw_input=metin, normalized_input=metin, kanal=self.kanal)
            if arac.intentler:
                alt.intent = arac.intentler[0]
            alt = SecurityAnalyzerLayer().process(alt)
        except Exception as e:
            # Güvenlik ölçülemediyse işi YAPMA, sor.
            print(f"[Ultron Ajan] Güvenlik kontrolü yapılamadı: {e}")
            return 'CONFIRM', ''
        if alt.security_level == 'FORBIDDEN':
            return 'FORBIDDEN', alt.security_message
        if alt.security_level in ('CONFIRM', 'DOUBLE_CONFIRM'):
            return 'CONFIRM', alt.security_message
        return '', ''

    @staticmethod
    def _pencereyi_hazirla(arac, metin):
        if arac.ad in ("klavye_tusu", "ekranda_tikla", "ekranda_sec", "ekrani_oku"):
            try:
                from core.world_state import uygun_pencereyi_odakla
                uygun_pencereyi_odakla(metin)
            except Exception as e:
                print(f"[Ultron Ajan] Pencere odağı hatası: {e}")

    @staticmethod
    def _ozet(sonuc: AjanSonucu, model_metni: str = "") -> str:
        """Model son sözü söyleyemediyse yapılanları ARAÇ ÇIKTISINDAN kur."""
        parcalar = [model_metni.strip()] if model_metni and model_metni.strip() else []
        for a in sonuc.adimlar:
            if a.get('durum') == 'ok' and a.get('cikti'):
                parcalar.append(a['cikti'])
            elif a.get('durum') in ('hata', 'yasak'):
                parcalar.append(f"⚠️ `{a['arac']}` başarısız: {a.get('cikti') or a['durum']}")
        return "\n\n".join(parcalar)


# Halüsinasyon freni — reflection'daki 1. tekil kalıplara ek olarak EDİLGEN
# bitmiş eylem ("basıldı", "gönderildi"): küçük model ölçümde bunu kullandı.
_EDILGEN_IDDIA = re.compile(
    r'\b(bas[ıi]ld[ıi]|a[çc][ıi]ld[ıi]|g[öo]nderildi|kapat[ıi]ld[ıi]|kaydedildi'
    r'|ayarland[ıi]|ba[şs]lat[ıi]ld[ıi]|eklendi|silindi|kuruldu|olu[şs]turuldu'
    r'|yaz[ıi]ld[ıi]|duraklat[ıi]ld[ıi]|ger[çc]ekle[şs]tirildi)\b',
    re.IGNORECASE)

DUZELTME_NOTU = ("Cevabında \"{iddia}\" dedin ama HİÇBİR araç çağırmadın, yani hiçbir şey "
                 "yapılmadı. İş isteniyorsa şimdi uygun aracı çağır; yapamıyorsan "
                 "yapamadığını açıkça söyle.")


def eylem_iddiasi(metin: str) -> Optional[str]:
    """Metin yapılmış bir eylem iddia ediyor mu? → iddia sözcüğü ya da None."""
    if not metin:
        return None
    from core.reflection import _EYLEM_IDDIASI, _MASUM_BAGLAM
    if _MASUM_BAGLAM.search(metin):
        return None
    m = _EYLEM_IDDIASI.search(metin) or _EDILGEN_IDDIA.search(metin)
    return m.group(0) if m else None


def iz_satiri(sonuc: AjanSonucu) -> str:
    """Kullanıcıya gösterilen kısa iz: hangi model, hangi araçlar.
    Sessiz ajan, yanlış aracın fark edilmeden çalışması demektir."""
    if not sonuc.adimlar:
        return ""
    simge = {'ok': '✓', 'hata': '✗', 'yasak': '⛔', 'onay': '⏸', 'bilinmeyen': '?', 'eksik': '?'}
    adimlar = " → ".join(f"{a['arac']}{simge.get(a['durum'], '')}" for a in sonuc.adimlar)
    return f"_(🤖 {sonuc.saglayici}: {adimlar})_"
