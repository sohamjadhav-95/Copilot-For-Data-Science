# -*- coding: utf-8 -*-
"""Verify local templates handle all screenshot-failing queries."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from engines import _keyword_classify, _try_local_display

# Load the actual dataset
csv_path = os.path.join(os.path.dirname(__file__), "uploads", "1", "BTCUSDm_M1_Cleaned.csv")
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    print(f"Dataset: {df.shape[0]} rows, {list(df.columns)}")
else:
    print(f"CSV not found at {csv_path}")
    sys.exit(1)

# Test 1: Keyword classification for screenshot queries
print("\n== INTENT CLASSIFICATION ==")
queries = [
    ("show 5 rows", "display"),
    ("show mid 2 rows", "display"),
    ("what is max of low", "display"),
    ("what is maximum high to low difference in a day", "display"),
    ("on which day the largest movement happened", "display"),
    ("show 10 rows", "display"),
    ("create a pie chart", "visualize"),
    ("delete time column", "modify"),
    ("hello", "chat"),
    ("tell me in words", "chat"),  # this is chat-like
]
for inp, expected in queries:
    got = _keyword_classify(inp)
    ok = "PASS" if got == expected else "FAIL"
    print(f"  {ok}: '{inp}' -> {got} (expected {expected})")

# Test 2: Local templates (zero API calls!)
print("\n== LOCAL TEMPLATES ==")
template_tests = [
    "show 5 rows",
    "show 10 rows",
    "show mid 2 rows",
    "what is max of low",
    "describe",
    "columns",
    "shape",
    "last 3 rows",
    "missing values",
]
for inp in template_tests:
    code, title = _try_local_display(inp, df, csv_path)
    if code:
        # Actually execute the code to verify it works
        ns = {}
        try:
            exec(code, ns)
            rdf = ns.get("_result_df")
            if rdf is not None:
                rows = len(rdf) if hasattr(rdf, '__len__') else 1
                print(f"  PASS: '{inp}' -> '{title}' ({rows} rows)")
            else:
                print(f"  FAIL: '{inp}' -> code ran but no _result_df")
        except Exception as e:
            print(f"  FAIL: '{inp}' -> exec error: {e}")
    else:
        print(f"  SKIP: '{inp}' -> no local template (needs AI)")

# Test 3: Queries that SHOULD go to AI
print("\n== SHOULD USE AI (no local template) ==")
ai_queries = [
    "on which day the largest movement happened",
    "what is maximum high to low difference in a day",
    "what is main insight of the data",
]
for inp in ai_queries:
    code, title = _try_local_display(inp, df, csv_path)
    status = "CORRECT (needs AI)" if code is None else f"HAS TEMPLATE: {title}"
    print(f"  {inp}: {status}")

print("\nDONE")
