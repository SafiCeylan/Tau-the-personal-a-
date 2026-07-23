"""
ULTRON CORE ENGINE v1.0 — Self-Reflection & Auto-Correction Engine Layer
Diagnoses failures, repairs arguments/paths, and executes self-retries.
"""

import os
from typing import Tuple
from core.context import UltronContext
from features.file_reader import dosya_oku_ve_analiz_et

class SelfReflectionEngine:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def reflect_and_retry(self, ctx: UltronContext) -> Tuple[bool, str]:
        """
        Diagnoses failure, auto-corrects parameters, and retries.
        """
        raw_msg = ctx.normalized_input
        err = ctx.error_reason or ctx.execution_result or ""

        # 1. Self-Reflection Scenario: File Not Found Correction
        if "bulunamadı" in err.lower() or "file not found" in err.lower():
            target_path = ctx.entities.get("file_path") or raw_msg.replace("oku:", "").replace("dosya oku:", "").strip()
            
            # Auto-correction attempt 1: Try checking root workspace directory
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            alt_path = os.path.join(root_dir, target_path)
            
            if os.path.exists(alt_path):
                success, content = dosya_oku_ve_analiz_et(alt_path)
                if success:
                    log_msg = f"🔄 **ÖZ-YANSIMA (SELF-REFLECTION) BAŞARILI:** Dosya yolu `{target_path}` -> `{alt_path}` olarak kendi kendine düzeltildi.\n\n{content}"
                    return True, log_msg

        # 2. Self-Reflection Scenario: Generic Error Retry
        return False, f"⚠️ Öz-yansıma: {err}"
