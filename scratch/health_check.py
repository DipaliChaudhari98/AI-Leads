import requests

BASE = "http://localhost:8000"

print("=" * 50)
print("BACKEND HEALTH CHECK")
print("=" * 50)

# 1. Backend reachability
try:
    r = requests.get(BASE + "/api/campaign-status", timeout=5)
    print("[OK] Backend is running - status:", r.status_code)
except Exception as e:
    print("[FAIL] Backend not reachable:", e)
    exit(1)

# 2. Stats endpoint
r = requests.get(BASE + "/api/stats", timeout=5)
if r.status_code == 200:
    d = r.json()
    print("[OK] /api/stats OK")
    print("     total_leads:", d.get("total_leads"))
    print("     total_emails:", d.get("total_emails_sent"))
else:
    print("[WARN] /api/stats status:", r.status_code, r.text[:100])

# 3. Try login credentials
creds_list = [
    ("admin@sigasystems.com", "admin123"),
    ("admin@sigasystems.com", "SiGaSystema@123"),
    ("admin@admin.com", "admin123"),
    ("ashlesha.p@sigasystems.com", "admin123"),
    ("admin@sigasystems.com", "password"),
]
token = None
for email, password in creds_list:
    r = requests.post(BASE + "/api/auth/login", json={"email": email, "password": password}, timeout=5)
    if r.status_code == 200:
        token = r.json().get("access_token")
        print("[OK] Login success:", email)
        break
    else:
        print("[FAIL] Login failed:", email, "->", r.status_code)

# 4. API endpoints with auth
if token:
    H = {"Authorization": "Bearer " + token}
    for path in ["/api/leads?page=1&limit=5", "/api/followups", "/api/emails"]:
        r = requests.get(BASE + path, headers=H, timeout=5)
        extra = ""
        if r.status_code == 200 and "total" in r.json():
            extra = " total=" + str(r.json()["total"])
        print("[OK]", path, "->", r.status_code, extra)
else:
    # Try without auth
    for path in ["/api/leads?page=1&limit=5", "/api/followups", "/api/emails"]:
        r = requests.get(BASE + path, timeout=5)
        print("[NO-AUTH]", path, "->", r.status_code)

# 5. Check Apify token
print("\n[INFO] Checking Apify token...")
token_check = requests.get(
    "https://api.apify.com/v2/users/me",
    headers={"Authorization": "Bearer YOUR_API_TOKEN"},
    timeout=10
)
if token_check.status_code == 200:
    username = token_check.json().get("data", {}).get("username", "unknown")
    print("[OK] Apify token valid - account:", username)
else:
    print("[FAIL] Apify token invalid - status:", token_check.status_code)

print("\n" + "=" * 50)
print("CHECK COMPLETE")
print("=" * 50)
