"""
ULTRON CORE ENGINE v1.0 — Central Pipeline Orchestration Engine
Executes all 14 layers in strict architecture order with zero hallucination & interactive security.
"""

from core.context import UltronContext
from core.layers.pipeline_layers import (
    InputCaptureLayer, NormalizationLayer, IntentAnalyzerLayer,
    EntityExtractionLayer, MemoryContextLayer, SecurityAnalyzerLayer,
    TaskPlannerLayer, ToolSelectionEngineLayer, PromptGeneratorLayer,
    LLMCoreLayer, ActionPlannerLayer, ExecutionEngineLayer,
    ResultCheckerLayer, ResponseBuilderLayer
)
from core.layers.routine_engine import RoutineEngine
from core.layers.self_reflection import SelfReflectionEngine

class UltronCoreEngine:
    def __init__(self, db_manager=None, cursor=None, conn=None):
        self.db = db_manager
        self.cursor = cursor
        self.conn = conn

        # Initialize 14 layers
        self.l1_capture = InputCaptureLayer()
        self.l2_norm = NormalizationLayer()
        self.l3_intent = IntentAnalyzerLayer()
        self.l4_entity = EntityExtractionLayer()
        self.l5_memory = MemoryContextLayer(db_manager)
        self.l6_security = SecurityAnalyzerLayer()
        self.l7_planner = TaskPlannerLayer()
        self.l8_tools = ToolSelectionEngineLayer()
        self.l9_prompt = PromptGeneratorLayer()
        self.l10_llm = LLMCoreLayer()
        self.l11_action = ActionPlannerLayer()
        self.l12_exec = ExecutionEngineLayer()
        self.l13_checker = ResultCheckerLayer()
        self.l14_response = ResponseBuilderLayer()

        # Autonomous Engines
        self.routine_engine = RoutineEngine(db_manager)
        self.self_reflection = SelfReflectionEngine()

    def process(self, raw_input: str, input_type: str = "text", recent_context: list = None) -> UltronContext:
        """
        Executes the 14-layer pipeline sequentially for every user prompt.

        SQLite bağlantıları thread'ler arasında paylaşılamadığı için her çağrıda
        (worker thread'de çalışsa bile güvenli olacak şekilde) kendi bağlantısını açar.
        """
        own_conn = None
        cursor, conn = self.cursor, self.conn
        if self.db is not None:
            try:
                own_conn = self.db.get_connection()
                conn = own_conn
                cursor = conn.cursor()
            except Exception as e:
                print(f"[Ultron Engine] DB bağlantısı açılamadı, mevcut bağlantı kullanılacak: {e}")
                own_conn = None

        try:
            return self._run_pipeline(raw_input, input_type, recent_context, cursor, conn)
        finally:
            if own_conn is not None:
                try:
                    own_conn.close()
                except Exception:
                    pass

    def _run_pipeline(self, raw_input, input_type, recent_context, cursor, conn) -> UltronContext:
        # 1. Input Capture
        ctx = self.l1_capture.process(raw_input, input_type)
        if recent_context:
            ctx.recent_context = recent_context

        # 2. Input Normalization (Fixes typos: chorome -> chrome)
        ctx = self.l2_norm.process(ctx)

        # 3. Intent Analyzer
        ctx = self.l3_intent.process(ctx)

        # 4. Entity Extraction
        ctx = self.l4_entity.process(ctx)

        # 5. Memory Context
        ctx = self.l5_memory.process(ctx)

        # 6. Security Analyzer (0-100+ Risk Rating)
        ctx = self.l6_security.process(ctx)

        # SECURITY INTERCEPT: If confirmation is needed or forbidden, STOP IMMEDIATELY!
        if ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
            ctx.execution_success = False
            ctx.execution_result = ctx.security_message
            return self.l14_response.process(ctx)

        # Routine Engine Check (Autonomous Workflows)
        is_routine, routine_output = self.routine_engine.check_and_execute_routine(ctx)
        if is_routine:
            ctx.execution_success = True
            ctx.execution_result = routine_output
            ctx.verification_passed = True
            return self.l14_response.process(ctx)

        # 7. Task Planner
        ctx = self.l7_planner.process(ctx)

        # 8. Tool Selection Engine
        ctx = self.l8_tools.process(ctx)

        # 12. Execution Engine (Fetches Web Data / System Actions FIRST)
        ctx = self.l12_exec.process(ctx, db_cursor=cursor, db_conn=conn)

        # Self-Reflection Check (Auto-Correction & Self-Retry on failure)
        if not ctx.execution_success and ctx.intent == "FILE_OPERATION":
            reflected, corrected_output = self.self_reflection.reflect_and_retry(ctx)
            if reflected:
                ctx.execution_success = True
                ctx.execution_result = corrected_output
                ctx.verification_passed = True

        # 9. Prompt Generator (Builds enriched prompt with live web data and multi-turn chat history)
        ctx = self.l9_prompt.process(ctx)

        # 10. LLM Core
        ctx = self.l10_llm.process(ctx)

        # 11. Action Planner
        ctx = self.l11_action.process(ctx)

        # 13. Result Checker
        ctx = self.l13_checker.process(ctx)

        # 14. Response Builder
        ctx = self.l14_response.process(ctx)

        return ctx
