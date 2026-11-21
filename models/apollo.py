from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ApolloLead(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    title: Optional[str] = None
    apollo_id: str
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    apollo_location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    utc_offset: Optional[str] = None
    business_hours_start: Optional[str] = "09:00"
    business_hours_end: Optional[str] = "18:00"
    source: Optional[str] = "apollo"                        # Data source identifier
    skills: List[str] = []
    experience: List[str] = []
    summary: Optional[str] = None
    raw_data: Optional[dict] = None
    company_enrichment: Optional[Dict] = None           # Output from CompanyEnrichmentAgent (website research)
    # ── Scoring ──────────────────────────────────────────────────────────
    lead_score: Optional[int] = None                        # 0-100 composite score
    score_breakdown: Optional[Dict[str, Any]] = None        # per-dimension raw scores or point objects

    # ── AI Lead Intelligence (set by LeadScoringAgent) ────────────────
    priority: Optional[str] = None                          # High / Medium / Low / Very Low
    buying_probability: Optional[str] = None                # High / Medium / Low
    ai_summary: Optional[str] = None                        # Generated narrative
    strengths: Optional[List[str]] = None                   # Positive buying signals
    weaknesses: Optional[List[str]] = None                  # Risk factors / gaps
    recommended_services: Optional[List[str]] = None        # SIGA services to pitch
    recommended_contact_role: Optional[str] = None          # Best person to reach out to
    pain_points: Optional[List[Dict[str, str]]] = None      # Evidence-grounded pain points mapped to SIGA services
    next_action: Optional[str] = None                       # Suggested outreach step
    scoring_method: Optional[str] = None                    # "llm" or "rule_based"
