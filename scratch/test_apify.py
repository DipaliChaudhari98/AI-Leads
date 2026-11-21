import requests
import json

dataset_url = "https://api.apify.com/v2/actors/pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe/run-sync-get-dataset-items?token=YOUR_API_TOKEN"

payload = {
    "totalResults": 1
}

resp = requests.post(dataset_url, json=payload)
print("Status Code:", resp.status_code)
print("Response text:", resp.text)
