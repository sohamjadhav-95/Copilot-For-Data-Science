# core/dataset_profiler.py — Structured dataset profiling for Normal & Pro modes
# Generates a rich DatasetProfile object that models receive *instead* of raw data.
import json
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.config import (
    PROFILER_SAMPLE_THRESHOLD,
    PROFILER_SAMPLE_SIZE,
    PROFILER_CORRELATION_THRESHOLD,
    PROFILER_ID_UNIQUE_RATIO,
    PROFILER_MAX_SAMPLE_VALUES,
)


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

class DatasetProfiler:
    """Generates a structured DatasetProfile from a pandas DataFrame.

    Usage:
        profiler = DatasetProfiler()
        profile = profiler.profile(df)   # returns dict
        profile_json = profiler.profile_json(df)  # returns JSON string
    """

    def profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Build a complete DatasetProfile dictionary."""
        working_df = self._maybe_sample(df)

        column_profiles = {}
        for col in df.columns:
            column_profiles[col] = self._profile_column(df, working_df, col)

        high_corr = self._find_high_correlations(working_df)
        id_cols = self._detect_id_columns(df)
        class_dist = self._detect_class_distribution(df)
        profile_warnings = self._generate_warnings(df, column_profiles)

        return {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "column_names": df.columns.tolist(),
            "column_profiles": column_profiles,
            "high_correlation_pairs": high_corr,
            "potential_id_columns": id_cols,
            "class_distribution": class_dist,
            "warnings": profile_warnings,
        }

    def profile_json(self, df: pd.DataFrame) -> str:
        """Return profile as a JSON string (for model prompts)."""
        return json.dumps(self.profile(df), indent=2, default=str)

    # ───────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ───────────────────────────────────────────────────────────────────

    def _maybe_sample(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a sampled DF for heavy calculations on large datasets."""
        if len(df) > PROFILER_SAMPLE_THRESHOLD:
            return df.sample(n=min(PROFILER_SAMPLE_SIZE, len(df)), random_state=42)
        return df

    def _profile_column(
        self, full_df: pd.DataFrame, sample_df: pd.DataFrame, col: str
    ) -> Dict[str, Any]:
        """Profile a single column."""
        series = full_df[col]
        sample_series = sample_df[col]
        total = len(series)

        profile: Dict[str, Any] = {
            "dtype": str(series.dtype),
            "missing_count": int(series.isnull().sum()),
            "missing_pct": round(float(series.isnull().sum()) / total * 100, 2) if total > 0 else 0.0,
            "unique_count": int(series.nunique()),
        }

        # Numeric columns — compute stats from sample for speed
        if pd.api.types.is_numeric_dtype(series):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                profile.update({
                    "min": self._safe_scalar(sample_series.min()),
                    "max": self._safe_scalar(sample_series.max()),
                    "mean": self._safe_scalar(sample_series.mean()),
                    "std": self._safe_scalar(sample_series.std()),
                    "skewness": self._safe_scalar(sample_series.skew()),
                })
        else:
            profile.update({"min": None, "max": None, "mean": None, "std": None, "skewness": None})

        # Sample values (always from full DF, non-null)
        non_null = series.dropna()
        if len(non_null) > 0:
            sample_vals = non_null.unique()[:PROFILER_MAX_SAMPLE_VALUES]
            profile["sample_values"] = [str(v)[:80] for v in sample_vals]
        else:
            profile["sample_values"] = []

        return profile

    def _find_high_correlations(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Find column pairs with correlation above threshold."""
        num_df = df.select_dtypes(include="number")
        if num_df.shape[1] < 2:
            return []

        try:
            corr = num_df.corr()
        except Exception:
            return []

        pairs = []
        seen = set()
        for i, c1 in enumerate(corr.columns):
            for j, c2 in enumerate(corr.columns):
                if i >= j:
                    continue
                r = corr.iloc[i, j]
                if pd.notna(r) and abs(r) >= PROFILER_CORRELATION_THRESHOLD:
                    key = tuple(sorted([c1, c2]))
                    if key not in seen:
                        seen.add(key)
                        pairs.append({
                            "column_a": c1,
                            "column_b": c2,
                            "correlation": round(float(r), 4),
                        })

        # Sort by |r| descending
        pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
        return pairs[:20]  # cap at 20 pairs

    def _detect_id_columns(self, df: pd.DataFrame) -> List[str]:
        """Detect columns that are likely unique identifiers."""
        id_cols = []
        for col in df.columns:
            series = df[col]
            if series.isnull().all():
                continue
            unique_ratio = series.nunique() / max(len(series), 1)
            # High unique ratio + (integer or string) → likely ID
            if unique_ratio >= PROFILER_ID_UNIQUE_RATIO:
                if pd.api.types.is_integer_dtype(series) or pd.api.types.is_string_dtype(series):
                    id_cols.append(col)
        return id_cols

    def _detect_class_distribution(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Detect class distribution if a categorical target column exists."""
        # Heuristic: look for columns named 'target', 'label', 'class', 'category'
        target_candidates = [
            c for c in df.columns
            if c.lower() in ("target", "label", "class", "category", "y", "output")
        ]
        if not target_candidates:
            # Fallback: last categorical column with low cardinality
            cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
            low_card = [c for c in cat_cols if df[c].nunique() <= 20]
            if low_card:
                target_candidates = [low_card[-1]]

        if not target_candidates:
            return None

        col = target_candidates[0]
        dist = df[col].value_counts().head(20).to_dict()
        return {
            "column": col,
            "distribution": {str(k): int(v) for k, v in dist.items()},
            "total_classes": int(df[col].nunique()),
        }

    def _generate_warnings(
        self, df: pd.DataFrame, column_profiles: Dict[str, Dict]
    ) -> List[str]:
        """Generate data quality warnings."""
        warns = []

        # High missing percentage
        for col, prof in column_profiles.items():
            if prof["missing_pct"] > 50:
                warns.append(f"Column '{col}' has {prof['missing_pct']}% missing values")
            elif prof["missing_pct"] > 20:
                warns.append(f"Column '{col}' has {prof['missing_pct']}% missing values")

        # Constant columns
        for col, prof in column_profiles.items():
            if prof["unique_count"] <= 1 and prof["missing_count"] < len(df):
                warns.append(f"Column '{col}' is constant (single value)")

        # Very high cardinality text columns
        for col, prof in column_profiles.items():
            if prof["dtype"] == "object" and prof["unique_count"] > 0.9 * len(df) and len(df) > 100:
                if col not in self._detect_id_columns(df):
                    warns.append(f"Column '{col}' has very high cardinality ({prof['unique_count']} unique)")

        # Duplicate rows
        try:
            dup_count = df.duplicated().sum()
            if dup_count > 0:
                warns.append(f"Dataset has {dup_count} duplicate rows ({dup_count / len(df) * 100:.1f}%)")
        except Exception:
            pass

        return warns

    @staticmethod
    def _safe_scalar(val) -> Any:
        """Convert numpy scalars to Python natives for JSON serialization."""
        if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            return None
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return round(float(val), 6)
        return val
