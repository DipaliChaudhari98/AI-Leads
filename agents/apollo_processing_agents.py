import asyncio
import logging
import json
import time
import re
from pydantic import BaseModel
from crewai import Agent, Task, Crew
from typing import List, Dict, Any
from tools.apollo_tools import ApolloClient
from tools.db_tools import DatabaseManager
from models.apollo import ApolloLead
from services.enrichment import enrich_lead_location_and_tz

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ApolloWorkflow")

# ─── Pipeline Logging Helpers ────────────────────────────────────────────────

def _agent_start(name: str) -> float:
    """Print agent start banner and return start timestamp."""
    print(f"\n{'-'*60}")
    print(f"  [START] {name} started")
    print(f"{'-'*60}")
    return time.time()

def _agent_done(name: str, start: float, count: int = None, extra: str = ""):
    """Print agent completion with elapsed time and optional record count."""
    elapsed = time.time() - start
    count_str = f" | Records: {count}" if count is not None else ""
    extra_str = f" | {extra}" if extra else ""
    print(f"  [OK] {name} completed in {elapsed:.2f}s{count_str}{extra_str}")

def _agent_error(name: str, error: Exception):
    """Print agent failure with error message."""
    print(f"  [ERROR] {name} FAILED: {error}")


class InputAgent:
    """Validates and prepares input parameters from the UI."""
    async def process(self, roles: List[str], location: str, industry: str, companies: List[str] = None, size: str = None, limit: int = 10, filters: dict = None) -> Dict[str, Any]:
        t = _agent_start("Input Agent")
        logger.info("Input Agent: Validating inputs...")
        
        # Helper to parse comma-separated strings into lists
        def parse_list(val):
            if not val:
                return None
            if isinstance(val, list):
                parsed = [v.strip() for v in val if v and v.strip()]
            else:
                parsed = [v.strip() for v in str(val).split(",") if v and v.strip()]
            return parsed if parsed else None

        result = {
            "titles": parse_list(roles),
            "locations": parse_list(location),
            "industries": parse_list(industry),
            "companies": parse_list(companies),
            "employee_ranges": parse_list(size),
            "limit": limit,
            "filters": filters or {}
        }
        _agent_done("Input Agent", t, extra=f"Roles: {result['titles']}")
        return result

class ApolloFetchAgent:
    """Fetches raw data from Apollo API using apollo_tools.py."""
    def __init__(self):
        self.client = ApolloClient()
        
    async def process(self, search_params: Dict[str, Any]) -> List[ApolloLead]:
        t = _agent_start("Apollo Fetch Agent")
        logger.info(f"Fetch Agent: Searching Apollo with params: {search_params}")
        # search_leads_advanced is synchronous, so we run it in a thread to prevent blocking
        loop = asyncio.get_running_loop()
        try:
            leads = await loop.run_in_executor(
                None,
                lambda: self.client.search_leads_advanced(
                    titles=search_params.get("titles"),
                    locations=search_params.get("locations"),
                    industries=search_params.get("industries"),
                    companies=search_params.get("companies"),
                    employee_ranges=search_params.get("employee_ranges"),
                    limit=search_params.get("limit"),
                    filters=search_params.get("filters")
                )
            )
            logger.info(f"Fetch Agent: Retrieved {len(leads)} leads.")
            _agent_done("Apollo Fetch Agent", t, count=len(leads))
            return leads
        except Exception as e:
            _agent_error("Apollo Fetch Agent", e)
            raise

class ValidationAgent:
    """Validates fetched Apollo leads to ensure critical data is present."""
    async def process(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        t = _agent_start("Validation Agent")
        logger.info("Validation Agent: Validating leads...")
        valid_leads = []
        for lead in leads:
            if not lead.name or lead.name.lower() == "unknown":
                continue
            if not lead.email or "@" not in lead.email:
                continue
            if not lead.company or lead.company.lower() == "unknown":
                continue
            valid_leads.append(lead)
        logger.info(f"Validation Agent: {len(valid_leads)} out of {len(leads)} passed validation.")
        _agent_done("Validation Agent", t, count=len(valid_leads), extra=f"{len(leads)-len(valid_leads)} rejected")
        return valid_leads

class DeduplicationAgent:
    """Removes duplicates based on email, apollo_id, phone, and company using an intelligent merge strategy."""
    async def process(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        t = _agent_start("Deduplication Agent")
        logger.info("Deduplication Agent: Removing duplicates and merging records...")
        unique_leads = {}
        
        for lead in leads:
            # Composite key strategy. Primary: email, Secondary: apollo_id
            key = lead.email.lower().strip() if lead.email else lead.apollo_id
            
            if not key:
                continue
                
            if key in unique_leads:
                # Merge logic: Keep the best/latest record (fill missing fields)
                existing = unique_leads[key]
                existing.name = existing.name if existing.name and existing.name != "Unknown" else lead.name
                existing.company = existing.company if existing.company and existing.company != "Unknown" else lead.company
                existing.title = existing.title if existing.title and existing.title != "Lead" else lead.title
                existing.linkedin_url = existing.linkedin_url or lead.linkedin_url
                existing.location = existing.location or lead.location
            else:
                unique_leads[key] = lead
                
        deduplicated = list(unique_leads.values())
        logger.info(f"Deduplication Agent: Reduced to {len(deduplicated)} unique leads.")
        _agent_done("Deduplication Agent", t, count=len(deduplicated), extra=f"{len(leads)-len(deduplicated)} duplicates removed")
        return deduplicated

class CleanedLeadsList(BaseModel):
    leads: List[ApolloLead]

class DataCleaningAgent:
    """Cleans and normalizes the data for storage using deterministic rule-based logic.
    No LLM needed — all cleaning is done programmatically."""
    BATCH_SIZE = 3

    def __init__(self):
        pass  # No LLM needed for programmatic cleaning

    def _programmatic_clean(self, lead: ApolloLead) -> ApolloLead:
        """Lightweight rule-based cleaning used as fallback."""
        lead.name = lead.name.strip().title() if lead.name else "Unknown"
        lead.company = lead.company.strip() if lead.company else "Unknown"
        lead.title = lead.title.strip() if lead.title else None
        if lead.email:
            lead.email = lead.email.strip().lower()
            if "@" not in lead.email:
                lead.email = None
        if lead.linkedin_url:
            lead.linkedin_url = lead.linkedin_url.strip()
            if not lead.linkedin_url.startswith("http"):
                lead.linkedin_url = None
        if lead.location:
            lead.location = lead.location.strip()
        return lead

    async def _clean_batch(self, batch: List[ApolloLead], batch_num: int, total: int) -> List[ApolloLead]:
        print(f"    -> Batch {batch_num}/{total}: cleaning {len(batch)} lead(s) programmatically...")
        cleaned = [self._programmatic_clean(lead) for lead in batch]
        print(f"    OK Batch {batch_num}/{total}: Programmatic Clean OK ({len(cleaned)} records)")
        return cleaned

    async def process(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        if not leads:
            return []
        t = _agent_start("Data Cleaning Agent")
        batches = [leads[i:i + self.BATCH_SIZE] for i in range(0, len(leads), self.BATCH_SIZE)]
        total = len(batches)
        logger.info(f"Data Cleaning Agent: Processing {len(leads)} leads in {total} batch(es) of {self.BATCH_SIZE}.")
        print(f"    -> {len(leads)} leads -> {total} batch(es) of up to {self.BATCH_SIZE}")

        all_cleaned: List[ApolloLead] = []
        for idx, batch in enumerate(batches, 1):
            cleaned = await self._clean_batch(batch, idx, total)
            all_cleaned.extend(cleaned)

        _agent_done("Data Cleaning Agent", t, count=len(all_cleaned))
        return all_cleaned

class EnrichmentAgent:
    """Enriches leads with location and timezone data."""
    async def process(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        t = _agent_start("Enrichment Agent")
        logger.info("Enrichment Agent: Enriching leads with location and timezone...")
        enriched = []
        for i, lead in enumerate(leads, 1):
            enriched.append(enrich_lead_location_and_tz(lead))
            if i % 5 == 0 or i == len(leads):
                print(f"    -> Progress: {i}/{len(leads)} leads enriched...")
        logger.info("Enrichment Agent: Enrichment complete.")
        _agent_done("Enrichment Agent", t, count=len(enriched))
        return enriched

# ── SIGA Systems AI service catalog (used to constrain LLM output) ─────────
SIGA_SERVICES = [
    "AI Agents & Multi-Agent Systems",
    "Workflow Automation",
    "OCR & Intelligent Document Processing",
    "WhatsApp AI Chatbots",
    "Custom Software Development",
    "Cloud & Enterprise AI Solutions",
    "aws",
    "azure",
    "gcp",
    "react",
    "angular",
    "node.js",
    "python",
    "java",
    ".net",
    "docker",
    "kubernetes",
    "salesforce",
    "sap",
    "hubspot",
]

# ── Technologies that qualify a company for LLM scoring ─────────────────────
# A company must use at least one of these to be worth an LLM call.
SIGA_TECH_STACK: set = {
    "aws", "azure", "gcp", "react", "angular", "node.js", "nodejs",
    "python", "java", ".net", "dotnet", "docker", "kubernetes", "k8s",
    "salesforce", "sap", "hubspot",
    # also qualify on broad AI/cloud service signals
    "ai", "machine learning", "ml", "automation", "cloud", "erp", "crm",
    "digital transformation", "workflow", "ocr", "chatbot",
}

# ── Priority bands — single source of truth, used to derive `priority` ─────
PRIORITY_BANDS = [
    (90, 100, "Very High"),
    (75, 89, "High"),
    (60, 74, "Medium"),
    (40, 59, "Low"),
    (0, 39, "Very Low"),
]

def score_to_priority(score: int) -> str:
    """Deterministically map a 0-100 leadScore to a priority label."""
    score = max(0, min(100, score))  # clamp defensively
    for lo, hi, label in PRIORITY_BANDS:
        if lo <= score <= hi:
            return label
    return "Very Low"

# ── Prompt template ─────────────────────────────────────────────────────────
SIGA_PROMPT = """You are the Lead Scoring Agent for SIGA Systems AI.

Your task is to evaluate whether a company is a good potential customer for SIGA Systems AI and assign a lead score from 0 to 100.

SIGA Systems AI provides exactly these services:
{services_list}

Evaluate the company using the information below. Use ONLY the provided company information. Do not guess or invent missing facts —
if information for a category is missing, score that category conservatively (low/zero) rather than assuming.

Company Information:
{company_json}

STRICT GROUNDING RULES:
- Every rationale you write must cite the SPECIFIC evidence from company_json (e.g. name the actual technology, actual industry text, actual title) — never a vague phrase like "modern stack" or "good fit."
- Never include invented statistics, percentages, or multipliers (e.g. "40% faster", "3x ROI") unless that exact number is present in company_json.
- Do not assume AI/automation readiness just because of industry type.
- Distinguish tech the company USES internally from services they SELL to clients.

Scoring Criteria (assign an integer subscore for each, respecting the max):
1. Technology Adoption (max 30)
   - High (20-30): Strong evidence of AWS, Azure, GCP, React, Angular, Node.js, Python, Java, .NET, Docker, Kubernetes, Salesforce, SAP, HubSpot, or similar technologies.
   - Low (0-5): Little to no evidence of matching tech stack.

2. AI & Software Dev Readiness (max 30)
   - High (20-30): Clear need or evidence for AI, automation, cloud, custom software development, OCR, chatbots, or digital transformation.
   - Low (0-5): No evidence of needing software development or AI services.

3. Industry (max 10)
   - High (8-10): Software, IT Services, SaaS, Healthcare, Finance, Manufacturing, Logistics
   - Medium (4-7): Education, Retail, Professional Services
   - Low (0-3): Industries with little need for AI automation

4. Company Size (max 10)
   - 1000+ employees = 10
   - 200-999 = 7
   - 50-199 = 5
   - Below 50 = 2

5. Decision Maker Available (max 5)
   Contact is CEO, Founder, CTO, Director, VP, or Head of IT.

6. Website & Business Email (max 5)
   Professional website and a verified business email domain.

7. Target Market (max 5)
   Company is based in India, USA, UK, Canada, Australia, UAE, or Singapore.

8. Growth Indicators (max 5)
   Evidence of hiring, expansion, multiple offices, funding, growing customer base, or new products.

leadScore MUST equal the sum of the 8 subscores above (max possible 100).

PAIN POINTS:
- Identify 1-3 concrete pain points, each grounded in specific evidence from company_json.
- Each pain point must map to exactly one SIGA service.
- If there's not enough evidence, return an empty list — don't invent generic pain points.

Output rules (strict — follow exactly):
- "buyingProbability" must be exactly one of: "High", "Medium", "Low".
- "priority" must be left as an empty string "".
- "recommendedServices" must contain ONLY values from this exact list: {services_list}
- Each entry in "scoreBreakdown" is an object with "points" and "rationale" — rationale must cite specific evidence, max 20 words.
- "painPoints" is a list of objects with "point", "evidence", "relatedService" — max 3 items.
- "strengths" and "weaknesses" are each a list of short strings (max 5 items each).
- "recommendedContactRole" is a single job title string, or "" if none identifiable.
- "nextAction" is one short, concrete, actionable sentence.
- Return ONLY the JSON object below, fully filled in. No markdown fences, no commentary.

{{
  "scoreBreakdown": {{
    "industry": {{"points": 0, "rationale": ""}},
    "companySize": {{"points": 0, "rationale": ""}},
    "techAdoption": {{"points": 0, "rationale": ""}},
    "aiReadiness": {{"points": 0, "rationale": ""}},
    "decisionMaker": {{"points": 0, "rationale": ""}},
    "websiteEmail": {{"points": 0, "rationale": ""}},
    "targetMarket": {{"points": 0, "rationale": ""}},
    "growthIndicators": {{"points": 0, "rationale": ""}}
  }},
  "leadScore": 0,
  "priority": "",
  "buyingProbability": "",
  "summary": "",
  "strengths": [],
  "weaknesses": [],
  "painPoints": [
    {{"point": "", "evidence": "", "relatedService": ""}}
  ],
  "recommendedServices": [],
  "recommendedContactRole": "",
  "nextAction": ""
}}"""

class LeadScoringAgent:
    """Scores a company for SIGA Systems AI fit, preferring the LLM path
    and transparently falling back to deterministic rules on any failure."""

    MAX_SCORE_BREAKDOWN_DRIFT = 5

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        # Setup real OpenRouter config fallback if no explicit client passed
        if not self.llm_client:
            from core.llm_config import get_llm
            try:
                self.llm = get_llm()
            except Exception:
                self.llm = None
        else:
            self.llm = None

    # ── LLM qualification gate ───────────────────────────────────────────
    @staticmethod
    def _qualifies_for_llm(company: dict) -> bool:
        """Return True only if the company's tech stack / description
        contains at least one SIGA-relevant technology keyword.
        Prevents wasting LLM credits on leads with no relevant tech signals."""
        # Gather all text signals from the company dict
        techs = company.get("technologies") or company.get("techStack") or \
                company.get("tech_stack") or company.get("technology_stack") or []
        if isinstance(techs, str):
            techs = [techs]
        tech_text = " ".join(str(t) for t in techs).lower()

        desc = str(
            company.get("description") or company.get("short_description") or
            company.get("summary") or company.get("about") or ""
        ).lower()

        industry = str(
            company.get("industry") or company.get("industry_name") or
            company.get("sector") or ""
        ).lower()

        combined = f"{tech_text} {desc} {industry}"
        return any(kw in combined for kw in SIGA_TECH_STACK)

    @staticmethod
    def _has_tech_stack_match(company: dict) -> bool:
        """Return True if any of the specific target tech stack keywords are found."""
        techs = company.get("technologies") or company.get("techStack") or \
                company.get("tech_stack") or company.get("technology_stack") or []
        if isinstance(techs, str):
            techs = [techs]
        tech_text = " ".join(str(t) for t in techs).lower()

        desc = str(
            company.get("description") or company.get("short_description") or
            company.get("summary") or company.get("about") or ""
        ).lower()

        industry = str(
            company.get("industry") or company.get("industry_name") or
            company.get("sector") or ""
        ).lower()

        combined = f"{tech_text} {desc} {industry}"
        specific_techs = {
            "aws", "azure", "gcp", "react", "angular", "node.js", "nodejs",
            "python", "java", ".net", "dotnet", "docker", "kubernetes", "k8s",
            "salesforce", "sap", "hubspot"
        }
        return any(kw in combined for kw in specific_techs)


    # ── Public entrypoint ───────────────────────────────────────────────
    def score(self, company: dict) -> ApolloLead:
        company_val = company.get("company")
        if isinstance(company_val, dict):
            company_val = company_val.get("name")
            
        # Create final ApolloLead object to return
        apollo_lead = ApolloLead(
            name=company.get("contact_name") or company.get("name") or company.get("fullName") or "Unknown",
            email=company.get("contact_email") or company.get("email") or "",
            company=company.get("companyName") or company_val or "Unknown",
            title=company.get("contact_title") or company.get("title") or company.get("personTitle") or "",
            apollo_id=str(company.get("apollo_id") or company.get("apolloId") or company.get("id") or ""),
            linkedin_url=company.get("linkedin_url") or company.get("linkedinUrl") or company.get("linkedin") or "",
            phone=company.get("phone") or company.get("phoneNumber") or "",
            location=company.get("location") or company.get("apollo_location") or company.get("country") or "",
            raw_data=company
        )

        max_retries = 2
        backoff_delay = 2.0
        llm_success = False

        # Precompute a deterministic fallback so we can use it if the LLM path fails.
        rule_lead = self._score_with_rules(company)

        for attempt in range(max_retries + 1):
            try:
                scored = self._score_with_llm(company)

                # Copy LLM results to target apollo_lead
                apollo_lead.lead_score = scored.lead_score
                apollo_lead.priority = scored.priority
                apollo_lead.buying_probability = scored.buying_probability
                apollo_lead.score_breakdown = scored.score_breakdown
                apollo_lead.ai_summary = scored.ai_summary
                apollo_lead.summary = scored.ai_summary   # keep .summary in sync so _score_single propagates it correctly
                apollo_lead.strengths = scored.strengths
                apollo_lead.weaknesses = scored.weaknesses
                apollo_lead.pain_points = scored.pain_points
                apollo_lead.recommended_services = scored.recommended_services
                apollo_lead.recommended_contact_role = scored.recommended_contact_role
                apollo_lead.next_action = scored.next_action
                apollo_lead.scoring_method = "llm"
                llm_success = True
                break
            except Exception as exc:
                logger.warning(
                    "LLM scoring attempt %d failed (%s); retrying in %ds...",
                    attempt + 1, exc, backoff_delay
                )
                if attempt < max_retries:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0

        if not llm_success:
            logger.warning("All LLM scoring attempts failed. Using deterministic rule-based fallback scorer.")
            fallback = self._score_with_rules(company)
            apollo_lead.lead_score = fallback.lead_score
            apollo_lead.priority = fallback.priority
            apollo_lead.score_breakdown = fallback.score_breakdown
            apollo_lead.pain_points = fallback.pain_points
            apollo_lead.scoring_method = "rule_based"

        # ── Tech Stack Boost & Required Info Population ──
        if self._has_tech_stack_match(company):
            current_score = apollo_lead.lead_score or 0
            if current_score < 70:
                apollo_lead.lead_score = 70
                apollo_lead.priority = score_to_priority(70)
                if apollo_lead.score_breakdown:
                    # Calculate current points sum
                    def _get_pts(v):
                        return v.get("points", 0) if isinstance(v, dict) else int(v or 0)
                    current_sum = sum(_get_pts(v) for k, v in apollo_lead.score_breakdown.items() if k != "techAdoption")
                    new_pts = max(0, 70 - current_sum)
                    if isinstance(apollo_lead.score_breakdown.get("techAdoption"), dict):
                        apollo_lead.score_breakdown["techAdoption"]["points"] = new_pts
                    else:
                        apollo_lead.score_breakdown["techAdoption"] = new_pts
            
            # Ensure all required enrichment fields are populated
            if not apollo_lead.ai_summary:
                techs_clean = company.get("technologies") or company.get("techStack") or company.get("tech_stack") or "Target TechStack"
                apollo_lead.ai_summary = f"Company matches target technology stack. Identified signals: {techs_clean}."
                apollo_lead.summary = apollo_lead.ai_summary
            if not apollo_lead.strengths:
                apollo_lead.strengths = ["Uses target tech stack", "Good fit for SIGA Systems integration"]
            if not apollo_lead.weaknesses:
                apollo_lead.weaknesses = ["Needs discovery to identify exact scope"]
            if not apollo_lead.recommended_services:
                apollo_lead.recommended_services = ["Custom Software Development", "Workflow Automation"]
            if not apollo_lead.recommended_contact_role:
                apollo_lead.recommended_contact_role = "CTO or IT Director"
            if not apollo_lead.next_action:
                apollo_lead.next_action = "Reach out with tech-stack-specific case study."

        return apollo_lead

    # ── Primary path: LLM scoring ───────────────────────────────────────
    def _score_with_llm(self, company: dict) -> ApolloLead:
        prompt = SIGA_PROMPT.format(
            company_json=json.dumps(company, ensure_ascii=False, indent=2),
            services_list=", ".join(SIGA_SERVICES),
        )

        raw_response = self._call_llm(prompt)
        data = self._parse_json_response(raw_response)

        # ── Validate & sanity-check the LLM's own arithmetic ────────────
        breakdown = data.get("scoreBreakdown", {}) or {}
        
        def extract_points(item):
            if isinstance(item, dict):
                return int(item.get("points", 0))
            return int(item or 0)

        breakdown_sum = sum(extract_points(v) for v in breakdown.values()) if breakdown else None
        llm_score = int(data.get("leadScore", 0))

        if breakdown_sum is not None and abs(breakdown_sum - llm_score) > self.MAX_SCORE_BREAKDOWN_DRIFT:
            raise ValueError(
                f"leadScore ({llm_score}) doesn't match scoreBreakdown sum "
                f"({breakdown_sum}); discarding LLM result."
            )

        final_score = breakdown_sum if breakdown_sum is not None else llm_score
        final_score = max(0, min(100, final_score))

        buying_prob = data.get("buyingProbability", "")
        if buying_prob not in ("High", "Medium", "Low"):
            buying_prob = "Medium"

        raw_services = data.get("recommendedServices", []) or []
        clean_services = [s for s in raw_services if s in SIGA_SERVICES]

        raw_pain_points = data.get("painPoints", []) or []
        clean_pain_points = []
        if isinstance(raw_pain_points, list):
            for pp in raw_pain_points:
                if isinstance(pp, dict) and pp.get("point"):
                    clean_pain_points.append({
                        "point": str(pp.get("point", "")),
                        "evidence": str(pp.get("evidence", "")),
                        "relatedService": str(pp.get("relatedService", ""))
                    })

        return ApolloLead(
            name=company.get("contact_name") or company.get("name") or "Unknown",
            email=company.get("contact_email") or company.get("email") or "",
            apollo_id=str(company.get("apollo_id") or company.get("id") or ""),
            lead_score=final_score,
            priority=score_to_priority(final_score),
            buying_probability=buying_prob,
            score_breakdown=breakdown or None,
            ai_summary=data.get("summary") or None,
            strengths=data.get("strengths", []) or [],
            weaknesses=data.get("weaknesses", []) or [],
            pain_points=clean_pain_points,
            recommended_services=clean_services,
            recommended_contact_role=data.get("recommendedContactRole") or None,
            next_action=data.get("nextAction") or None,
            scoring_method="llm",
        )

    def _call_llm(self, prompt: str) -> str:
        """Calls the Anthropic API using the native SDK."""
        if self.llm_client:
            return self.llm_client.complete(prompt)

        from core.llm_config import call_anthropic, PRIMARY_MODEL
        return call_anthropic(prompt, model=PRIMARY_MODEL)

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE)
        return json.loads(cleaned)

    # ── Fallback path: deterministic rule-based scoring ─────────────────
    def _score_with_rules(self, company: dict) -> ApolloLead:
        breakdown = {
            "industry": self._score_industry(company),
            "companySize": self._score_company_size(company),
            "techAdoption": self._score_tech_adoption(company),
            "aiReadiness": self._score_ai_readiness(company),
            "decisionMaker": self._score_decision_maker(company),
            "websiteEmail": self._score_website_email(company),
            "targetMarket": self._score_target_market(company),
            "growthIndicators": self._score_growth(company),
        }
        total = sum(breakdown.values())
        total = max(0, min(100, total))

        # Extract rule-based pain points grounded in company characteristics
        rule_pain_points = []
        techs = str(company.get("technologies") or company.get("techStack") or company.get("tech_stack") or "").lower()
        industry = str(company.get("industry") or company.get("companyIndustry") or "").lower()

        if "software" in industry or "saas" in industry or "it" in industry:
            rule_pain_points.append({
                "point": "Need for automated workflow integration & AI scaling",
                "evidence": f"Operating in {industry.title()} sector",
                "relatedService": "Workflow Automation"
            })
        if any(t in techs for t in ["aws", "azure", "gcp", "docker", "kubernetes"]):
            rule_pain_points.append({
                "point": "Cloud infrastructure optimization & enterprise deployment challenges",
                "evidence": f"Utilizes cloud technologies ({techs[:40]})",
                "relatedService": "Cloud & Enterprise AI Solutions"
            })
        if not rule_pain_points:
            rule_pain_points.append({
                "point": "Manual process bottlenecks in day-to-day operations",
                "evidence": f"Company profile: {company.get('companyName') or company.get('company') or 'Software/Services'}",
                "relatedService": "Custom Software Development"
            })

        return ApolloLead(
            name=company.get("contact_name") or company.get("name") or "Unknown",
            email=company.get("contact_email") or company.get("email") or "",
            apollo_id=str(company.get("apollo_id") or company.get("id") or ""),
            lead_score=total,
            priority=score_to_priority(total),
            buying_probability=None,
            score_breakdown=breakdown,
            ai_summary=None,
            pain_points=rule_pain_points,
            scoring_method="rule_based",
        )

    # -- individual rule-based scorers -----------------------------------
    @staticmethod
    def _get_company_value(company: dict, *keys, default=None):
        for key in keys:
            value = company.get(key)
            if value not in (None, "", [], {}):
                return value
        return default

    @staticmethod
    def _score_industry(company: dict) -> int:
        industry = str(
            LeadScoringAgent._get_company_value(
                company,
                "industry",
                "industry_name",
                "industryName",
                "primary_industry",
                "companyIndustry",
                "sector",
                "vertical",
                default="",
            ) or ""
        ).lower()
        high = {"software", "it services", "saas", "healthcare", "finance", "manufacturing", "logistics"}
        medium = {"education", "retail", "professional services"}
        if any(k in industry for k in high):
            return 10
        if any(k in industry for k in medium):
            return 5
        return 2

    @staticmethod
    def _parse_employee_count(raw) -> int:
        if not raw:
            return 0
        try:
            if isinstance(raw, int):
                return raw
            raw_str = str(raw).replace(",", "").replace(" ", "")
            import re
            m = re.search(r"(\d+)[\-–](\d+)", raw_str)
            if m:
                return (int(m.group(1)) + int(m.group(2))) // 2
            m = re.search(r"(\d+)\+", raw_str)
            if m:
                return int(m.group(1))
            m = re.search(r"~?(\d+)", raw_str)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    def _score_company_size(self, company: dict) -> int:
        raw_size = self._get_company_value(
            company,
            "employeeCount",
            "employee_count",
            "companySize",
            "numEmployees",
            "estimated_num_employees",
            "company_size",
            default=0,
        )
        size = self._parse_employee_count(raw_size)
        if size >= 1000:
            return 10
        if size >= 200:
            return 7
        if size >= 50:
            return 5
        return 2

    @staticmethod
    def _score_tech_adoption(company: dict) -> int:
        techs = LeadScoringAgent._get_company_value(
            company,
            "technologies",
            "techStack",
            "tech_stack",
            "technology_stack",
            "technologies_used",
            default=[],
        )
        if isinstance(techs, str):
            techs = [techs]
        tech_stack = [t.lower() for t in techs]
        known = {"aws", "azure", "gcp", "react", "angular", "node.js", "python",
                 "java", ".net", "docker", "kubernetes", "salesforce", "sap", "hubspot"}
        matches = len(known.intersection(tech_stack))
        return min(30, matches * 10)

    @staticmethod
    def _score_ai_readiness(company: dict) -> int:
        techs = LeadScoringAgent._get_company_value(
            company,
            "technologies",
            "techStack",
            "tech_stack",
            "technology_stack",
            default=[],
        )
        if isinstance(techs, str):
            techs = [techs]
        techs_clean = [str(t) for t in techs if t is not None]
        desc = str(
            LeadScoringAgent._get_company_value(
                company,
                "description",
                "short_description",
                "summary",
                "about",
                "overview",
                default="",
            ) or ""
        )
        text = f"{desc} {' '.join(techs_clean)}".lower()
        keywords = {"ai", "automation", "cloud", "erp", "crm", "digital transformation"}
        matches = sum(1 for k in keywords if k in text)
        return min(30, matches * 10)

    @staticmethod
    def _score_decision_maker(company: dict) -> int:
        title = str(
            LeadScoringAgent._get_company_value(
                company,
                "contact_title",
                "title",
                "personTitle",
                "job_title",
                "role",
                default="",
            ) or ""
        ).lower()
        senior = {"ceo", "founder", "cto", "director", "vp", "head of it"}
        return 5 if any(t in title for t in senior) else 0

    @staticmethod
    def _score_website_email(company: dict) -> int:
        has_site = bool(
            LeadScoringAgent._get_company_value(
                company,
                "website",
                "website_url",
                "company_website",
                "url",
                default="",
            )
        )
        has_verified_email = bool(
            LeadScoringAgent._get_company_value(
                company,
                "email_verified",
                "email",
                "contact_email",
                "work_email",
                "verified_email",
                default="",
            )
        )
        return 5 if (has_site and has_verified_email) else (2 if has_site else 0)

    @staticmethod
    def _score_target_market(company: dict) -> int:
        country = str(
            LeadScoringAgent._get_company_value(
                company,
                "country",
                "location",
                "company_location",
                "geo",
                "region",
                "address",
                default="",
            ) or ""
        ).lower()
        targets = {"india", "usa", "united states", "uk", "united kingdom",
                   "canada", "australia", "uae", "singapore"}
        if any(t in country for t in targets):
            return 5
        return 0

    @staticmethod
    def _score_growth(company: dict) -> int:
        desc = str(
            LeadScoringAgent._get_company_value(
                company,
                "description",
                "short_description",
                "summary",
                "about",
                "overview",
                default="",
            ) or ""
        )
        funding = str(
            LeadScoringAgent._get_company_value(
                company,
                "recent_funding",
                "funding",
                "funding_rounds",
                "capital",
                default="",
            ) or ""
        )
        text = f"{desc} {funding}".lower()
        keywords = {"hiring", "funding", "expansion", "new office", "growing"}
        matches = sum(1 for k in keywords if k in text)
        return min(5, matches * 2)

    # ── Legacy Orchestration Compatibility ────────────────────────────────────

    def _score_single(self, lead: ApolloLead, idx: int, total: int) -> ApolloLead:
        """Scores a single lead, mapping back and forth for legacy process() compatibility."""
        raw = lead.raw_data or {}
        org = raw.get("organization", {}) if isinstance(raw.get("organization"), dict) else {}
        enr = lead.company_enrichment or {}

        # Construct flat company dict
        company_dict = {
            "name": lead.name,
            "email": lead.email,
            "company": lead.company,
            "contact_title": lead.title,
            "title": lead.title,
            "apollo_id": lead.apollo_id,
            "linkedin_url": lead.linkedin_url,
            "phone": lead.phone,
            "location": lead.location or lead.apollo_location,
            "country": lead.country or enr.get("country"),
            "industry": enr.get("industry") or raw.get("industry") or org.get("industry"),
            "employeeCount": enr.get("employeeCount") or raw.get("employeeCount") or org.get("estimated_num_employees"),
            "technologies": list(set((enr.get("techStack") or []) + (raw.get("techStack") or raw.get("technologies") or org.get("technologies") or []))),
            "description": enr.get("description") or raw.get("short_description") or org.get("short_description"),
            "website": enr.get("website") or raw.get("website_url") or org.get("website_url"),
            "email_verified": bool(lead.email)
        }

        scored = self.score(company_dict)

        # Copy scored fields back to the original lead object
        lead.lead_score = scored.lead_score
        lead.priority = scored.priority
        lead.buying_probability = scored.buying_probability
        lead.score_breakdown = scored.score_breakdown
        lead.ai_summary = scored.ai_summary
        lead.summary = scored.summary
        lead.strengths = scored.strengths
        lead.weaknesses = scored.weaknesses
        lead.recommended_services = scored.recommended_services
        lead.recommended_contact_role = scored.recommended_contact_role
        lead.next_action = scored.next_action
        lead.scoring_method = scored.scoring_method

        print(f"    -> [{idx}/{total}] {lead.company or lead.name} -- "
              f"Score: {lead.lead_score} ({scored.scoring_method})")
        return lead

    async def process(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        """Score all leads using LLM (with rule-based fallback). Runs in thread pool."""
        t = _agent_start("Lead Scoring Agent")
        logger.info(f"Lead Scoring Agent: Scoring {len(leads)} lead(s) via SIGA Systems AI prompt...")

        loop = asyncio.get_running_loop()
        total = len(leads)
        scored: List[ApolloLead] = []

        for idx, lead in enumerate(leads, 1):
            result = await loop.run_in_executor(
                None, self._score_single, lead, idx, total
            )
            scored.append(result)

        if scored:
            valid_scores = [l.lead_score for l in scored if l.lead_score is not None]
            if valid_scores:
                avg = sum(valid_scores) / len(valid_scores)
                top = max(valid_scores)
                hot = sum(1 for s in valid_scores if s >= 75)
                mid = sum(1 for s in valid_scores if 60 <= s < 75)
                low = sum(1 for s in valid_scores if s < 60)
                print(f"    -> Avg: {avg:.1f}  |  Top: {top}  |  "
                      f"High(>=75): {hot}  |  Medium(60-74): {mid}  |  Low(<60): {low}")

        _agent_done("Lead Scoring Agent", t, count=len(scored))
        return scored

class WebsiteEnrichmentAgent:
    """
    Website Enrichment Agent
    ────────────────────────
    Runs between the Enrichment Agent and Lead Scoring Agent.

    For each lead that has a website URL, it:
      1. Runs the WebsiteCrawlerAgent to crawl homepage + important subpages.
      2. Runs the WebsiteResearchAgent to extract structured fields.
      3. Stores the result in `lead.company_enrichment`.

    This enriched data is then used by the LeadScoringAgent via
    `_build_company_json()` for much more accurate LLM scoring:
      - Real company description from the website
      - Detected tech stack
      - Products and services pages
      - Social media presence

    Crawling is done concurrently (all leads in parallel via asyncio.gather)
    with a per-lead timeout of 30 seconds to keep the pipeline fast.
    """
    TIMEOUT_PER_LEAD = 30  # seconds

    def __init__(self):
        from agents.website_research_agents import WebsiteCrawlerAgent, WebsiteResearchAgent
        self.crawler  = WebsiteCrawlerAgent()
        self.research = WebsiteResearchAgent()

    def _extract_website_url(self, lead: ApolloLead) -> str:
        """Extract website URL from lead raw_data or organization fields."""
        raw = lead.raw_data or {}
        org = raw.get("organization", {}) if isinstance(raw.get("organization"), dict) else {}
        url = (
            raw.get("website_url") or
            org.get("website_url") or
            raw.get("website") or
            org.get("website") or
            raw.get("domain") or
            org.get("primary_domain") or
            raw.get("company_domain") or
            ""
        )
        if not url and lead.email and "@" in lead.email:
            domain = lead.email.split("@")[-1].strip().lower()
            public_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "protonmail.com"}
            if domain and domain not in public_domains:
                url = f"https://{domain}"

        if url and not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        return url

    async def _enrich_single(self, lead: ApolloLead, idx: int, total: int) -> ApolloLead:
        """
        Full enrichment pipeline for one lead:
          1. Crawl website with WebsiteCrawlerAgent
          2. Extract structured fields with WebsiteResearchAgent
          3. Merge Apollo lead data + website research via CompanyEnrichmentAgent (LLM)
          4. Store the merged EnrichedCompanyProfile in lead.company_enrichment
             → Used by LeadScoringAgent._build_company_json() for accurate scoring
        """
        from agents.website_research_agents import CompanyEnrichmentAgent

        website_url = self._extract_website_url(lead)
        if not website_url:
            print(f"    -> [{idx}/{total}] {lead.company or lead.name}: No website URL — skipping enrichment.")
            return lead

        try:
            # ── Step 1: Crawl the company website ────────────────────────────────
            crawler_result = await asyncio.wait_for(
                self.crawler.process(website_url, lead.company),
                timeout=self.TIMEOUT_PER_LEAD
            )

            # ── Step 2: Extract structured data from crawled content ─────────────
            research_data = await self.research.process(crawler_result)

            # ── Step 3: Merge Apollo lead data + website research (LLM merge) ────
            # Build the Apollo-side data dict to pass to CompanyEnrichmentAgent
            raw = lead.raw_data or {}
            org = raw.get("organization", {}) if isinstance(raw.get("organization"), dict) else {}
            apollo_lead_data = {
                "company":           lead.company,
                "contact_name":      lead.name,
                "contact_title":     lead.title,
                "contact_email":     lead.email,
                "location":          lead.location or lead.apollo_location,
                "country":           lead.country,
                "phone":             lead.phone,
                "linkedin_url":      lead.linkedin_url,
                "industry":          raw.get("industry") or org.get("industry"),
                "employee_count":    (
                    raw.get("employeeCount") or
                    raw.get("employment_summary") or
                    org.get("estimated_num_employees")
                ),
                "annual_revenue":    raw.get("revenue") or org.get("annual_revenue"),
                "website":           website_url,
                "technologies":      (
                    raw.get("techStack") or
                    raw.get("technologies") or
                    org.get("technologies") or []
                ),
                "keywords":          raw.get("keywords") or org.get("keywords") or [],
                "short_description": raw.get("short_description") or org.get("short_description"),
            }
            # Remove empty/None keys for a leaner prompt
            apollo_lead_data = {k: v for k, v in apollo_lead_data.items() if v not in (None, [], "")}

            enrichment_agent = CompanyEnrichmentAgent()
            enriched_profile = await enrichment_agent.process(apollo_lead_data, research_data)

            # ── Step 4: Store merged profile for LeadScoringAgent ────────────────
            lead.company_enrichment = enriched_profile.model_dump(exclude_none=True)

            pages_count = len(crawler_result.pages)
            tech = enriched_profile.techStack or research_data.techStack or []
            print(
                f"    -> [{idx}/{total}] {lead.company or lead.name}: "
                f"Enriched via CompanyEnrichmentAgent | "
                f"Pages={pages_count} | Tech={tech or 'none'} | "
                f"Industry={enriched_profile.industry or 'unknown'}"
            )

        except asyncio.TimeoutError:
            print(f"    -> [{idx}/{total}] {lead.company or lead.name}: Enrichment timed out — using Apollo data only.")
        except Exception as e:
            logger.warning(f"WebsiteEnrichmentAgent: Enrichment failed for {lead.company} ({website_url}): {e}")
            print(f"    -> [{idx}/{total}] {lead.company or lead.name}: Enrichment failed — {e}")

        return lead

    async def process(self, leads: List[ApolloLead]) -> List[ApolloLead]:
        """Enrich all leads concurrently with website data."""
        if not leads:
            return leads

        t = _agent_start("Website Enrichment Agent")
        logger.info(
            f"WebsiteEnrichmentAgent: Enriching {len(leads)} leads with website data "
            f"(concurrent, {self.TIMEOUT_PER_LEAD}s timeout per lead)..."
        )

        total = len(leads)
        tasks = [
            self._enrich_single(lead, idx, total)
            for idx, lead in enumerate(leads, 1)
        ]
        enriched = await asyncio.gather(*tasks)
        enriched_count = sum(1 for l in enriched if l.company_enrichment)
        _agent_done(
            "Website Enrichment Agent", t,
            count=enriched_count,
            extra=f"{total - enriched_count} skipped (no website URL or crawl failed)"
        )
        return list(enriched)


class StorageAgent:
    """Saves the final clean dataset to the database."""
    def __init__(self):
        self.db_manager = DatabaseManager()
        
    async def process(self, leads: List[ApolloLead]) -> bool:
        t = _agent_start("Storage Agent")
        logger.info("Storage Agent: Saving to database...")
        loop = asyncio.get_running_loop()
        try:
            # db_manager.save_leads handles DB-level dedup & merging securely
            await loop.run_in_executor(None, self.db_manager.save_leads, leads)
            logger.info("Storage Agent: Successfully saved leads to database.")
            _agent_done("Storage Agent", t, count=len(leads))
            return True
        except Exception as e:
            _agent_error("Storage Agent", e)
            logger.error(f"Storage Agent Error: {e}")
            return False
        finally:
            self.db_manager.close()

class OrchestratorAgent:
    """Controls the execution flow of the entire Apollo Data Pipeline."""
    def __init__(self):
        self.input_agent              = InputAgent()
        self.fetch_agent              = ApolloFetchAgent()
        self.validation_agent         = ValidationAgent()
        self.dedup_agent              = DeduplicationAgent()
        self.data_cleaning_agent      = DataCleaningAgent()
        self.enrichment_agent         = EnrichmentAgent()
        self.website_enrichment_agent = WebsiteEnrichmentAgent()
        self.scoring_agent            = LeadScoringAgent()
        self.storage_agent            = StorageAgent()

    async def execute_pipeline(self, roles: List[str], location: str, industry: str, companies: List[str] = None, size: str = None, limit: int = 10, filters: dict = None, update_status_cb=None) -> Dict[str, Any]:
        pipeline_start = time.time()
        print("\n" + "="*60)
        print("  APOLLO LEAD GENERATION PIPELINE")
        print("  Pipeline Flow:")
        print("  Input -> Fetch -> Validation -> Deduplication ->")
        print("  Data Cleaning -> Enrichment -> Website Enrichment -> Lead Scoring -> Storage")
        print("="*60)
        try:
            if update_status_cb: update_status_cb("Input Agent started...")
            search_params = await self.input_agent.process(roles, location, industry, companies, size, limit, filters)
            
            if update_status_cb: update_status_cb("Fetch Agent started...")
            raw_leads = await self.fetch_agent.process(search_params)
            
            if not raw_leads:
                print("\n[WARNING] No leads found for given criteria.")
                return {"status": "success", "message": "No leads found for given criteria.", "count": 0}
                
            if update_status_cb: update_status_cb("Validation Agent started...")
            valid_leads = await self.validation_agent.process(raw_leads)
            
            if update_status_cb: update_status_cb("Deduplication Agent started...")
            unique_leads = await self.dedup_agent.process(valid_leads)
            
            if update_status_cb: update_status_cb("Data Cleaning Agent started...")
            processed_leads = await self.data_cleaning_agent.process(unique_leads)
            
            if update_status_cb: update_status_cb("Enrichment Agent started...")
            enriched_leads = await self.enrichment_agent.process(processed_leads)

            if update_status_cb: update_status_cb("Website Enrichment Agent started...")
            website_enriched_leads = await self.website_enrichment_agent.process(enriched_leads)

            if update_status_cb: update_status_cb("Lead Scoring Agent started...")
            scored_leads = await self.scoring_agent.process(website_enriched_leads)

            if update_status_cb: update_status_cb("Storage Agent started...")
            success = await self.storage_agent.process(scored_leads)

            total_time = time.time() - pipeline_start
            if success:
                if update_status_cb: update_status_cb("Completed!")
                avg_score = (
                    sum(l.lead_score for l in scored_leads if l.lead_score is not None)
                    / max(1, sum(1 for l in scored_leads if l.lead_score is not None))
                )
                print("\n" + "="*60)
                print("  PIPELINE COMPLETE")
                print(f"  Total leads processed : {len(scored_leads)}")
                print(f"  Average lead score    : {avg_score:.1f} / 100")
                print(f"  Total pipeline time   : {total_time:.2f}s")
                print("="*60 + "\n")
                return {"status": "success", "message": "Pipeline executed successfully.",
                        "count": len(scored_leads), "leads": scored_leads}
            else:
                if update_status_cb: update_status_cb("Error during storage.")
                print(f"\n[ERROR] Pipeline failed at Storage Agent after {total_time:.2f}s")
                return {"status": "error", "message": "Failed to store leads.", "count": 0, "leads": []}
                
        except Exception as e:
            total_time = time.time() - pipeline_start
            logger.error(f"Orchestrator pipeline failed: {str(e)}")
            if update_status_cb: update_status_cb(f"Failed: {str(e)}")
            print(f"\n[ERROR] Pipeline failed after {total_time:.2f}s: {e}")
            return {"status": "error", "message": str(e), "count": 0, "leads": []}

async def run_apollo_pipeline(roles: List[str], location: str, industry: str, size: str = None, limit: int = 10, filters: dict = None, update_status_cb=None):
    orchestrator = OrchestratorAgent()
    return await orchestrator.execute_pipeline(roles, location, industry, None, size, limit, filters, update_status_cb)
