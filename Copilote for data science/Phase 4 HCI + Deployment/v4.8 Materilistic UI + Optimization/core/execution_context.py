# core/execution_context.py — Internal execution memory for Pro Mode DAG execution
# Persists across all DAG steps.  Models receive .to_model_context(), never raw data.
import sys
import json
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from core.config import (
    PRO_MAX_ARTIFACT_SIZE_BYTES,
    PRO_MAX_ARTIFACTS,
    PRO_MAX_HISTORY_ENTRIES,
)


class ExecutionContext:
    """Persistent execution state that flows through the entire DAG.

    Attributes:
        df:              The current DataFrame being operated on.
        dataset_profile: The structured profile (from DatasetProfiler).
        variables:       Named variables produced by DAG nodes (e.g. corr_value=0.87).
        artifacts:       Heavy outputs like charts, reports (stored as {name: data}).
        history:         Chronological log of every step executed.
        step_outputs:    Mapping of node_id → output for cross-node references.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        dataset_profile: Dict[str, Any],
        file_path: str = "",
    ):
        self.df = df
        self.dataset_profile = dataset_profile
        self.file_path = file_path
        self.variables: Dict[str, Any] = {}
        self.artifacts: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.step_outputs: Dict[str, Any] = {}

    # ───────────────────────────────────────────────────────────────────
    # MUTATION METHODS (used by DAG executor)
    # ───────────────────────────────────────────────────────────────────

    def set_variable(self, name: str, value: Any) -> None:
        """Store a named variable produced by a DAG node."""
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Retrieve a named variable."""
        return self.variables.get(name, default)

    def store_step_output(self, node_id: str, output: Any) -> None:
        """Record the raw output of a DAG node."""
        self.step_outputs[node_id] = output

    def get_step_output(self, node_id: str) -> Any:
        """Retrieve a previous node's output."""
        return self.step_outputs.get(node_id)

    def add_artifact(self, name: str, data: Any) -> None:
        """Store a heavy artifact (chart base64, report text, etc.).

        Enforces two limits:
          1. Single artifact size <= PRO_MAX_ARTIFACT_SIZE_BYTES (default 5 MB)
          2. Total artifact count <= PRO_MAX_ARTIFACTS (prunes oldest on overflow)
        """
        # Size guard: reject artifacts that exceed the per-item limit
        try:
            item_size = sys.getsizeof(data)
            if isinstance(data, str):
                item_size = len(data.encode("utf-8"))
            elif isinstance(data, bytes):
                item_size = len(data)
        except Exception:
            item_size = 0

        if item_size > PRO_MAX_ARTIFACT_SIZE_BYTES:
            from logger import app_logger
            app_logger.warning(
                f"[CONTEXT] Artifact '{name}' size {item_size:,} bytes exceeds limit "
                f"{PRO_MAX_ARTIFACT_SIZE_BYTES:,} bytes — storing summary only."
            )
            # Store a placeholder summary instead of the full artifact
            data = f"<artifact too large: {item_size:,} bytes>"

        self.artifacts[name] = data

        # Count guard: prune oldest artifact when limit exceeded
        if len(self.artifacts) > PRO_MAX_ARTIFACTS:
            oldest_key = next(iter(self.artifacts))
            del self.artifacts[oldest_key]
            from logger import app_logger
            app_logger.info(
                f"[CONTEXT] Artifact store full ({PRO_MAX_ARTIFACTS} max) — "
                f"pruned oldest: '{oldest_key}'"
            )

    def record_history(
        self,
        node_id: str,
        operation: str,
        status: str,
        details: str = "",
        model_used: str = "",
        duration_ms: float = 0,
    ) -> None:
        """Append a step record to execution history.

        Caps list at PRO_MAX_HISTORY_ENTRIES to prevent unbounded growth.
        Oldest entries are dropped when the cap is exceeded.
        """
        self.history.append({
            "node_id": node_id,
            "operation": operation,
            "status": status,
            "details": details[:500],
            "model_used": model_used,
            "duration_ms": round(duration_ms, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Trim oldest entries if over cap
        if len(self.history) > PRO_MAX_HISTORY_ENTRIES:
            self.history = self.history[-PRO_MAX_HISTORY_ENTRIES:]

    def update_df(self, new_df: pd.DataFrame) -> None:
        """Replace the working DataFrame (e.g. after a modify step)."""
        self.df = new_df

    def update_profile(self, new_profile: Dict[str, Any]) -> None:
        """Replace the dataset profile (e.g. after schema change)."""
        self.dataset_profile = new_profile

    def prune_artifacts(self, keep_latest: int = 10) -> int:
        """Manually prune artifacts to the N most recently inserted.

        Returns the number of artifacts removed.
        Call this after a node completes to reclaim memory proactively.
        """
        if len(self.artifacts) <= keep_latest:
            return 0
        keys = list(self.artifacts.keys())
        to_remove = keys[: len(keys) - keep_latest]
        for k in to_remove:
            del self.artifacts[k]
        return len(to_remove)

    # ───────────────────────────────────────────────────────────────────
    # SERIALIZATION FOR MODELS (safe — never sends raw data)
    # ───────────────────────────────────────────────────────────────────

    def to_model_context(self, max_history: int = 10) -> str:
        """Return a text summary safe to send to LLM models.

        Includes: profile summary, variables, recent history, step output summaries.
        NEVER includes: raw DataFrame rows, full artifacts.
        """
        parts = []

        # 1. Dataset profile summary
        prof = self.dataset_profile
        parts.append(f"DATASET: {prof.get('rows', '?')} rows × {prof.get('columns', '?')} columns")
        parts.append(f"Columns: {', '.join(prof.get('column_names', []))}")

        if prof.get("warnings"):
            parts.append(f"Warnings: {'; '.join(prof['warnings'][:5])}")

        if prof.get("high_correlation_pairs"):
            pairs_str = ", ".join(
                f"{p['column_a']}↔{p['column_b']}(r={p['correlation']})"
                for p in prof["high_correlation_pairs"][:5]
            )
            parts.append(f"High correlations: {pairs_str}")

        # 2. Current variables
        if self.variables:
            var_lines = []
            for k, v in self.variables.items():
                v_str = str(v)
                if len(v_str) > 200:
                    v_str = v_str[:200] + "..."
                var_lines.append(f"  {k} = {v_str}")
            parts.append("VARIABLES:\n" + "\n".join(var_lines))

        # 3. Recent history
        recent = self.history[-max_history:] if self.history else []
        if recent:
            hist_lines = []
            for h in recent:
                hist_lines.append(
                    f"  [{h['node_id']}] {h['operation']} → {h['status']}"
                    + (f" ({h['details'][:100]})" if h['details'] else "")
                )
            parts.append("EXECUTION HISTORY:\n" + "\n".join(hist_lines))

        # 4. Step output summaries (not full data)
        if self.step_outputs:
            out_lines = []
            for nid, out in self.step_outputs.items():
                summary = self._summarize_output(out)
                out_lines.append(f"  {nid}: {summary}")
            parts.append("STEP OUTPUTS:\n" + "\n".join(out_lines))

        return "\n\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the context state (excluding df) for API responses."""
        return {
            "file_path": self.file_path,
            "dataset_profile": self.dataset_profile,
            "variables": {k: self._safe_serialize(v) for k, v in self.variables.items()},
            "artifacts": list(self.artifacts.keys()),
            "history": self.history,
            "step_output_ids": list(self.step_outputs.keys()),
        }

    # ───────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _summarize_output(output: Any) -> str:
        """Create a brief summary of a step output for model context."""
        if output is None:
            return "None"
        if isinstance(output, pd.DataFrame):
            return f"DataFrame({output.shape[0]}×{output.shape[1]}, cols={list(output.columns)[:8]})"
        if isinstance(output, pd.Series):
            return f"Series(len={len(output)}, name={output.name})"
        if isinstance(output, dict):
            return f"Dict(keys={list(output.keys())[:8]})"
        if isinstance(output, (list, tuple)):
            return f"{'List' if isinstance(output, list) else 'Tuple'}(len={len(output)})"
        if isinstance(output, (int, float, bool)):
            return str(output)
        s = str(output)
        return s[:150] + "..." if len(s) > 150 else s

    @staticmethod
    def _safe_serialize(val: Any) -> Any:
        """Convert to JSON-safe types."""
        if isinstance(val, pd.DataFrame):
            return f"<DataFrame {val.shape}>"
        if isinstance(val, pd.Series):
            return f"<Series len={len(val)}>"
        if isinstance(val, (int, float, str, bool, type(None))):
            return val
        try:
            json.dumps(val)
            return val
        except (TypeError, ValueError):
            return str(val)[:200]
