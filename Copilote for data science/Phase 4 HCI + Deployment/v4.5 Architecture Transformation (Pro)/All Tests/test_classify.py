"""Quick test to verify keyword classifier routes chat queries correctly."""
from engines import _keyword_classify

tests = [
    # Chat queries (should NOT go to display)
    ("what is this data about", "chat"),
    ("tell me about this data", "chat"),
    ("explain this data", "chat"),
    ("describe the data in words", "chat"),
    ("in words", "chat"),
    ("what kind of data is this", "chat"),
    ("summarize in text", "chat"),
    ("tell me summary of data", "chat"),
    ("give me overview of this dataset", "chat"),
    ("what do you think about this data", "chat"),
    ("insights about this data", "chat"),
    
    # Display queries (should still go to display)
    ("show first 5 rows", "display"),
    ("summary statistics", "display"),
    ("describe", "display"),
    ("how many rows", "display"),
    ("what is max price", "display"),
    
    # Visualize queries
    ("plot histogram", "visualize"),
    ("scatter plot", "visualize"),
    
    # Modify queries
    ("add column price_diff", "modify"),
    ("drop column x", "modify"),
]

passed = 0
for query, expected in tests:
    result = _keyword_classify(query)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        print(f"  {status}: \"{query}\" -> {result} (expected {expected})")
    passed += 1 if result == expected else 0

print(f"\n{passed}/{len(tests)} tests passed")
if passed == len(tests):
    print("All tests passed!")
