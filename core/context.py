"""
ULTRON CORE ENGINE v1.0 — Shared Context & Pipeline Data Structure
Holds state as the prompt travels through all 14 layers.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class UltronContext:
    # 1. Input Capture
    raw_input: str
    input_type: str = "text"  # text, voice, file, image
    
    # 2. Input Normalization
    normalized_input: str = ""
    
    # 3. Intent Analyzer
    intent: str = "UNKNOWN"
    confidence: float = 0.0
    intent_source: str = "regex"  # "regex" | "llm" — gözlemlenebilirlik için

    # 4. Entity Extraction
    entities: Dict[str, Any] = field(default_factory=dict)
    # LLM niyet çözücünün çıkardığı kanonik parametreler (EntityExtraction bunları
    # ezmez; execution katmanı tercih eder). Örn: {"song_title": "motivasyon"}
    llm_entities: Dict[str, Any] = field(default_factory=dict)
    
    # 5. Memory Context
    user_memories: List[str] = field(default_factory=list)
    recent_context: List[Dict[str, str]] = field(default_factory=list)
    
    # 6. Security Analyzer
    security_score: int = 0  # 0-100+
    security_level: str = "SAFE"  # SAFE (0-20), INFO (20-60), CONFIRM (60-80), DOUBLE_CONFIRM (80-100), FORBIDDEN (100+)
    security_message: str = ""
    
    # 7. Task Planner
    subtasks: List[str] = field(default_factory=list)
    
    # 8. Tool Selection Engine
    selected_tools: List[str] = field(default_factory=list)
    
    # 9. Prompt Generator
    enriched_prompt: str = ""
    
    # 10. LLM Core
    llm_response: str = ""
    # LLM gerçekten engine içinde çağrıldı mı? (False ise llm_response ham prompt'tur
    # ve çağıran UI streaming için kendi LLM worker'ını çalıştırmalıdır.)
    llm_generated: bool = False
    
    # 11. Action Planner
    action_plan: List[Dict[str, Any]] = field(default_factory=list)
    
    # 12. Execution Engine
    execution_success: bool = False
    execution_result: Optional[str] = None
    
    # 13. Result Checker
    verification_passed: bool = True
    error_reason: Optional[str] = None
    
    # 14. Response Builder
    final_output: str = ""
    ui_state: str = "idle"
