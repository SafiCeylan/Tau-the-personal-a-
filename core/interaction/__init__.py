"""
ULTRON Interaction Engine — Adaptive Interaction Pipeline (AIP)

Felsefe: ULTRON hiçbir zaman doğrudan fareyi/klavyeyi hareket ettirmeyi tercih etmez.
Her görevi önce en güvenilir, en hızlı ve en doğrulanabilir yöntemle gerçekleştirmeye
çalışır; gerekirse katmanlar arasında otomatik geçiş yapar.

Katmanlar (öncelik sırasıyla):
    Level 1 — Native API      (URI şemaları, shell:AppsFolder, pycaw...)
    Level 2 — UI Automation   (pywinauto/UIA: elementi bul, Invoke et — fare yok)
    Level 3 — Vision Engine   (Windows OCR: metni ekranda gör, koordinatına tıkla)
    Level 4 — Input Emulation (son çare: odak korumalı klavye/fare)

Karar merkezi: InteractionDecisionEngine — stratejileri sırayla dener,
başarılı sonucu doğrular, hangi seviyenin işe yaradığını capability cache'e yazar.
"""

from core.interaction.base import InteractionResult, InteractionStrategy
from core.interaction.decision_engine import InteractionDecisionEngine

__all__ = ["InteractionResult", "InteractionStrategy", "InteractionDecisionEngine",
           "OcrClickStrategy"]


def __getattr__(ad):
    """OcrClickStrategy tembel yüklenir — winsdk/mss import'u paket açılışını
    yavaşlatmasın, kurulu değilse de paket import'u patlamasın."""
    if ad == "OcrClickStrategy":
        from core.interaction.level3_ocr import OcrClickStrategy
        return OcrClickStrategy
    raise AttributeError(ad)
