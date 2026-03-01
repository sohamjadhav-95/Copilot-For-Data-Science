# engines.py — Backward-compatibility shim
# v4.5: All logic has moved to engines_normal/normal_engine.py
# This file re-exports everything so existing imports in app.py continue to work.
from engines_normal.normal_engine import *  # noqa: F401, F403
