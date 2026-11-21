import requests

dataset_url = "https://api.apify.com/v2/actors/pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe/run-sync-get-dataset-items?token=YOUR_API_TOKEN"

payload = {
    "totalResults": 5,
    "companyLocationCountryIncludes": ["United States"],
    "personTitleIncludes": ["ceo and founder"],
    "companySizeIncludes": ["101,200"]
}

resp = requests.post(dataset_url, json=payload)
print("Status Code:", resp.status_code)
print("Response text:", resp.text[:1000])
