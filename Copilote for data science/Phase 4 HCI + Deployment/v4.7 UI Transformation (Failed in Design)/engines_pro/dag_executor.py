# engines_pro/dag_executor.py — Graph execution engine with topological sort
# Executes DAG nodes sequentially, handles retries, timeouts, re-planning triggers.
from __future__ import annotations

import io
import re
import time
import base64
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.config import PRO_NODE_RETRY_LIMIT, PRO_EXECUTION_TIMEOUT
from core.execution_context import ExecutionContext
from core.dataset_profiler import DatasetProfiler
from engines_pro.dag_schema import (
    DAGPlan, DAGNode, NodeType, NodeStatus, OutputType,
    NodeOutput, ExecutionMetadata,
)
from engines_pro.validator import (
    evaluate_condition, validate_node_output, detect_schema_change, resolve_operand,
)
from models_api.model_router import router
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# SAFE EXEC — isolated execution with restricted globals
# ═══════════════════════════════════════════════════════════════════════

# Reuse safe execution patterns from normal engine
_DANGEROUS_PATTERNS = [
    r"\bos\.\w+", r"\bsys\.\w+", r"\bsubprocess\b", r"\b__import__\b",
    r"\bopen\s*\(", r"\bexec\s*\(", r"\beval\s*\(", r"\bcompile\s*\(",
    r"\bglobals\s*\(", r"\blocals\s*\(",
    r"\bimport\s+os\b", r"\bimport\s+sys\b",
    r"\bimport\s+subprocess\b", r"\bimport\s+shutil\b",
    r"\bfrom\s+os\b", r"\bfrom\s+sys\b",
]


def _restricted_import(name, *args, **kwargs):
    allowed = {
        "pandas", "numpy", "matplotlib", "matplotlib.pyplot", "matplotlib.dates",
        "seaborn", "math", "statistics", "collections", "datetime", "re",
        "time", "functools", "itertools", "operator", "string", "decimal",
        "copy", "json", "csv", "io", "textwrap", "warnings", "scipy",
        "scipy.stats", "sklearn", "sklearn.preprocessing",
    }
    if name in allowed:
        return __import__(name, *args, **kwargs)
    raise ImportError(f"Import of '{name}' is not allowed in Pro Mode sandbox")


def _validate_code(code: str) -> Tuple[bool, str]:
    """Check if code is safe to execute."""
    import re as re_mod
    for pattern in _DANGEROUS_PATTERNS:
        if re_mod.search(pattern, code):
            return False, f"Blocked dangerous pattern: {pattern}"
    return True, ""


def _safe_exec_with_timeout(
    code: str, timeout: int = PRO_EXECUTION_TIMEOUT, description: str = ""
) -> Tuple[dict, Optional[str]]:
    """Execute code with restricted globals and a hard timeout.

    Returns (namespace, error_or_None).
    """
    is_safe, reason = _validate_code(code)
    if not is_safe:
        return {}, f"Code blocked: {reason}"

    import numpy as np
    import seaborn as sns

    restricted_globals = {
        "__builtins__": {
            "range": range, "len": len, "int": int, "float": float,
            "str": str, "bool": bool, "list": list, "dict": dict, "tuple": tuple,
            "set": set, "frozenset": frozenset, "sorted": sorted, "reversed": reversed,
            "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
            "sum": sum, "min": min, "max": max, "abs": abs, "round": round, "pow": pow,
            "any": any, "all": all, "isinstance": isinstance, "type": type,
            "print": lambda *a, **k: None,  # suppress prints
            "True": True, "False": False, "None": None,
            "__import__": _restricted_import,
            "property": property, "staticmethod": staticmethod,
            "classmethod": classmethod, "super": super,
            "ValueError": ValueError, "TypeError": TypeError,
            "KeyError": KeyError, "IndexError": IndexError,
            "RuntimeError": RuntimeError, "Exception": Exception,
        },
    }
    ns = dict(restricted_globals)

    # Pre-inject common libraries
    ns["pd"] = pd
    ns["np"] = np
    ns["plt"] = plt
    ns["sns"] = sns

    result = {"ns": ns, "error": None}

    def _exec_target():
        try:
            exec(code, result["ns"])
        except Exception as e:
            result["error"] = str(e)

    thread = threading.Thread(target=_exec_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        return result["ns"], f"Execution timed out after {timeout}s"

    return result["ns"], result["error"]


# ═══════════════════════════════════════════════════════════════════════
# CODE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

def _extract_code(raw: str) -> Optional[str]:
    """Extract Python code from model response."""
    if not raw:
        return None
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    for pat in [r"```python3?\s*\n(.*?)```", r"```py\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()

    m = re.search(r"```python3?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        if code:
            return code

    return None


# ═══════════════════════════════════════════════════════════════════════
# TOPOLOGICAL SORT
# ═══════════════════════════════════════════════════════════════════════

def topological_sort(plan: DAGPlan) -> List[str]:
    """Kahn's algorithm topological sort.  Returns ordered node IDs."""
    in_degree = {n.id: 0 for n in plan.nodes}
    adj = {n.id: [] for n in plan.nodes}

    for node in plan.nodes:
        for dep in node.depends_on:
            if dep in adj:
                adj[dep].append(node.id)
                in_degree[node.id] += 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    ordered = []

    while queue:
        nid = queue.popleft()
        ordered.append(nid)
        for neighbor in adj.get(nid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(plan.nodes):
        app_logger.warning("[EXECUTOR] Topological sort incomplete — possible cycle. Using node order.")
        return [n.id for n in plan.nodes]

    return ordered


# ═══════════════════════════════════════════════════════════════════════
# REPLAN TRIGGER POLICY — deterministic rules
# ═══════════════════════════════════════════════════════════════════════

class ReplanTrigger:
    """Deterministic rules for when re-planning should occur."""

    SCHEMA_CHANGE   = "schema_change"
    DOUBLE_FAILURE  = "double_failure"
    MISSING_VARIABLE = "missing_variable"

    @staticmethod
    def check_schema_change(context: ExecutionContext) -> Tuple[bool, str]:
        """After a transformation node, check if schema changed unexpectedly."""
        if context.df is not None and context.dataset_profile:
            changed, desc = detect_schema_change(context.dataset_profile, context.df)
            if changed:
                return True, f"{ReplanTrigger.SCHEMA_CHANGE}: {desc}"
        return False, ""

    @staticmethod
    def check_double_failure(node_id: str, metadata: Dict[str, ExecutionMetadata]) -> Tuple[bool, str]:
        """Check if a node has failed twice (original + retry)."""
        meta = metadata.get(node_id)
        if meta and meta.retry_count >= PRO_NODE_RETRY_LIMIT and meta.status == NodeStatus.FAILED:
            return True, f"{ReplanTrigger.DOUBLE_FAILURE}: node '{node_id}' failed after retry"
        return False, ""

    @staticmethod
    def check_missing_variable(node: DAGNode, context: ExecutionContext) -> Tuple[bool, str]:
        """Check if a node's input references a variable that doesn't exist."""
        for input_key, input_val in node.inputs.items():
            if isinstance(input_val, dict) and input_val.get("kind") == "variable":
                var_name = input_val.get("value")
                if var_name and var_name not in context.variables:
                    return True, (
                        f"{ReplanTrigger.MISSING_VARIABLE}: "
                        f"node '{node.id}' needs variable '{var_name}' which doesn't exist"
                    )
        return False, ""


# ═══════════════════════════════════════════════════════════════════════
# DAG EXECUTOR
# ═══════════════════════════════════════════════════════════════════════

class DAGExecutor:
    """Execute a DAG plan step-by-step with retry, timeout, and replan support.

    Execution flow per node:
      1. Check replan triggers (missing variable, etc.)
      2. Generate code via mid-tier model
      3. Execute with timeout
      4. Validate output (NodeOutput contract)
      5. Store results in ExecutionContext
      6. Check post-execution triggers (schema change)
      7. On failure: retry once, then abort or replan
    """

    def __init__(self):
        self._profiler = DatasetProfiler()
        self._skipped_nodes: set = set()

    def execute(
        self,
        plan: DAGPlan,
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Execute the full DAG plan.

        Returns:
            {
                "status": "completed" | "partial" | "failed" | "replan_needed",
                "completed_nodes": [...],
                "failed_nodes": [...],
                "skipped_nodes": [...],
                "replan_reason": "..." or None,
                "summary": "...",
            }
        """
        plan.status = "executing"
        execution_order = topological_sort(plan)
        completed = []
        failed = []
        replan_reason = None

        app_logger.info(f"[EXECUTOR] Starting DAG execution: {len(execution_order)} nodes")

        for node_id in execution_order:
            if node_id in self._skipped_nodes:
                continue

            node = plan.get_node(node_id)
            if not node:
                app_logger.warning(f"[EXECUTOR] Node '{node_id}' not found in plan, skipping")
                continue

            # Initialize metadata
            meta = ExecutionMetadata(node_id=node_id, status=NodeStatus.RUNNING)
            meta.started_at = datetime.now(timezone.utc).isoformat()
            plan.metadata[node_id] = meta

            # Pre-execution replan check
            if node.type != NodeType.CONDITIONAL:
                should_replan, reason = ReplanTrigger.check_missing_variable(node, context)
                if should_replan:
                    replan_reason = reason
                    meta.status = NodeStatus.ABORTED
                    meta.error = reason
                    meta.completed_at = datetime.now(timezone.utc).isoformat()
                    app_logger.warning(f"[EXECUTOR] Replan triggered before node '{node_id}': {reason}")
                    # Abort remaining
                    for remaining_id in execution_order[execution_order.index(node_id):]:
                        if remaining_id not in plan.metadata:
                            plan.metadata[remaining_id] = ExecutionMetadata(
                                node_id=remaining_id, status=NodeStatus.ABORTED
                            )
                    break

            # Execute node
            t0 = time.time()
            success = False

            if node.type == NodeType.CONDITIONAL:
                success = self._execute_conditional(node, context, meta, execution_order)
            else:
                success = self._execute_operation(node, context, meta, plan)

            elapsed = (time.time() - t0) * 1000
            meta.execution_time_ms = elapsed
            meta.completed_at = datetime.now(timezone.utc).isoformat()

            if success:
                completed.append(node_id)
                context.record_history(
                    node_id, node.operation or "conditional",
                    "success", model_used=meta.model_used, duration_ms=elapsed,
                )
            else:
                failed.append(node_id)
                context.record_history(
                    node_id, node.operation or "conditional",
                    "failed", details=meta.error or "", model_used=meta.model_used,
                    duration_ms=elapsed,
                )
                # Check double failure for replan
                should_replan, reason = ReplanTrigger.check_double_failure(node_id, plan.metadata)
                if should_replan:
                    replan_reason = reason
                    # Abort remaining nodes
                    remaining_idx = execution_order.index(node_id) + 1
                    for remaining_id in execution_order[remaining_idx:]:
                        if remaining_id not in self._skipped_nodes:
                            plan.metadata[remaining_id] = ExecutionMetadata(
                                node_id=remaining_id, status=NodeStatus.ABORTED
                            )
                    break
                else:
                    # Single failure — already retried in _execute_operation, abort chain
                    remaining_idx = execution_order.index(node_id) + 1
                    for remaining_id in execution_order[remaining_idx:]:
                        if remaining_id not in self._skipped_nodes:
                            plan.metadata[remaining_id] = ExecutionMetadata(
                                node_id=remaining_id, status=NodeStatus.ABORTED
                            )
                    break

            # Post-execution: check schema change
            if node.type in (NodeType.TRANSFORMATION, NodeType.OPERATION):
                should_replan, reason = ReplanTrigger.check_schema_change(context)
                if should_replan:
                    # Update profile to reflect new schema
                    new_profile = self._profiler.profile(context.df)
                    context.update_profile(new_profile)
                    app_logger.info(f"[EXECUTOR] Schema changed after '{node_id}', profile updated")
                    # Don't immediately replan — just update profile and continue
                    # Replan only if downstream nodes fail due to the change

        # Determine final status
        if replan_reason:
            status = "replan_needed"
            plan.status = "failed"
        elif failed:
            status = "partial" if completed else "failed"
            plan.status = "failed"
        else:
            status = "completed"
            plan.status = "completed"

        skipped = list(self._skipped_nodes)

        return {
            "status": status,
            "completed_nodes": completed,
            "failed_nodes": failed,
            "skipped_nodes": skipped,
            "replan_reason": replan_reason,
            "metadata": {k: v.to_dict() for k, v in plan.metadata.items()},
        }

    # ───────────────────────────────────────────────────────────────────
    # OPERATION NODE EXECUTION
    # ───────────────────────────────────────────────────────────────────

    def _execute_operation(
        self, node: DAGNode, context: ExecutionContext,
        meta: ExecutionMetadata, plan: DAGPlan,
    ) -> bool:
        """Execute an operation node. Returns True on success."""
        # Generate code via mid-tier model
        code = self._generate_node_code(node, context)
        if not code:
            meta.status = NodeStatus.FAILED
            meta.error = "Code generation failed"
            return False

        # Execute with timeout
        ns, err = _safe_exec_with_timeout(code, description=f"Node {node.id}: {node.operation}")

        # Retry once on failure
        if err:
            meta.retry_count += 1
            meta.status = NodeStatus.RETRYING
            app_logger.warning(f"[EXECUTOR] Node '{node.id}' failed: {err}, retrying...")

            # Generate fix
            fixed_code = self._generate_fix(code, err, node, context)
            if fixed_code:
                code = fixed_code
                ns, err = _safe_exec_with_timeout(code, description=f"Node {node.id} (retry): {node.operation}")

        if err:
            meta.status = NodeStatus.FAILED
            meta.error = err
            return False

        # Extract and validate output
        output = self._extract_node_output(ns, node)

        is_valid, warnings = validate_node_output(node, output, context)
        meta.warnings = warnings
        meta.output_type = output.output_type.value

        if not is_valid:
            meta.status = NodeStatus.FAILED
            meta.error = f"Output validation failed: {'; '.join(warnings)}"
            return False

        # Store output in context
        if node.output_var and output.value is not None:
            context.set_variable(node.output_var, output.value)

        context.store_step_output(node.id, output.value)

        # If output is a DataFrame update, replace context df
        if output.output_type == OutputType.DATAFRAME and isinstance(output.value, pd.DataFrame):
            if node.type == NodeType.TRANSFORMATION:
                context.update_df(output.value)

        # If output is an artifact (chart), store it
        if output.output_type == OutputType.ARTIFACT and output.value:
            context.add_artifact(f"{node.id}_artifact", output.value)

        meta.status = NodeStatus.SUCCESS
        app_logger.info(f"[EXECUTOR] Node '{node.id}' completed: {output.output_type.value}")
        return True

    # ───────────────────────────────────────────────────────────────────
    # CONDITIONAL NODE EXECUTION
    # ───────────────────────────────────────────────────────────────────

    def _execute_conditional(
        self, node: DAGNode, context: ExecutionContext,
        meta: ExecutionMetadata, execution_order: list,
    ) -> bool:
        """Evaluate a conditional node and set branch skip set."""
        if not node.condition:
            meta.status = NodeStatus.FAILED
            meta.error = "No condition defined"
            return False

        try:
            result = evaluate_condition(node.condition, context)
        except ValueError as e:
            meta.status = NodeStatus.FAILED
            meta.error = str(e)
            return False

        if result:
            # True branch executes, skip false branch
            for fb in node.false_branch:
                self._skipped_nodes.add(fb)
            meta.status = NodeStatus.SUCCESS
            app_logger.info(f"[EXECUTOR] Conditional '{node.id}' → TRUE (executing: {node.true_branch})")
        else:
            # False branch executes, skip true branch
            for tb in node.true_branch:
                self._skipped_nodes.add(tb)
            meta.status = NodeStatus.SUCCESS
            app_logger.info(f"[EXECUTOR] Conditional '{node.id}' → FALSE (executing: {node.false_branch})")

        context.set_variable(f"{node.id}_result", result)
        context.store_step_output(node.id, result)
        return True

    # ───────────────────────────────────────────────────────────────────
    # CODE GENERATION PER NODE
    # ───────────────────────────────────────────────────────────────────

    def _generate_node_code(self, node: DAGNode, context: ExecutionContext) -> Optional[str]:
        """Generate Python code for a single DAG node using mid-tier model."""
        model_context = context.to_model_context()

        system_prompt = f"""You are an expert Python/pandas code generator executing a step in a data analysis pipeline.

EXECUTION CONTEXT:
{model_context}

FILE PATH: {context.file_path}

YOUR TASK: Generate Python code for this specific operation.

STRICT RULES:
1. Import pandas as pd at the top.
2. Load data: df = pd.read_csv(r'{context.file_path}')
3. You have access to: pd, np, plt, sns, scipy, sklearn
4. Store the primary result in a variable called _result
5. _result should be: a scalar, a DataFrame, a dict, or a matplotlib figure
6. For visualizations: create the chart and set _result_fig = plt.gcf()
7. For DataFrames that modify data: save with df.to_csv(r'{context.file_path}', index=False) and set _result = df
8. Column names are CASE-SENSITIVE.
9. NO print() statements.
10. NO os/sys/subprocess imports.
11. Return code inside ```python ... ``` block ONLY."""

        user_content = (
            f"NODE: {node.id}\n"
            f"TYPE: {node.type.value}\n"
            f"OPERATION: {node.operation}\n"
            f"DESCRIPTION: {node.description}\n"
        )

        if node.inputs:
            user_content += f"INPUTS: {node.inputs}\n"

        if node.output_var:
            user_content += f"STORE RESULT AS: {node.output_var}\n"

        user_content += f"\nEXPECTED OUTPUT TYPE: {node.expected_output_type.value}"

        # Get model info for metadata tracking
        model_info = router.get_model_info("mid")

        raw = router.call(
            tier="mid",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=4000,
        )

        if model_info:
            meta = next(
                (m for m in [None] if False),  # placeholder
                None,
            )

        code = _extract_code(raw) if raw else None
        return code

    def _generate_fix(
        self, failed_code: str, error: str, node: DAGNode, context: ExecutionContext
    ) -> Optional[str]:
        """Ask mid-tier model to fix failed code."""
        system_prompt = f"""Fix this Python code that failed with an error.

CONTEXT:
{context.to_model_context(max_history=5)}

FILE PATH: {context.file_path}
ERROR: {error}

FAILED CODE:
```python
{failed_code}
```

Return ONLY the corrected code inside ```python ... ``` block.
Fix the specific error while keeping the original intent.
Column names are CASE-SENSITIVE."""

        raw = router.call(
            tier="mid",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Fix the code."},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        return _extract_code(raw) if raw else None

    # ───────────────────────────────────────────────────────────────────
    # OUTPUT EXTRACTION
    # ───────────────────────────────────────────────────────────────────

    def _extract_node_output(self, ns: dict, node: DAGNode) -> NodeOutput:
        """Extract standardized NodeOutput from execution namespace."""
        # Check for visualization output
        if node.type == NodeType.VISUALIZATION or "_result_fig" in ns:
            fig = ns.get("_result_fig", plt.gcf())
            if fig and fig.get_axes():
                try:
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
                    buf.seek(0)
                    b64 = base64.b64encode(buf.getvalue()).decode()
                    plt.close("all")
                    return NodeOutput(
                        output_type=OutputType.ARTIFACT,
                        value=b64,
                        summary=f"Chart generated for {node.operation}",
                    )
                except Exception as e:
                    plt.close("all")
                    app_logger.warning(f"[EXECUTOR] Chart capture failed: {e}")

        # Check for _result variable
        result = ns.get("_result")
        if result is None:
            result = ns.get("_result_df")

        if result is None:
            return NodeOutput(output_type=OutputType.NONE, summary="No output produced")

        if isinstance(result, pd.DataFrame):
            return NodeOutput(
                output_type=OutputType.DATAFRAME, value=result,
                summary=f"DataFrame ({result.shape[0]}×{result.shape[1]})",
            )
        if isinstance(result, pd.Series):
            return NodeOutput(
                output_type=OutputType.DATAFRAME, value=result.to_frame(),
                summary=f"Series→DataFrame (len={len(result)})",
            )
        if isinstance(result, dict):
            return NodeOutput(
                output_type=OutputType.DICT, value=result,
                summary=f"Dict with keys: {list(result.keys())[:5]}",
            )
        # Scalar
        return NodeOutput(
            output_type=OutputType.SCALAR, value=result,
            summary=f"Scalar: {str(result)[:100]}",
        )

    # ───────────────────────────────────────────────────────────────────
    # FINAL SUMMARY GENERATION
    # ───────────────────────────────────────────────────────────────────

    def generate_final_summary(
        self, plan: DAGPlan, context: ExecutionContext, execution_result: dict,
    ) -> str:
        """Generate a human-readable summary of DAG execution using heavy model."""
        model_context = context.to_model_context()

        prompt = f"""You are a data science expert summarizing the results of an automated analysis pipeline.

ORIGINAL GOAL: {plan.user_goal}

EXECUTION RESULTS:
  Completed: {execution_result.get('completed_nodes', [])}
  Failed: {execution_result.get('failed_nodes', [])}
  Skipped: {execution_result.get('skipped_nodes', [])}

EXECUTION CONTEXT:
{model_context}

Write a clear, concise summary of:
1. What was accomplished
2. Key findings and results
3. Any issues encountered
4. Suggestions for next steps

Use **bold** for key terms. Use bullet points for lists. Be professional but approachable."""

        result = router.call(
            tier="heavy",
            messages=[
                {"role": "system", "content": "You are a data science report writer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=2000,
        )

        return result or "Execution completed. Check step details for individual results."
