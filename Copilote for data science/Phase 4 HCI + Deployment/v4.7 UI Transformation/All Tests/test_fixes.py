# -*- coding: utf-8 -*-
"""Verify all fixes work correctly."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines import classify_intent, _keyword_classify

# Test 1: Keyword classification (instant, zero API calls)
print("=== KEYWORD CLASSIFICATION ===")
tests = [
    ("show 10 rows", "display"),
    ("show 5 rows", "display"),
    ("what is max of low", "display"),
    ("describe", "display"),
    ("columns", "display"),
    ("on which day the largest movement happened", "display"),
    ("what is maximum high to low difference in a day", "display"),
    ("what is main insight of the data", "display"),
    ("create a pie chart", "visualize"),
    ("plot close over time", "visualize"),
    ("delete time column", "modify"),
    ("add column", "modify"),
    ("sort by close", "modify"),
    ("undo", "undo"),
    ("hello", "chat"),
    ("tell me in words", "chat"),
]
passed = 0
for inp, expected in tests:
    result = _keyword_classify(inp)
    ok = "PASS" if result == expected else "FAIL"
    if ok == "PASS":
        passed += 1
    print(f"  {ok}: \"{inp}\" -> {result} (expected {expected})")
print(f"\n  Score: {passed}/{len(tests)}")

# Test 2: Full classify_intent (keyword-first, AI fallback)
print("\n=== FULL CLASSIFY_INTENT ===")
for inp, expected in [("show 10 rows", "display"), ("create a pie chart", "visualize")]:
    result = classify_intent(inp)
    ok = "PASS" if result == expected else "FAIL"
    print(f"  {ok}: \"{inp}\" -> {result} (expected {expected})")

# Test 3: safe_exec builtins
print("\n=== SAFE EXEC BUILTINS ===")
from engines import _safe_exec
code1 = "x = all([True, True, False])\n_result_df = x"
ns, err = _safe_exec(code1, "test all()")
print(f"  all(): {'PASS' if err is None else 'FAIL: ' + str(err)}")

code2 = "x = any([False, False, True])\n_result_df = x"
ns, err = _safe_exec(code2, "test any()")
print(f"  any(): {'PASS' if err is None else 'FAIL: ' + str(err)}")

code3 = "x = hasattr('hello', 'upper')\n_result_df = x"
ns, err = _safe_exec(code3, "test hasattr()")
print(f"  hasattr(): {'PASS' if err is None else 'FAIL: ' + str(err)}")

# Test 4: restricted imports
print("\n=== RESTRICTED IMPORTS ===")
code4 = "import time\n_result_df = time.time()"
ns, err = _safe_exec(code4, "test time import")
print(f"  import time: {'PASS' if err is None else 'FAIL: ' + str(err)}")

code5 = "import os\n_result_df = 'bad'"
ns, err = _safe_exec(code5, "test os import")
print(f"  import os (should block): {'PASS' if err is not None or 'blocked' in str(err).lower() else 'FAIL'}")

# Test 5: Check Groq model config
print("\n=== MODEL CONFIG ===")
from api_config import PROVIDERS
groq_primary = PROVIDERS["groq"]["models"]["primary"]
groq_coder = PROVIDERS["groq"]["models"]["coder"]
print(f"  Groq primary: {groq_primary} - {'PASS' if 'llama' in groq_primary else 'FAIL'}")
print(f"  Groq coder:   {groq_coder} - {'PASS' if 'llama' in groq_coder else 'FAIL'}")

print("\nDONE")
