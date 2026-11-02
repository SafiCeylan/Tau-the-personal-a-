# -*- coding: utf-8 -*-
"""
🤖 AJAN SAĞLAYICILARI — araç çağırabilen dil modelleri (yerel Ollama + Claude).

Ajan döngüsü (core/ajan.py) sağlayıcıyı TANIMAZ; yalnızca bu sözleşmeyi bilir:

    s = Saglayici(config)
    s.baslat(sistem, gecmis, kullanici_mesaji, baglam)   # konuşmayı kur
    adim = s.uret(araclar)                       # → Adim(metin, cagrilar, ...)
    s.sonuclari_ekle([(cagri, sonuc_metni, hata_mi), ...])
    adim = s.uret(araclar)                       # ... araç çağrısı bitene kadar
    s.kullanici_ekle(metin)                      # düzeltme notu (halüsinasyon freni)

`baglam` (saat, kullanıcı hafızası) kullanıcının SÖZÜ DEĞİLDİR. Ölçüm (15 Eki):
kullanıcı mesajının başına "[Bağlam — şu an …]" eklenince 4B yerel model cümleyi
komut olarak görmeyi bıraktı ("alt+tab bas" → araçsız cevap, aynı cümle öneksiz
→ klavye_tusu). Yerelde bağlam SİSTEM mesajına, bulutta sistem talimatı önbellekte
kalsın diye kullanıcı cümlesinin ARKASINA açıkça etiketlenmiş not olarak gider.

Her sağlayıcı kendi mesaj biçimini KENDİSİ tutar. Sebep: Claude'un cevabındaki
`thinking` blokları bir sonraki istekte DEĞİŞTİRİLMEDEN geri gönderilmeli
(Opus 5.5'te düşünce blokları konuşmaya bağlıdır); ortak bir ara biçime
çevirip geri kurmak bu blokları bozar. Konuşma YALNIZCA SONA EKLENİR.

`araclar` sağlayıcıdan bağımsız biçimdedir: [{"ad", "aciklama", "sema"}],
`sema` bir JSON Schema nesnesidir.
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class SaglayiciHatasi(Exception):
    """Sağlayıcıya ulaşılamadı / istek reddedildi. `gecici` ise yedeğe düşülebilir."""

    def __init__(self, mesaj: str, gecici: bool = True):
        super().__init__(mesaj)
        self.gecici = gecici


@dataclass
class Cagri:
    id: str
    ad: str
    girdi: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Adim:
    metin: str = ""
    cagrilar: List[Cagri] = field(default_factory=list)
    reddedildi: bool = False          # Claude güvenlik sınıflandırıcısı reddetti


# ===========================================================================
# YEREL — Ollama /api/chat (tools)
# ===========================================================================
class OllamaSaglayici:
    ad = "yerel"

    def __init__(self, config: dict):
        self.config = config or {}
        self.url = (self.config.get('ollama_url') or 'http://127.0.0.1:11434').rstrip('/')
        self.model = self.config.get('ollama_model') or 'qwen3:4b-instruct'
        self.mesajlar: List[dict] = []

    @property
    def etiket(self) -> str:
        return f"yerel · {self.model}"

    def baslat(self, sistem: str, gecmis: List[dict], kullanici: str, baglam: str = ""):
        self.mesajlar = [{"role": "system",
                          "content": f"{sistem}\n\n{baglam}" if baglam else sistem}]
        for m in gecmis:
            self.mesajlar.append({"role": m["role"], "content": m["text"]})
        self.mesajlar.append({"role": "user", "content": kullanici})

    def uret(self, araclar: List[dict]) -> Adim:
        if requests is None:
            raise SaglayiciHatasi("requests kurulu değil", gecici=False)
        from features.ollama import dusunme_alani
        govde = {
            "model": self.model,
            "messages": self.mesajlar,
            "tools": [{"type": "function",
                       "function": {"name": a["ad"], "description": a["aciklama"],
                                    "parameters": a["sema"]}} for a in araclar],
            "stream": False,
            "keep_alive": self.config.get('ollama_keep_alive', '30m'),
            # 38 araç şeması ~4k token; varsayılan bağlam penceresi taşar ve
            # Ollama sessizce BAŞTAN keser (sistem talimatı kaybolur).
            "options": {"num_ctx": int(self.config.get('ajan_num_ctx', 8192)),
                        "temperature": 0.2},
        }
        govde.update(dusunme_alani(self.model, self.config.get('ollama_dusunme')))
        try:
            r = requests.post(f"{self.url}/api/chat", json=govde,
                              timeout=float(self.config.get('ajan_zaman_asimi', 90)))
        except requests.RequestException as e:
            raise SaglayiciHatasi(f"Ollama'ya ulaşılamadı ({type(e).__name__})")
        if r.status_code != 200:
            raise SaglayiciHatasi(f"Ollama hatası {r.status_code}: {r.text[:200]}",
                                  gecici=r.status_code >= 500)
        mesaj = (r.json() or {}).get("message") or {}
        self.mesajlar.append(mesaj)

        cagrilar = []
        for tc in mesaj.get("tool_calls") or []:
            fn = tc.get("function") or {}
            girdi = fn.get("arguments") or {}
            if isinstance(girdi, str):
                try:
                    girdi = json.loads(girdi)
                except ValueError:
                    girdi = {"metin": girdi}
            cagrilar.append(Cagri(id=tc.get("id") or uuid.uuid4().hex[:8],
                                  ad=fn.get("name", ""), girdi=girdi if isinstance(girdi, dict) else {}))
        return Adim(metin=(mesaj.get("content") or "").strip(), cagrilar=cagrilar)

    def sonuclari_ekle(self, sonuclar):
        for cagri, metin, _hata in sonuclar:
            self.mesajlar.append({"role": "tool", "content": metin, "tool_name": cagri.ad})

    def kullanici_ekle(self, metin: str):
        self.mesajlar.append({"role": "user", "content": metin})


# ===========================================================================
# BULUT — Claude (resmî anthropic SDK)
# ===========================================================================
VARSAYILAN_CLAUDE_MODELI = "claude-opus-5-5"
# Asistan turu gecikmeye duyarlı: "low" düşünmeyi kısa tutar. Ayardan
# (claude_effort) değiştirilebilir — medium/high daha derin ama daha yavaş.
VARSAYILAN_CLAUDE_EFORU = "low"


def claude_kullanilabilir_mi(config: dict) -> bool:
    """SDK kurulu ve bir kimlik bilgisi var mı? (ağ kontrolü YAPMAZ)"""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    import os
    return bool((config or {}).get('claude_api_key') or os.environ.get('ANTHROPIC_API_KEY'))


class ClaudeSaglayici:
    ad = "bulut"

    def __init__(self, config: dict, istemci=None):
        self.config = config or {}
        self.model = self.config.get('claude_model') or VARSAYILAN_CLAUDE_MODELI
        self.efor = self.config.get('claude_effort') or VARSAYILAN_CLAUDE_EFORU
        self._istemci = istemci
        self.sistem = ""
        self.mesajlar: List[dict] = []

    @property
    def etiket(self) -> str:
        return f"bulut · {self.model}"

    def _istemci_al(self):
        if self._istemci is None:
            import anthropic
            self._istemci = anthropic.Anthropic(
                api_key=self.config.get('claude_api_key') or None,  # None → ortam değişkeni
                timeout=float(self.config.get('ajan_zaman_asimi', 90)),
                max_retries=1,
            )
        return self._istemci

    def baslat(self, sistem: str, gecmis: List[dict], kullanici: str, baglam: str = ""):
        self.sistem = sistem
        self.mesajlar = []
        for m in gecmis:
            # İlk mesaj user olmalı; baştaki asistan satırları atlanır.
            if not self.mesajlar and m["role"] != "user":
                continue
            self.mesajlar.append({"role": m["role"], "content": m["text"]})
        if baglam:
            kullanici = (f"{kullanici}\n\n<sistem_notu>(kullanıcının sözü değil)\n"
                         f"{baglam}\n</sistem_notu>")
        self.mesajlar.append({"role": "user", "content": kullanici})

    def uret(self, araclar: List[dict]) -> Adim:
        import anthropic
        try:
            yanit = self._istemci_al().beta.messages.create(
                model=self.model,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                output_config={"effort": self.efor},
                # Sistem talimatı ve araç listesi her turda AYNI → önbellek.
                # Değişken bilgi (saat, hafıza) kullanıcı mesajında durur.
                system=[{"type": "text", "text": self.sistem,
                         "cache_control": {"type": "ephemeral"}}],
                tools=[{"name": a["ad"], "description": a["aciklama"],
                        "input_schema": a["sema"]} for a in araclar],
                messages=self.mesajlar,
                # Güvenlik sınıflandırıcısı yanlışlıkla reddederse istek
                # sunucu tarafında önerilen modelle yeniden denenir.
                extra_body={"fallbacks": "default"},
            )
        except anthropic.AuthenticationError:
            raise SaglayiciHatasi("Claude API anahtarı geçersiz", gecici=False)
        except anthropic.PermissionDeniedError:
            raise SaglayiciHatasi("Claude API anahtarının bu modele yetkisi yok", gecici=False)
        except anthropic.BadRequestError as e:
            raise SaglayiciHatasi(f"Claude isteği reddetti: {e.message}", gecici=False)
        except anthropic.RateLimitError:
            raise SaglayiciHatasi("Claude kullanım sınırına takıldı")
        except anthropic.APIStatusError as e:
            raise SaglayiciHatasi(f"Claude hatası {e.status_code}", gecici=e.status_code >= 500)
        except anthropic.APIConnectionError:
            raise SaglayiciHatasi("Claude'a ulaşılamadı (internet?)")

        if yanit.stop_reason == "refusal":
            return Adim(metin="Bu isteği bulut modeli güvenlik gerekçesiyle yanıtlamadı.",
                        reddedildi=True)

        # İçerik OLDUĞU GİBİ geri eklenir (thinking blokları dahil).
        self.mesajlar.append({"role": "assistant", "content": yanit.content})
        metin = "\n".join(b.text for b in yanit.content if b.type == "text").strip()
        cagrilar = [Cagri(id=b.id, ad=b.name, girdi=dict(b.input or {}))
                    for b in yanit.content if b.type == "tool_use"]
        return Adim(metin=metin, cagrilar=cagrilar)

    def sonuclari_ekle(self, sonuclar):
        # Paralel çağrıların TÜM sonuçları TEK user mesajında döner.
        self.mesajlar.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cagri.id, "content": metin,
             "is_error": bool(hata)}
            for cagri, metin, hata in sonuclar
        ]})

    def kullanici_ekle(self, metin: str):
        self.mesajlar.append({"role": "user", "content": metin})


def saglayici_sec(config: dict, internet_var: Optional[bool] = None):
    """
    Ayara göre (birincil, yedek) sağlayıcı döner; ajan kapalıysa (None, None).

        ajan_modu = "kapali" → ajan yok (eski akış)
        ajan_modu = "yerel"  → yalnız Ollama
        ajan_modu = "hibrit" → Claude (anahtar + SDK + internet varsa), yedek Ollama
    """
    mod = (config or {}).get('ajan_modu', 'kapali')
    if mod == 'yerel':
        return OllamaSaglayici(config), None
    if mod == 'hibrit':
        if internet_var is None:
            try:
                from core.world_state import internet_var_mi
                internet_var = internet_var_mi()
            except Exception:
                internet_var = True
        if internet_var and claude_kullanilabilir_mi(config):
            return ClaudeSaglayici(config), OllamaSaglayici(config)
        return OllamaSaglayici(config), None
    return None, None
