"""
AIP — Interaction Decision Engine

Her aksiyonda şu soruyu sorar: "Bu işi en güvenilir şekilde nasıl yapabilirim?"

- Stratejiler kayıt sırasına göre denenir (Level 1 → 2 → 3 → 4).
- Daha önce başarılı olmuş seviye capability cache'ten okunur ve İLK o denenir.
- Başarılı görünen ama DOĞRULAMASI BAŞARISIZ olan sonuç, başarısızlık sayılır
  ve bir alt seviyeye geçilir (Smart Fallback + Verification sinerjisi).
"""

import json
import os
from typing import Callable, Dict, List, Optional

from core.interaction.base import InteractionResult, InteractionStrategy

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAPABILITY_CACHE_PATH = os.path.join(_ROOT, 'capability_cache.json')


class InteractionDecisionEngine:
    def __init__(self, cache_path: str = CAPABILITY_CACHE_PATH):
        self._actions: Dict[str, List[InteractionStrategy]] = {}
        self._cache_path = cache_path
        self._cache = self._load_cache()

    # ------------------------------------------------------------------
    # Capability Cache — hangi aksiyonda hangi seviye işe yaradı
    # ------------------------------------------------------------------
    def _load_cache(self) -> dict:
        try:
            with open(self._cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cache(self):
        try:
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AIP Cache] Yazılamadı: {e}")

    # ------------------------------------------------------------------
    # Kayıt & Çalıştırma
    # ------------------------------------------------------------------
    def register(self, action_name: str, strategies: List[InteractionStrategy]):
        """Bir aksiyonu, öncelik sıralı strateji zinciriyle kaydeder."""
        self._actions[action_name] = list(strategies)

    def run_with(self, action_name: str, strategies: List[InteractionStrategy],
                 verifier: Optional[Callable[..., Optional[bool]]] = None,
                 **kwargs) -> InteractionResult:
        """
        Ön kayıt gerektirmeden geçici strateji zinciriyle çalıştırır.
        Capability cache yine action_name üzerinden kullanılır/öğrenilir —
        böylece sistemin her köşesi (uygulama açma, müzik, ileride e-posta UI'ı)
        aynı öğrenen fallback mekanizmasından faydalanabilir.
        """
        self._actions[action_name] = list(strategies)
        return self.run(action_name, verifier=verifier, **kwargs)

    def run(self, action_name: str,
            verifier: Optional[Callable[..., Optional[bool]]] = None,
            **kwargs) -> InteractionResult:
        """
        Aksiyonu çalıştırır. verifier verilirse başarılı denemeden sonra çağrılır;
        False dönerse bir alt stratejiye geçilir, True → verified=True,
        None → doğrulama yapılamadı (sonuç yine başarılı kabul edilir).
        """
        strategies = self._actions.get(action_name)
        if not strategies:
            return InteractionResult(False, "none", f"Kayıtlı aksiyon yok: {action_name}")

        # Cache'teki son başarılı seviye öne alınır, kalan sıra korunur
        ordered = list(strategies)
        last_level = self._cache.get(action_name, {}).get('last_success_level')
        if last_level:
            hits = [s for s in ordered if s.level == last_level]
            rest = [s for s in ordered if s.level != last_level]
            ordered = hits + rest

        attempts = []
        for strat in ordered:
            try:
                if not strat.available():
                    attempts.append(f"{strat.level}/{strat.name}: kullanılamıyor")
                    continue
                res = strat.execute(**kwargs)
            except Exception as e:
                attempts.append(f"{strat.level}/{strat.name}: hata ({e})")
                continue

            if not res.success:
                attempts.append(f"{strat.level}/{strat.name}: {res.message or 'başarısız'}")
                continue

            # Doğrulama
            if verifier is not None:
                try:
                    res.verified = verifier(**kwargs)
                except Exception as e:
                    print(f"[AIP Verify] Doğrulama hatası: {e}")
                    res.verified = None
                if res.verified is False:
                    attempts.append(f"{strat.level}/{strat.name}: yürüdü ama DOĞRULANAMADI")
                    continue  # bir alt seviyeye geç

            # Başarı → cache'e öğret
            self._cache[action_name] = {'last_success_level': strat.level}
            self._save_cache()
            res.detail['attempts'] = attempts
            return res

        return InteractionResult(
            False, "none",
            "Hiçbir etkileşim seviyesi görevi tamamlayamadı.",
            detail={'attempts': attempts}
        )
