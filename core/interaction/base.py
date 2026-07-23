"""AIP — Ortak veri yapıları."""

from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any


@dataclass
class InteractionResult:
    """Bir etkileşim denemesinin sonucu."""
    success: bool
    level: str              # "native" | "uia" | "vision" | "input" | "none"
    message: str = ""
    verified: Optional[bool] = None   # None = doğrulama yapılamadı / uygulanamaz
    detail: Dict[str, Any] = field(default_factory=dict)


class InteractionStrategy:
    """
    Tek bir etkileşim yönteminin sözleşmesi.

    Alt sınıflar `level`, `name` tanımlar ve `execute(**kwargs)` uygular.
    execute başarısızlıkta InteractionResult(success=False, ...) döner veya
    exception fırlatabilir — Decision Engine ikisini de 'bir alt seviyeye geç'
    olarak yorumlar.
    """
    level: str = "none"
    name: str = "unnamed"

    def available(self) -> bool:
        """Bu strateji bu makinede kullanılabilir mi (bağımlılık kontrolü)."""
        return True

    def execute(self, **kwargs) -> InteractionResult:
        raise NotImplementedError
