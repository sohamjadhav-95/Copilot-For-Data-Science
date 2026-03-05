# engines.py — Backward-compatibility shim
# v4.5: All logic has moved to engines_normal/normal_engine.py
# This file re-exports everything so existing imports in app.py continue to work.
from engines_normal.normal_engine import *  # noqa: F401, F403
# Explicitly re-export underscore-prefixed names skipped by import *
from engines_normal.normal_engine import _safe_exec, _validate_code, _restricted_import  # noqa: F401
from engines_normal.normal_engine import set_high_tier, get_high_tier  # noqa: F401
