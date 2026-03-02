# engines_pro/pro_engine.py — Pro Mode orchestrator
# Top-level entry point for the Plan → Approve → Execute flow.
# Manages ExecutionContext persistence (in-memory, keyed by plan_id).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from core.config import PRO_MAX_ROWS, PRO_MAX_CONTENT_LENGTH, PRO_MAX_REPLAN_COUNT
from core.dataset_profiler import DatasetProfiler
from core.execution_context import ExecutionContext
from engines_pro.dag_schema import DAGPlan, NodeStatus
from engines_pro.dag_planner import DAGPlanner
from engines_pro.dag_executor import DAGExecutor
from models_api.model_router import router
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# IN-MEMORY EXECUTION STORE — persists plans + contexts between requests
# ═══════════════════════════════════════════════════════════════════════

_execution_store: Dict[str, Dict[str, Any]] = {}
"""
Maps plan_id → {
    "plan": DAGPlan,
    "context": ExecutionContext,
    "session_id": int,
    "user_id": int,
    "result": dict or None,
    "created_at": str,
}
"""


def _store_execution(plan_id: str, plan: DAGPlan, context: ExecutionContext,
                     session_id: int, user_id: int) -> None:
    _execution_store[plan_id] = {
        "plan": plan,
        "context": context,
        "session_id": session_id,
        "user_id": user_id,
        "result": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _get_execution(plan_id: str) -> Optional[Dict[str, Any]]:
    return _execution_store.get(plan_id)


def _cleanup_old_executions(max_entries: int = 50) -> None:
    """Remove oldest entries if store exceeds max."""
    if len(_execution_store) > max_entries:
        sorted_keys = sorted(
            _execution_store.keys(),
            key=lambda k: _execution_store[k]["created_at"],
        )
        for k in sorted_keys[: len(sorted_keys) - max_entries]:
            del _execution_store[k]


# ═══════════════════════════════════════════════════════════════════════
# PRO ENGINE
# ═══════════════════════════════════════════════════════════════════════

class ProEngine:
    """Top-level orchestrator for Pro Mode.

    Flow:
      1. detect_complexity()   — light model decides Normal vs Pro
      2. plan()                — heavy model generates DAG plan
      3. execute()             — DAG executor runs approved plan
      4. get_status()          — poll execution state
    """

    def __init__(self):
        self._planner = DAGPlanner()
        self._executor = DAGExecutor()
        self._profiler = DatasetProfiler()

    # ───────────────────────────────────────────────────────────────────
    # COMPLEXITY DETECTION
    # ───────────────────────────────────────────────────────────────────

    def detect_complexity(
        self,
        user_input: str,
        dataset_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Use light model to decide if a request needs Pro Mode.

        Returns:
            {"needs_pro": bool, "reason": str, "estimated_steps": int}
        """
        profile_summary = (
            f"Dataset: {dataset_profile.get('rows', '?')} rows × "
            f"{dataset_profile.get('columns', '?')} columns, "
            f"Columns: {', '.join(dataset_profile.get('column_names', [])[:15])}"
        )

        result = router.call_with_system(
            tier="light",
            system_prompt="""You are a complexity analyzer for a data science copilot.
Determine if a user request needs simple execution (Normal Mode) or multi-step planning (Pro Mode).

Pro Mode is needed when:
- Multiple dependent operations are required
- Conditional logic based on intermediate results
- Complex analysis pipelines (e.g., "prepare data for machine learning")
- Tasks requiring more than 2-3 steps

Normal Mode is fine for:
- Simple queries ("show first 10 rows", "plot histogram")
- Single operations ("add a column", "compute correlation")
- Direct questions about data

Reply with ONLY valid JSON:
{"needs_pro": true/false, "reason": "brief explanation", "estimated_steps": N}""",
            user_content=f"Dataset: {profile_summary}\n\nUser request: {user_input}",
            temperature=0.1,
            max_tokens=200,
        )

        if result:
            try:
                import json, re
                # Extract JSON
                m = re.search(r"\{.*\}", result, re.DOTALL)
                if m:
                    return json.loads(m.group())
            except Exception:
                pass

        # Default: not complex
        return {"needs_pro": False, "reason": "complexity detection failed", "estimated_steps": 1}

    # ───────────────────────────────────────────────────────────────────
    # DATASET SIZE CHECK
    # ───────────────────────────────────────────────────────────────────

    def check_dataset_size(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Check if dataset exceeds Pro Mode size limits.

        Returns:
            {
                "within_limits": bool,
                "rows": int,
                "max_rows": int,
                "warning": str or None,
                "requires_confirmation": bool,
            }
        """
        rows = len(df)
        within = rows <= PRO_MAX_ROWS

        warning = None
        if not within:
            warning = (
                f"Dataset has {rows:,} rows (limit: {PRO_MAX_ROWS:,}). "
                f"Pro Mode analysis may be slow. You can proceed with confirmation."
            )

        return {
            "within_limits": within,
            "rows": rows,
            "max_rows": PRO_MAX_ROWS,
            "warning": warning,
            "requires_confirmation": not within,
        }

    # ───────────────────────────────────────────────────────────────────
    # PLAN GENERATION
    # ───────────────────────────────────────────────────────────────────

    def plan(
        self,
        user_input: str,
        df: pd.DataFrame,
        file_path: str,
        session_id: int,
        user_id: int,
        previous_transforms: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a DAG plan for user approval.

        Returns plan dict for frontend display, or None on failure.
        """
        app_logger.info(f"[PRO] Planning for: {user_input[:100]}")

        # Profile dataset
        profile = self._profiler.profile(df)

        # Create execution context
        context = ExecutionContext(df=df, dataset_profile=profile, file_path=file_path)

        # Generate plan
        plan = self._planner.create_plan(
            user_goal=user_input,
            dataset_profile=profile,
            previous_transforms=previous_transforms,
        )

        if not plan:
            return None

        # Store for later execution
        _store_execution(plan.plan_id, plan, context, session_id, user_id)
        _cleanup_old_executions()

        # Return plan for frontend
        model_info = router.get_model_info("heavy")

        return {
            "plan_id": plan.plan_id,
            "plan": plan.to_dict(),
            "dataset_profile": profile,
            "model_used": model_info,
            "node_count": len(plan.nodes),
        }

    # ───────────────────────────────────────────────────────────────────
    # PLAN EXECUTION (after user approval)
    # ───────────────────────────────────────────────────────────────────

    def execute(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Execute an approved plan.

        Returns execution result dict or None if plan not found.
        """
        entry = _get_execution(plan_id)
        if not entry:
            app_logger.warning(f"[PRO] Plan '{plan_id}' not found in execution store")
            return None

        plan = entry["plan"]
        context = entry["context"]

        if plan.status not in ("planned", "replanned"):
            app_logger.warning(f"[PRO] Plan '{plan_id}' status is '{plan.status}', cannot execute")
            return {"error": f"Plan status is '{plan.status}', expected 'planned' or 'replanned'"}

        plan.status = "approved"
        app_logger.info(f"[PRO] Executing plan '{plan_id}' ({len(plan.nodes)} nodes)")

        # Execute DAG
        result = self._executor.execute(plan, context)

        # Handle re-planning
        if result["status"] == "replan_needed" and plan.replan_count < PRO_MAX_REPLAN_COUNT:
            app_logger.info(f"[PRO] Re-planning triggered: {result.get('replan_reason')}")
            remaining = [
                n.id for n in plan.nodes
                if plan.metadata.get(n.id, None) is None
                or plan.metadata[n.id].status in (NodeStatus.ABORTED, NodeStatus.PENDING)
            ]
            new_plan = self._planner.replan(
                original_plan=plan,
                execution_context_summary=context.to_model_context(),
                remaining_node_ids=remaining,
                reason=result.get("replan_reason", "Unknown"),
            )
            if new_plan:
                entry["plan"] = new_plan
                # Re-execute the new plan
                replan_result = self._executor.execute(new_plan, context)
                result = replan_result
                result["replanned"] = True

        # Generate final summary
        summary = self._executor.generate_final_summary(plan, context, result)
        result["summary"] = summary

        # Store result
        entry["result"] = result

        return result

    # ───────────────────────────────────────────────────────────────────
    # STATUS POLLING
    # ───────────────────────────────────────────────────────────────────

    def get_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get current execution state for a plan.

        Returns status dict or None if plan not found.
        """
        entry = _get_execution(plan_id)
        if not entry:
            return None

        plan = entry["plan"]
        result = entry["result"]

        return {
            "plan_id": plan.plan_id,
            "plan_status": plan.status,
            "version": plan.version,
            "replan_count": plan.replan_count,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type.value,
                    "description": n.description,
                    "status": (
                        plan.metadata[n.id].status.value
                        if n.id in plan.metadata
                        else "pending"
                    ),
                    "metadata": (
                        plan.metadata[n.id].to_dict()
                        if n.id in plan.metadata
                        else None
                    ),
                }
                for n in plan.nodes
            ],
            "result": result,
        }

    # ───────────────────────────────────────────────────────────────────
    # PROFILE ENDPOINT
    # ───────────────────────────────────────────────────────────────────

    def get_profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate and return dataset profile (used by both modes)."""
        return self._profiler.profile(df)


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════

pro_engine = ProEngine()
