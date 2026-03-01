# -*- coding: utf-8 -*-
"""Verify the new features work: code snippets API, alive responses, markdown rendering."""
import sys, os, json, requests
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:5000"
s = requests.Session()

# 1. Register a test user
print("=== REGISTER ===")
r = s.post(f"{BASE}/api/register", json={
    "username": "testuser", "email": "test@test.com", "password": "test1234"
})
if r.status_code in (201, 409):
    if r.status_code == 409:
        print("  User exists, logging in...")
        r = s.post(f"{BASE}/api/login", json={"login_id": "testuser", "password": "test1234"})
    print(f"  Auth: {r.status_code}")
else:
    print(f"  FAIL: {r.status_code} {r.text[:200]}")
    sys.exit(1)

# 2. Upload a CSV
print("\n=== UPLOAD CSV ===")
csv_path = None
upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
for root, dirs, files in os.walk(upload_dir):
    for f in files:
        if f.endswith(".csv"):
            csv_path = os.path.join(root, f)
            break
    if csv_path:
        break

if not csv_path:
    # Create a test CSV
    csv_path = os.path.join(upload_dir, "test.csv")
    os.makedirs(upload_dir, exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("date,open,high,low,close\n2024-01-01,100,110,95,105\n2024-01-02,105,115,100,112\n2024-01-03,112,120,108,118\n")
    print(f"  Created test CSV: {csv_path}")

with open(csv_path, "rb") as f:
    r = s.post(f"{BASE}/api/upload", files={"file": (os.path.basename(csv_path), f, "text/csv")})
    print(f"  Upload: {r.status_code}")
    data = r.json()
    session_id = data.get("dataset", {}).get("session_id")
    print(f"  Session ID: {session_id}")

if not session_id:
    print("  FAIL: No session ID")
    sys.exit(1)

# 3. Send a chat message (should trigger code generation + snippet saving)
print("\n=== CHAT: 'show first 5 rows' ===")
r = s.post(f"{BASE}/api/chat", json={"message": "show first 5 rows", "session_id": session_id})
data = r.json()
am = data.get("assistant_msg", {})
content = am.get("content", "")
result_type = am.get("result_type", "")
print(f"  Status: {r.status_code}")
print(f"  Content: {content[:120]}")
print(f"  Result Type: {result_type}")
print(f"  Has **bold**: {'PASS' if '**' in content else 'FAIL (no markdown)'}")

# 4. Check code snippets API
print("\n=== CODE SNIPPETS API ===")
r = s.get(f"{BASE}/api/code-snippets")
data = r.json()
snippets = data.get("snippets", [])
print(f"  Status: {r.status_code}")
print(f"  Snippet count: {len(snippets)}")
if snippets:
    s0 = snippets[0]
    print(f"  Latest: label='{s0['label']}', op='{s0['operation']}'")
    print(f"  Code preview: {s0['code'][:100]}...")
    print(f"  PASS: Code snippet saved!")
else:
    print(f"  FAIL: No snippets saved")

# 5. Check alive response variation
print("\n=== ALIVE RESPONSE VARIATION ===")
responses = set()
for i in range(3):
    r = s.post(f"{BASE}/api/chat", json={"message": f"show {i+1} rows", "session_id": session_id})
    am = r.json().get("assistant_msg", {})
    responses.add(am.get("content", ""))
print(f"  Unique responses from 3 queries: {len(responses)}")
print(f"  Varied: {'PASS' if len(responses) >= 2 else 'NEEDS MORE VARIETY'}")

print("\nDONE")
