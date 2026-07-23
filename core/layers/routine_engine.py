"""
ULTRON CORE ENGINE v1.0 — Learning & Routine Engine Layer
Executes autonomous multi-step workflows, dynamic user-defined modes, and habit patterns.
"""

import json
import re
from typing import Dict, Any, List, Tuple
from core.context import UltronContext
from features.actions.system_control import sistem_komutu_algila, sarki_otomatik_baslat
from features.web_search import canli_web_ara

class RoutineEngine:
    def __init__(self, db_manager=None):
        self.db = db_manager
        # Anahtarlar gövde (stem) halinde: "dinlenme mod" hem "dinlenme mod"
        # hem "dinlenme modu" hem "dinlenme modunu aç" ile eşleşir
        self.built_in_routines = {
            "çalışma mod": self._routine_calisma_modu,
            "kodlama mod": self._routine_calisma_modu,
            "work mode": self._routine_calisma_modu,
            "oyun mod": self._routine_oyun_modu,
            "game mode": self._routine_oyun_modu,
            "dinlenme mod": self._routine_dinlenme_modu,
            "müzik mod": self._routine_dinlenme_modu,
        }

    def check_and_execute_routine(self, ctx: UltronContext) -> Tuple[bool, str]:
        msg_lower = ctx.normalized_input.lower().strip()

        # 1. Check Built-in Routines First
        for routine_name, routine_func in self.built_in_routines.items():
            if routine_name in msg_lower:
                results = routine_func(ctx)
                output = f"⚡ **{routine_name.upper()} OTONOM OLARAK BAŞLATILDI**\n\n" + "\n".join(results)
                return True, output

        # 2. Check Custom User-Defined Routines from Database
        if self.db:
            try:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT name, trigger_keyword, actions_json FROM custom_routines")
                rows = cursor.fetchall()

                for row in rows:
                    name = row['name']
                    trigger = row['trigger_keyword'].lower().strip()
                    actions_json_raw = row['actions_json']

                    # Güvenlik: kısa/genel tetikleyiciler ("aç" gibi) her mesajı ele
                    # geçirmesin — tam eşleşme veya kelime sınırlı eşleşme (min 4 karakter)
                    if msg_lower == trigger or (
                        len(trigger) >= 4 and re.search(rf'\b{re.escape(trigger)}\b', msg_lower)
                    ):
                        try:
                            actions = json.loads(actions_json_raw)
                        except Exception:
                            actions = [actions_json_raw]

                        results = []
                        for i, action_cmd in enumerate(actions, 1):
                            # Execute atomic action step
                            is_action, resp = sistem_komutu_algila(action_cmd)
                            if is_action:
                                results.append(f"{i}. ⚙️ **{action_cmd.title()}**: {resp}")
                            else:
                                results.append(f"{i}. ⚙️ **{action_cmd.title()}**: Çalıştırıldı.")

                        output = f"⚡ **{name.upper()} MODU OTONOM BAŞLATILDI**\n\n" + "\n".join(results)
                        return True, output
            except Exception as e:
                print(f"[Ultron RoutineEngine Error]: {e}")

        return False, ""

    def _routine_calisma_modu(self, ctx: UltronContext) -> List[str]:
        results = []
        _, r1 = sistem_komutu_algila("sesi %40 yap")
        results.append(f"1. 🔊 {r1}")

        _, r2 = sistem_komutu_algila("chrome aç")
        results.append(f"2. {r2}")

        _, r3 = sistem_komutu_algila("sistem durumunu göster")
        results.append(f"3. {r3}")

        return results

    def _routine_oyun_modu(self, ctx: UltronContext) -> List[str]:
        results = []
        _, r1 = sistem_komutu_algila("sesi %70 yap")
        results.append(f"1. 🔊 {r1}")

        _, r2 = sistem_komutu_algila("sistem durumu")
        results.append(f"2. {r2}")

        return results

    def _routine_dinlenme_modu(self, ctx: UltronContext) -> List[str]:
        results = []
        _, r1 = sistem_komutu_algila("sesi %35 yap")
        results.append(f"1. 🔊 {r1}")

        _, r2 = sarki_otomatik_baslat("Relaxing Chill Beats")
        results.append(f"2. {r2}")

        return results
