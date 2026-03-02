# engines_pro/dag_planner.py — DAG plan generation via heavy reasoning model
# Sends DatasetProfile + user goal to heavy model and parses structured DAG JSON.
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.config import PRO_MAX_DAG_NODES
from engines_pro.dag_schema import DAGPlan, DAGNode, NodeType, OutputType
from engines_pro.validator import validate_plan
from models_api.model_router import router
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# DAG PLANNER
# ═══════════════════════════════════════════════════════════════════════

class DAGPlanner:
    """Generate structured DAG plans using the heavy reasoning model.

    The planner receives:
      - The user's goal
      - Full DatasetProfile JSON (column profiles, correlations, warnings)
      - Current schema summary
      - Previous transformation history (if any)

    And outputs a validated DAGPlan.
    """

    # ───────────────────────────────────────────────────────────────────
    # PLAN CREATION
    # ───────────────────────────────────────────────────────────────────

    def create_plan(
        self,
        user_goal: str,
        dataset_profile: Dict[str, Any],
        previous_transforms: List[str] = None,
    ) -> Optional[DAGPlan]:
        """Generate a DAG plan for the user's goal.

        Returns a validated DAGPlan or None if generation fails.
        """
        system_prompt = self._build_planner_prompt()
        user_content = self._build_user_content(user_goal, dataset_profile, previous_transforms)

        app_logger.info(f"[PLANNER] Generating DAG plan for: {user_goal[:100]}")

        raw = router.call(
            tier="heavy",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=8000,
            retries=2,
        )

        if not raw:
            app_logger.error("[PLANNER] Heavy model returned no response")
            return None

        return self._parse_plan(raw, user_goal)

    # ───────────────────────────────────────────────────────────────────
    # RE-PLANNING
    # ───────────────────────────────────────────────────────────────────

    def replan(
        self,
        original_plan: DAGPlan,
        execution_context_summary: str,
        remaining_node_ids: List[str],
        reason: str,
    ) -> Optional[DAGPlan]:
        """Re-plan remaining DAG nodes based on current ExecutionContext.

        Called when:
          - Schema change detected after a transformation
          - A node's output contradicts assumptions
          - Two consecutive failures on the same node
        """
        system_prompt = self._build_replan_prompt()
        user_content = (
            f"ORIGINAL GOAL: {original_plan.user_goal}\n\n"
            f"REPLAN REASON: {reason}\n\n"
            f"REMAINING NODES TO REPLACE: {remaining_node_ids}\n\n"
            f"CURRENT EXECUTION STATE:\n{execution_context_summary}\n\n"
            f"COMPLETED STEPS:\n"
            + "\n".join(
                f"  - {h['node_id']}: {h['operation']} → {h['status']}"
                for h in (original_plan.metadata.values())
                if hasattr(h, 'to_dict')
            )
            + "\n\nGenerate a NEW DAG plan for the remaining work only. "
              "Re-use variables and outputs already produced by completed steps."
        )

        app_logger.info(f"[PLANNER] Re-planning due to: {reason[:100]}")

        raw = router.call(
            tier="heavy",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            max_tokens=6000,
            retries=2,
        )

        if not raw:
            app_logger.error("[PLANNER] Re-plan failed — no response from model")
            return None

        plan = self._parse_plan(raw, original_plan.user_goal)
        if plan:
            plan.plan_id = original_plan.plan_id  # keep same plan ID
            plan.version = original_plan.version + 1
            plan.replan_count = original_plan.replan_count + 1
            plan.status = "replanned"
        return plan

    # ───────────────────────────────────────────────────────────────────
    # PROMPT ENGINEERING
    # ───────────────────────────────────────────────────────────────────

    def _build_planner_prompt(self) -> str:
        return f"""You are an expert data science DAG planner. Your job is to decompose a user's data analysis goal into a structured Directed Acyclic Graph (DAG) of execution steps.

CRITICAL RULES:
1. Output ONLY valid JSON. No explanation text before or after.
2. Prefer MEDIUM-GRAINED nodes: 3–10 steps total unless the task is explicitly complex.
3. Group related operations logically — do NOT create 40 micro-steps.
4. Use structured conditions for branching — NEVER use raw eval strings.
5. Maximum {PRO_MAX_DAG_NODES} nodes per plan.
6. Every operation node must specify expected_output_type: "scalar", "dataframe", "artifact", or "dict".
7. Conditions must use typed operands with explicit "kind" (literal, variable, or step_ref).

NODE TYPES (use the most specific one):
- "analysis"        — Read-only computation (stats, correlations, data inspection)
- "transformation"  — Modifies the DataFrame (add/remove columns, filter, clean)
- "visualization"   — Produces a chart or plot
- "conditional"     — Branches based on a structured condition
- "summary"         — Generates a textual report or summary
- "operation"       — Generic fallback for anything else

CONDITION FORMAT (for conditional nodes):
{{
  "left": {{"kind": "variable", "value": "corr_value"}},
  "operator": ">",
  "right": {{"kind": "literal", "value": 0.5}}
}}
Operator options: >, <, >=, <=, ==, !=, in, not_in, contains, is_null, not_null

OUTPUT JSON SCHEMA:
{{
  "nodes": [
    {{
      "id": "node_1",
      "type": "analysis",
      "description": "Compute correlation matrix for all numeric columns",
      "operation": "compute_correlation_matrix",
      "inputs": {{}},
      "output_var": "corr_matrix",
      "expected_output_type": "dataframe",
      "depends_on": []
    }},
    {{
      "id": "node_2",
      "type": "conditional",
      "description": "Check if any correlation exceeds 0.8",
      "condition": {{
        "left": {{"kind": "variable", "value": "max_correlation"}},
        "operator": ">",
        "right": {{"kind": "literal", "value": 0.8}}
      }},
      "true_branch": ["node_3"],
      "false_branch": ["node_4"],
      "depends_on": ["node_1"]
    }}
  ]
}}"""

    def _build_replan_prompt(self) -> str:
        return f"""You are an expert data science DAG re-planner. The original plan encountered an issue
and needs partial re-planning. Generate ONLY the replacement nodes, not the already-completed ones.

Follow the same JSON schema and rules as the original planner.
Maximum {PRO_MAX_DAG_NODES} nodes. Prefer 3–10 medium-grained steps.
Reference variables already produced by completed steps using {{"kind": "variable", "value": "var_name"}}.
Output ONLY valid JSON."""

    def _build_user_content(
        self,
        user_goal: str,
        dataset_profile: Dict[str, Any],
        previous_transforms: List[str] = None,
    ) -> str:
        """Build the user message with full profile injection."""
        parts = [f"USER GOAL: {user_goal}"]

        # Full dataset profile injection
        parts.append("\nDATASET PROFILE:")
        parts.append(f"Shape: {dataset_profile.get('rows', '?')} rows × {dataset_profile.get('columns', '?')} columns")
        parts.append(f"Columns: {', '.join(dataset_profile.get('column_names', []))}")

        # Column details
        col_profiles = dataset_profile.get("column_profiles", {})
        if col_profiles:
            parts.append("\nCOLUMN DETAILS:")
            for col_name, prof in col_profiles.items():
                line = f"  {col_name} ({prof.get('dtype', '?')})"
                if prof.get("missing_pct", 0) > 0:
                    line += f" — {prof['missing_pct']}% missing"
                if prof.get("mean") is not None:
                    line += f" — mean={prof['mean']}, std={prof.get('std')}"
                if prof.get("unique_count") is not None:
                    line += f" — {prof['unique_count']} unique"
                if prof.get("sample_values"):
                    line += f" — samples: {prof['sample_values'][:3]}"
                parts.append(line)

        # Correlations
        corr_pairs = dataset_profile.get("high_correlation_pairs", [])
        if corr_pairs:
            parts.append("\nHIGH CORRELATIONS:")
            for p in corr_pairs[:10]:
                parts.append(f"  {p['column_a']} ↔ {p['column_b']} (r={p['correlation']})")

        # Warnings
        warnings = dataset_profile.get("warnings", [])
        if warnings:
            parts.append("\nDATA QUALITY WARNINGS:")
            for w in warnings[:10]:
                parts.append(f"  ⚠ {w}")

        # ID columns
        id_cols = dataset_profile.get("potential_id_columns", [])
        if id_cols:
            parts.append(f"\nPOTENTIAL ID COLUMNS: {id_cols}")

        # Class distribution
        class_dist = dataset_profile.get("class_distribution")
        if class_dist:
            parts.append(f"\nCLASS DISTRIBUTION ({class_dist['column']}): {class_dist['distribution']}")

        # Previous transforms
        if previous_transforms:
            parts.append("\nPREVIOUS TRANSFORMATIONS:")
            for t in previous_transforms[-10:]:
                parts.append(f"  - {t}")

        return "\n".join(parts)

    # ───────────────────────────────────────────────────────────────────
    # RESPONSE PARSING
    # ───────────────────────────────────────────────────────────────────

    def _parse_plan(self, raw: str, user_goal: str) -> Optional[DAGPlan]:
        """Parse raw model output into a validated DAGPlan."""
        json_str = self._extract_json(raw)
        if not json_str:
            app_logger.error("[PLANNER] Could not extract JSON from model response")
            return None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            app_logger.error(f"[PLANNER] JSON parse error: {e}")
            log_error(e, context="DAGPlanner._parse_plan")
            return None

        # Build plan
        plan = DAGPlan(user_goal=user_goal)
        nodes_data = data.get("nodes", data if isinstance(data, list) else [])

        for nd in nodes_data:
            try:
                node = DAGNode.from_dict(nd)
                plan.nodes.append(node)
            except Exception as e:
                app_logger.warning(f"[PLANNER] Skipping malformed node: {e}")

        if not plan.nodes:
            app_logger.error("[PLANNER] No valid nodes parsed from response")
            return None

        # Auto-generate edges from depends_on + branches
        plan.build_edges_from_nodes()

        # Validate
        errors = validate_plan(plan)
        if errors:
            for err in errors:
                app_logger.warning(f"[PLANNER] Validation: {err}")
            # Don't reject if only warnings — log and continue
            if any("cycle" in e.lower() for e in errors):
                app_logger.error("[PLANNER] Plan contains cycle — rejected")
                return None

        app_logger.info(f"[PLANNER] Plan created: {len(plan.nodes)} nodes, plan_id={plan.plan_id}")
        return plan

    @staticmethod
    def _extract_json(raw: str) -> Optional[str]:
        """Extract JSON from model response (may be wrapped in markdown)."""
        # Try fenced JSON block
        m = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
        if m:
            return m.group(1).strip()

        # Try raw JSON object
        m = re.search(r"(\{[\s\S]*\})", raw)
        if m:
            return m.group(1).strip()

        # Try raw JSON array
        m = re.search(r"(\[[\s\S]*\])", raw)
        if m:
            return f'{{"nodes": {m.group(1).strip()}}}'

        return None
