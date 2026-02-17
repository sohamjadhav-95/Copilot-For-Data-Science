# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines import _keyword_classify, extract_code, _clean_think_tags

# Test keyword classification (no API needed)
tests = [
    ("show 10 rows", "display"),
    ("show 5 rows", "display"),
    ("only 5", "chat"),  # without history, this is chat
    ("what is highest value in low column", "display"),
    ("what is the maximum of CLOSE", "display"),
    ("visualize the data", "visualize"),
    ("create a pie chart", "visualize"),
    ("plot scatter of OPEN vs HIGH", "visualize"),
    ("delete time column", "modify"),
    ("remove rows where CLOSE is null", "modify"),
    ("sort by date", "modify"),
    ("hello", "chat"),
    ("what is machine learning", "chat"),
]

print("Keyword Classification Tests:")
passed = 0
for inp, expected in tests:
    got = _keyword_classify(inp)
    ok = got == expected
    if ok: passed += 1
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: '{inp}' -> expected={expected}, got={got}")
print(f"  {passed}/{len(tests)} passed")

# Test think tag cleaning
print("\nThink Tag Cleaning:")
raw = "<think>some reasoning here\nmultiline</think>\n```python\nimport pandas as pd\ndf = pd.read_csv('test.csv')\n_result_df = df.head(5)\n```"
cleaned = _clean_think_tags(raw)
has_think = "<think>" in cleaned
has_code = "import pandas" in cleaned
print(f"  Has think tags: {has_think} (should be False)")
print(f"  Has code: {has_code} (should be True)")

# Test code extraction after think cleanup
code = extract_code(raw)
print(f"  Code extracted: {code is not None} (should be True)")
if code:
    print(f"  Code starts with import: {code.startswith('import')} (should be True)")

print("\nDONE")
