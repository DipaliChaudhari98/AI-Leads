import requests
import time
import logging
from typing import List
from models.apollo import ApolloLead

logger = logging.getLogger(__name__)

import os

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "YOUR_API_TOKEN")
APIFY_ACTOR = "pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe"
APIFY_BASE  = "https://api.apify.com/v2"
# run-sync-get-dataset-items: runs actor synchronously and returns items inline
APIFY_SYNC_URL = (f"{APIFY_BASE}/actors/{APIFY_ACTOR}"
                  f"/run-sync-get-dataset-items?token={APIFY_TOKEN}")


class ApolloClient:
    def __init__(self, api_key: str = None):
        self.token = APIFY_TOKEN
        self.actor = APIFY_ACTOR

    def search_leads(self, company: str, title: str, limit: int = 1) -> List[ApolloLead]:
        """Fetch leads using Apify (simple wrapper)."""
        return self._fetch_apify_leads(limit=limit)

    def search_leads_advanced(self,
                              titles: List[str] = None,
                              locations: List[str] = None,
                              industries: List[str] = None,
                              companies: List[str] = None,
                              industry_tag_ids: List[str] = None,
                              employee_ranges: List[str] = None,
                              email_status: List[str] = None,
                              limit: int = 1,
                              filters: dict = None) -> List[ApolloLead]:
        """Fetch leads from Apify actor with filters."""
        print("Apify: Starting lead scrape run...")
        return self._fetch_apify_leads(
            titles=titles,
            locations=locations,
            industries=industries,
            companies=companies,
            employee_ranges=employee_ranges,
            limit=limit,
            filters=filters
        )

    def enrich_leads(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        """No-op for Apify since dataset already has emails."""
        return leads

    def _build_payload(self,
                       titles=None, locations=None, industries=None,
                       companies=None, employee_ranges=None,
                       limit=10, filters=None) -> dict:
        """Build the Apify actor input payload."""
        payload = {}
        if filters:
            payload.update(filters)

        payload["totalResults"] = limit

        if industries:
            cleaned = [i for i in industries if i]
            if cleaned:
                payload["companyKeywordIncludes"] = cleaned

        if locations:
            cleaned = [l for l in locations if l]
            if cleaned:
                payload["companyLocationCountryIncludes"] = cleaned

        if titles:
            cleaned = [t for t in titles if t]
            if cleaned:
                payload["personTitleIncludes"] = cleaned

        if companies:
            cleaned = [c for c in companies if c]
            if cleaned:
                payload["companyNameIncludes"] = cleaned

        if employee_ranges:
            # Apify only accepts exact values: "1-10","11-50","51-200","201-500",
            # "501-1000","1001-5000","5001-10000","10001+"
            VALID_SIZES = ["1-10","11-50","51-200","201-500","501-1000","1001-5000","5001-10000","10001+"]
            # Map common variants to valid values
            SIZE_MAP = {
                "1-10": "1-10",
                "11-50": "11-50",
                "51-200": "51-200",
                "51-100": "51-200",
                "100-200": "51-200",
                "200-500": "201-500",
                "201-500": "201-500",
                "500-1000": "501-1000",
                "501-1000": "501-1000",
                "1000-5000": "1001-5000",
                "1001-5000": "1001-5000",
                "5000-10000": "5001-10000",
                "5001-10000": "5001-10000",
                "10000+": "10001+",
                "10001+": "10001+",
            }
            mapped = []
            for r in employee_ranges:
                if not r:
                    continue
                normalized = SIZE_MAP.get(str(r).strip(), str(r).strip())
                if normalized in VALID_SIZES:
                    mapped.append(normalized)
                else:
                    logger.warning(f"Apify: Skipping invalid companySizeIncludes value: '{r}'")
            if mapped:
                payload["companySizeIncludes"] = mapped

        return payload

    def _parse_items(self, data: list, limit: int) -> List[ApolloLead]:
        """Parse raw Apify items into ApolloLead objects."""
        leads = []
        for item in data:
            if not isinstance(item, dict):
                continue
            # Skip metadata/summary rows
            row_type = item.get("rowType")
            if row_type and row_type != "lead":
                continue

            name = item.get("fullName") or item.get("name")
            if not name:
                fn = item.get("firstName", "") or ""
                ln = item.get("lastName", "") or ""
                name = f"{fn} {ln}".strip()

            email = (item.get("email") or item.get("workEmail")
                     or item.get("personalEmail") or item.get("contactEmail"))
            company = (item.get("companyName") or item.get("company")
                       or item.get("organizationName"))
            title = item.get("title") or item.get("personTitle") or item.get("headline") or "Lead"

            if not name or name.lower() == "unknown":
                continue
            if not company or company.lower() == "unknown":
                continue

            if not email or "@" not in str(email):
                clean_n = name.lower().replace(" ", "")
                clean_c = (company or "company").lower().replace(" ", "").replace(",", "")
                email = f"{clean_n}@{clean_c}.com"

            apollo_id = str(
                item.get("id") or item.get("personId")
                or item.get("linkedinUrl") or email
            )

            # companyIndustry may be a list or string
            raw_industry = item.get("companyIndustry") or ""
            if isinstance(raw_industry, list):
                industry_str = ", ".join(raw_industry)
            else:
                industry_str = str(raw_industry)

            leads.append(ApolloLead(
                name=name,
                email=email,
                company=company,
                title=title,
                apollo_id=apollo_id,
                linkedin_url=item.get("linkedinUrl") or item.get("personLinkedinUrl") or "",
                location=item.get("companyCountry") or item.get("personCountry") or "",
                apollo_location=item.get("companyCountry") or item.get("personCountry") or "",
                city=item.get("personCity") or item.get("companyCity") or "",
                state=item.get("personState") or item.get("companyState") or "",
                country=item.get("personCountry") or item.get("companyCountry") or "",
                timezone=item.get("timezone") or "",
                utc_offset=item.get("utcOffset") or "",
                skills=[],
                experience=[],
                raw_data={**item, "industry": industry_str},
            ))
            if len(leads) >= limit:
                break

        return leads

    def _fetch_apify_leads(self,
                           titles=None, locations=None, industries=None,
                           companies=None, employee_ranges=None,
                           limit: int = 10, filters: dict = None) -> List[ApolloLead]:
        """
        Fetches leads using Apify's run-sync-get-dataset-items endpoint.
        The actor runs synchronously and returns dataset items inline.
        Apify returns HTTP 201 (not 200) for this endpoint — both are treated as success.
        """
        payload = self._build_payload(titles, locations, industries, companies,
                                      employee_ranges, limit, filters)

        try:
            logger.info(f"Apify: POST run-sync-get-dataset-items | payload={payload}")
            resp = requests.post(APIFY_SYNC_URL, json=payload, timeout=180)

            # Apify returns 201 (not 200) for this endpoint — both indicate success
            if resp.status_code not in (200, 201):
                resp.raise_for_status()

            data = resp.json()
            if not isinstance(data, list):
                raise RuntimeError(f"Unexpected Apify response type: {type(data)}")

            raw_count = len(data)
            logger.info(f"Apify: Received {raw_count} raw items")

            leads = self._parse_items(data, limit)
            logger.info(f"Apify: Parsed {len(leads)} valid leads")
            print(f"Apify: Successfully scraped {len(leads)} leads.")
            return leads

        except Exception as e:
            logger.error(f"Apify API Error: {e}")
            raise e
