import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("APOLLO_API_KEY")
url = "https://api.apollo.io/api/v1/people/match?run_waterfall_email=true"

headers = {
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "accept": "application/json"
}

payload = {
    "api_key": key,
    "first_name": "Satya",
    "last_name": "Nadella",
    "domain": "microsoft.com"
}

try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
