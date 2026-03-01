# engines_pro/validator.py — Structured condition evaluation & node validation
# Handles operand resolution, condition evaluation, plan integrity, and output validation.
# NO eval() — all evaluation uses explicit operator mapping.
from __future__ import annotations

import operator
from typing import Any, List, Optional, Tuple

import pandas as pd

from engines_pro.dag_schema import (
    DAGPlan, DAGNode, StructuredCondition, Operand,
    OperandKind, OperatorType, NodeType, OutputType, NodeOutput,
)
from logger import app_logger


# ═══════════════════════════════════════════════════════════════════════
# OPERATOR DISPATCH — whitelisted, safe
# ═══════════════════════════════════════════════════════════════════════

_BINARY_OPS = {
    OperatorType.GT:  operator.gt,
    OperatorType.LT:  operator.lt,
    OperatorType.GTE: operator.ge,
    OperatorType.LTE: operator.le,
    OperatorType.EQ:  operator.eq,
    OperatorType.NEQ: operator.ne,
}


# ═══════════════════════════════════════════════════════════════════════
# OPERAND RESOLUTION — explicit rules per OperandKind
# ═══════════════════════════════════════════════════════════════════════

def resolve_operand(operand: Operand, context) -> Any:
    """Resolve an Operand to its concrete value using ExecutionContext.

    Resolution rules:
      LITERAL  → return operand.value as-is (number, string, bool, None)
      VARIABLE → lookup context.variables[operand.value]
      STEP_REF → lookup context.step_outputs[operand.value]

    Raises ValueError if the reference cannot be resolved.
    """
    if operand.kind == OperandKind.LITERAL:
        return operand.value

    if operand.kind == OperandKind.VARIABLE:
        name = str(operand.value)
        if name not in context.variables:
            raise ValueError(
                f"Variable '{name}' not found in ExecutionContext. "
                f"Available: {list(context.variables.keys())}"
            )
        return context.variables[name]

    if operand.kind == OperandKind.STEP_REF:
        node_id = str(operand.value)
        if node_id not in context.step_outputs:
            raise ValueError(
                f"Step output '{node_id}' not found in ExecutionContext. "
                f"Available: {list(context.step_outputs.keys())}"
            )
        return context.step_outputs[node_id]

    raise ValueError(f"Unknown OperandKind: {operand.kind}")


# ═══════════════════════════════════════════════════════════════════════
# CONDITION EVALUATION — structured, safe, no eval()
# ═══════════════════════════════════════════════════════════════════════

def evaluate_condition(condition: StructuredCondition, context) -> bool:
    """Evaluate a StructuredCondition against ExecutionContext.

    Returns True/False.  Raises ValueError on resolution failure.
    """
    left_val = resolve_operand(condition.left, context)
    op = condition.operator

    # Unary operators (right operand ignored)
    if op == OperatorType.IS_NULL:
        return left_val is None or (isinstance(left_val, float) and pd.isna(left_val))
    if op == OperatorType.NOT_NULL:
        return left_val is not None and not (isinstance(left_val, float) and pd.isna(left_val))

    # Binary operators — resolve right side
    right_val = resolve_operand(condition.right, context)

    # Collection operators
    if op == OperatorType.IN:
        return left_val in right_val
    if op == OperatorType.NOT_IN:
        return left_val not in right_val
    if op == OperatorType.CONTAINS:
        return right_val in left_val if isinstance(left_val, (str, list, tuple, set)) else False

    # Comparison operators
    fn = _BINARY_OPS.get(op)
    if fn:
        try:
            return bool(fn(left_val, right_val))
        except TypeError as e:
            app_logger.warning(f"[VALIDATOR] Type error in condition: {left_val} {op.value} {right_val}: {e}")
            return False

    app_logger.warning(f"[VALIDATOR] Unknown operator: {op}")
    return False


# ═══════════════════════════════════════════════════════════════════════
# PLAN VALIDATION — structural integrity checks
# ═══════════════════════════════════════════════════════════════════════

def validate_plan(plan: DAGPlan) -> List[str]:
    """Validate DAG plan structural integrity.  Returns list of error messages."""
    errors = []

    if not plan.nodes:
        errors.append("Plan has no nodes")
        return errors

    node_ids = {n.id for n in plan.nodes}

    # Check for duplicate IDs
    if len(node_ids) != len(plan.nodes):
        errors.append("Duplicate node IDs detected")

    for node in plan.nodes:
        # Validate dependencies exist
        for dep in node.depends_on:
            if dep not in node_ids:
                errors.append(f"Node '{node.id}' depends on non-existent node '{dep}'")

        # Validate conditional node structure
        if node.type == NodeType.CONDITIONAL:
            if not node.condition:
                errors.append(f"Conditional node '{node.id}' has no condition defined")
            for b in node.true_branch + node.false_branch:
                if b not in node_ids:
                    errors.append(f"Conditional node '{node.id}' references non-existent branch node '{b}'")
        else:
            # Operation nodes must have an operation name
            if not node.operation:
                errors.append(f"Node '{node.id}' has no operation defined")

    # Check for cycles (simple DFS)
    cycle = _detect_cycle(plan.nodes)
    if cycle:
        errors.append(f"DAG contains a cycle: {' → '.join(cycle)}")

    return errors


def _detect_cycle(nodes: list) -> Optional[List[str]]:
    """Detect cycles in DAG using DFS.  Returns cycle path or None."""
    adj = {}
    for n in nodes:
        adj[n.id] = list(n.depends_on)
        if n.type == NodeType.CONDITIONAL:
            adj[n.id].extend(n.true_branch)
            adj[n.id].extend(n.false_branch)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in adj}
    path = []

    def dfs(u):
        color[u] = GRAY
        path.append(u)
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                cycle_start = path.index(v)
                return path[cycle_start:] + [v]
            if color[v] == WHITE:
                result = dfs(v)
                if result:
                    return result
        path.pop()
        color[u] = BLACK
        return None

    for nid in adj:
        if color[nid] == WHITE:
            result = dfs(nid)
            if result:
                return result
    return None


# ═══════════════════════════════════════════════════════════════════════
# NODE OUTPUT VALIDATION — post-execution checks
# ═══════════════════════════════════════════════════════════════════════

def validate_node_output(
    node: DAGNode, output: NodeOutput, context
) -> Tuple[bool, List[str]]:
    """Validate a node's output after execution.

    TWO-TIER ENFORCEMENT:
      CRITICAL (is_valid=False) - executor MUST abort/replan:
        - output_var declared but output_type is NONE (variable never produced)
        - output_var declared but value is None (model returned null)
        - output_type claims DATAFRAME but runtime type is not pd.DataFrame
        - VISUALIZATION node produced no artifact

      WARNING (is_valid=True) - informational, execution continues:
        - expected_output_type mismatch but value is present and usable
        - DataFrame is empty (may be legitimate filtered result)
        - Schema column count changed after transformation

    Returns:
        (is_valid, [error/warning messages])
    """
    warnings: List[str] = []
    critical_errors: List[str] = []

    # ── RULE 1: output_var contract ─────────────────────────────────────
    # output_var declared + NONE output = model ignored variable contract.
    # Downstream nodes reading context.variables[output_var] will get KeyError.
    if node.output_var:
        if output.output_type == OutputType.NONE:
            critical_errors.append(
                f"CRITICAL: Node '{node.id}' declared output_var='{node.output_var}' "
                f"but produced no output (output_type=NONE). "
                f"Downstream variable reads will fail — aborting."
            )
        elif output.value is None:
            critical_errors.append(
                f"CRITICAL: Node '{node.id}' declared output_var='{node.output_var}' "
                f"but output.value is None. Context would be poisoned."
            )

    # ── RULE 2: DATAFRAME type-claim integrity ───────────────────────────
    # If node claims DATAFRAME output, value MUST be a pd.DataFrame.
    # Wrong runtime type corrupts any downstream transformation.
    if output.output_type == OutputType.DATAFRAME and output.value is not None:
        if not isinstance(output.value, pd.DataFrame):
            critical_errors.append(
                f"CRITICAL: Node '{node.id}' claims DATAFRAME output "
                f"but value is {type(output.value).__name__}. "
                f"Cannot safely store in ExecutionContext."
            )

    # ── RULE 3: visualization artifact contract ──────────────────────────
    if output.output_type == OutputType.ARTIFACT and not output.value:
        critical_errors.append(
            f"CRITICAL: Node '{node.id}' is a VISUALIZATION but produced "
            f"an empty artifact. Chart rendering failed."
        )

    # ── RULE 4: expected type mismatch (warn-only) ───────────────────────
    # Only warn when no critical issues — value exists, just wrong shape label.
    if (
        node.expected_output_type != OutputType.NONE
        and output.output_type != node.expected_output_type
        and not critical_errors
    ):
        warnings.append(
            f"Type mismatch: node '{node.id}' expected '{node.expected_output_type.value}' "
            f"but received '{output.output_type.value}'. Continuing — value is usable."
        )

    # ── RULE 5: empty DataFrame (warn-only) ─────────────────────────────
    if output.output_type == OutputType.DATAFRAME and isinstance(output.value, pd.DataFrame):
        if output.value.empty:
            warnings.append(
                f"Node '{node.id}' produced an empty DataFrame "
                f"(may be intentional from a filter operation)."
            )

    # ── RULE 6: schema column drift after transformation (warn-only) ─────
    if node.type == NodeType.TRANSFORMATION and context.df is not None:
        if context.dataset_profile and "columns" in context.dataset_profile:
            expected_cols = context.dataset_profile.get("columns", 0)
            actual_cols = context.df.shape[1]
            if actual_cols != expected_cols:
                warnings.append(
                    f"Schema drift after '{node.id}': "
                    f"expected {expected_cols} columns, got {actual_cols}."
                )

    # ── Final verdict ────────────────────────────────────────────────────
    is_valid = len(critical_errors) == 0
    for msg in critical_errors:
        app_logger.error(f"[VALIDATOR] {msg}")
    for msg in warnings:
        app_logger.warning(f"[VALIDATOR] {msg}")

    return is_valid, critical_errors + warnings



# ═══════════════════════════════════════════════════════════════════════
# SCHEMA CHANGE DETECTION — for replan triggers
# ═══════════════════════════════════════════════════════════════════════

def detect_schema_change(
    old_profile: dict, new_df: pd.DataFrame
) -> Tuple[bool, str]:
    """Compare a stored profile against the current DataFrame schema.

    Returns (changed, description).
    """
    old_cols = set(old_profile.get("column_names", []))
    new_cols = set(new_df.columns.tolist())

    added = new_cols - old_cols
    removed = old_cols - new_cols

    if not added and not removed:
        return False, ""

    parts = []
    if added:
        parts.append(f"added: {sorted(added)}")
    if removed:
        parts.append(f"removed: {sorted(removed)}")

    return True, f"Schema changed — {', '.join(parts)}"
