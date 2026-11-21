import requests

keys = [
    "HXwm9_VGH8XlrZ4UFfRHVg",
    "CtNAKM2mQNH5NEB-suzGsw",
    "KdERodBJj_znG2l6Dkoo_Q",
    "3wSexchKqTB9fDXXBcj3Q"
]

url = "https://api.apollo.io/api/v1/mixed_people/api_search"

for k in keys:
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "x-api-key": k
    }
    payload = {
        "page": 1,
        "per_page": 1
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Key {k[:5]}...: Status {response.status_code}")
        if response.status_code == 200:
            print(f"-> SUCCESS: Key {k} works!")
    except Exception as e:
        print(f"Key {k[:5]}...: Error {e}")
