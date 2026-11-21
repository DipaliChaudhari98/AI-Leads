"""
backfill_leads.py
─────────────────
Retroactively computes ALL missing intelligence fields for existing leads
using the rule-based scorer from LeadScoringAgent, and updates the DB.

Run once:
    python backfill_leads.py
"""

import os, json, re, sys
from dotenv import load_dotenv
load_dotenv()

from core.database import SessionLocal
from models.sql_models import Lead
from models.apollo import ApolloLead

# ── Inline copy of scorer helpers (no agent import needed) ────────────────────

TARGET_INDUSTRIES = [
    "e-commerce", "retail", "professional services", "real estate",
    "property management", "healthcare", "hospitality", "logistics",
    "finance", "education", "recruitment", "manufacturing", "saas",
    "technology", "consulting", "startups", "software", "it services",
    "information technology", "computer", "analytics", "network",
]

TARGET_SIZE_RANGE = (5, 500)

TARGET_TECH_STACK = [
    "wordpress", "shopify", "woocommerce", "magento",
    "salesforce", "hubspot", "microsoft dynamics", "azure",
    "asana", "make.com", "zapier", "aws", "google workspace",
    "react", "angular", "node.js", "python", "docker", "kubernetes",
]

WEIGHTS = {"industry": 30, "company_size": 25, "revenue": 15, "tech_stack": 30}


def _parse_employee_count(raw):
    if not raw:
        return None
    raw = str(raw).replace(",", "").replace(" ", "")
    m = re.search(r"(\d+)[\-–](\d+)", raw)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m = re.search(r"(\d+)\+", raw)
    if m:
        return int(m.group(1))
    m = re.search(r"~?(\d+)", raw)
    if m:
        return int(m.group(1))
    return None


def _clean_industry(raw_val):
    if not raw_val:
        return None
    val = str(raw_val).strip()
    if val.startswith("{") and val.endswith("}"):
        val = val[1:-1]
        parts = re.findall(r'"([^"]+)"|([^,]+)', val)
        items = [p[0] or p[1].strip() for p in parts if (p[0] or p[1].strip())]
        return ", ".join(items) if items else None
    return val


def _score_industry(raw_data):
    org = raw_data.get("organization", {}) if isinstance(raw_data.get("organization"), dict) else {}
    industry_str = (raw_data.get("industry") or org.get("industry") or "").lower()
    if not industry_str:
        return 50
    for target in TARGET_INDUSTRIES:
        if target in industry_str:
            return 100
    return 20


def _score_company_size(raw_data):
    org = raw_data.get("organization", {}) if isinstance(raw_data.get("organization"), dict) else {}
    size_raw = (
        raw_data.get("employeeCount") or
        raw_data.get("employment_summary") or
        org.get("estimated_num_employees") or
        None
    )
    count = _parse_employee_count(str(size_raw)) if size_raw is not None else None
    if count is None:
        return 50
    lo, hi = TARGET_SIZE_RANGE
    if lo <= count <= hi:
        mid = (lo + hi) / 2
        proximity = 1.0 - abs(count - mid) / (mid - lo + 1)
        return int(60 + 40 * proximity)
    elif count < lo:
        return max(20, int(40 * count / lo))
    else:
        return max(10, int(40 * hi / count))


def _parse_revenue(raw):
    if not raw:
        return None
    raw = str(raw).lower().replace(",", "").replace(" ", "")
    m = re.search(r"[\$]?([\d.]+)([bmk]?)", raw)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2)
    if suffix == "b":
        val *= 1_000_000_000
    elif suffix == "m":
        val *= 1_000_000
    elif suffix == "k":
        val *= 1_000
    return val


def _score_revenue(raw_data):
    org = raw_data.get("organization", {}) if isinstance(raw_data.get("organization"), dict) else {}
    rev_raw = raw_data.get("revenue") or org.get("annual_revenue") or None
    rev = _parse_revenue(str(rev_raw)) if rev_raw is not None else None
    if rev is None:
        return 50
    if 1_000_000 <= rev <= 50_000_000:
        return 100
    elif rev < 1_000_000:
        return max(20, int(60 * rev / 1_000_000))
    else:
        return max(15, int(60 * 50_000_000 / rev))


def _score_tech_stack(raw_data):
    org = raw_data.get("organization", {}) if isinstance(raw_data.get("organization"), dict) else {}
    tech_list = (
        raw_data.get("techStack") or raw_data.get("technologies") or
        org.get("technologies") or []
    )
    if isinstance(tech_list, str):
        tech_list = [tech_list]
    tech_lower = " ".join(str(t).lower() for t in tech_list)
    if not tech_lower.strip():
        return 50
    matches = sum(1 for t in TARGET_TECH_STACK if t in tech_lower)
    if matches == 0:
        return 20
    return min(100, 40 + matches * 20)


def _safe_str(val) -> str:
    """Convert any value (str, list, None) to a safe lowercase string."""
    if not val:
        return ""
    if isinstance(val, list):
        return " ".join(str(v) for v in val).lower()
    return str(val).lower()


def compute_all_fields(lead: Lead) -> dict:
    """Compute all intelligence fields for a Lead DB record."""
    raw_data = lead.lead_metadata or {}
    if not isinstance(raw_data, dict):
        raw_data = {}
    org = raw_data.get("organization", {}) if isinstance(raw_data.get("organization"), dict) else {}

    industry_str = _safe_str(
        raw_data.get("industry") or raw_data.get("companyIndustry") or
        org.get("industry") or lead.industry or ""
    )

    title = _safe_str(lead.title)

    tech_list = (
        raw_data.get("techStack") or raw_data.get("technologies") or
        org.get("technologies") or []
    )
    if isinstance(tech_list, str):
        tech_list = [tech_list]
    tech_str = " ".join(str(t).lower() for t in tech_list)

    breakdown = {
        "industry":     _score_industry(raw_data),
        "company_size": _score_company_size(raw_data),
        "revenue":      _score_revenue(raw_data),
        "tech_stack":   _score_tech_stack(raw_data),
    }
    score = round(sum(breakdown[dim] * (WEIGHTS[dim] / 100) for dim in WEIGHTS))

    # Priority
    if score >= 75:
        priority = "High"
    elif score >= 60:
        priority = "Medium"
    elif score >= 40:
        priority = "Low"
    else:
        priority = "Very Low"

    # Buying probability
    if score >= 70:
        buying_probability = "High"
    elif score >= 45:
        buying_probability = "Medium"
    else:
        buying_probability = "Low"

    # Strengths & Weaknesses
    strengths = []
    weaknesses = []

    if breakdown["industry"] >= 60:
        strengths.append(f"Strong industry fit ({industry_str.title() or 'Technology / Services'})")
    else:
        weaknesses.append("Industry may not be a primary fit for SIGA AI services")

    if breakdown["company_size"] >= 60:
        strengths.append("Company size indicates operational complexity that benefits from automation")
    else:
        weaknesses.append("Company size may limit budget for enterprise AI solutions")

    if breakdown["tech_stack"] >= 60:
        strengths.append("Modern tech stack signals AI/automation readiness")
    else:
        weaknesses.append("Limited technology signals — may require digital transformation groundwork first")

    if breakdown["revenue"] >= 60:
        strengths.append("Revenue profile suggests healthy budget for AI investment")
    elif breakdown["revenue"] < 40:
        weaknesses.append("Revenue data insufficient or indicates constrained budget capacity")

    if any(t in title for t in ["ceo", "cto", "founder", "director", "vp", "head", "chief", "president", "owner"]):
        strengths.append(f"Direct access to a decision-maker ({lead.title})")

    # Recommended services
    services = ["AI Agents & Multi-Agent Systems", "Workflow Automation"]
    if any(t in tech_str for t in ["salesforce", "hubspot", "crm"]):
        services.append("CRM Integration & AI Sales Automation")
    if any(t in industry_str for t in ["healthcare", "medical", "pharma"]):
        services.append("Intelligent Document Processing (OCR) for Healthcare Records")
    if any(t in industry_str for t in ["finance", "banking", "insurance"]):
        services.append("AI-Powered Financial Document Automation")
    if any(t in industry_str for t in ["logistics", "supply chain", "transport"]):
        services.append("Supply Chain AI & Route Optimisation")
    if any(t in tech_str for t in ["wordpress", "shopify", "woocommerce", "ecommerce"]):
        services.append("WhatsApp AI Chatbots for E-commerce Support")
    if any(t in industry_str for t in ["saas", "software", "it services", "technology", "computer", "analytics"]):
        services.append("Custom Software Development & Cloud AI Solutions")
    services = list(dict.fromkeys(services))

    # Recommended contact role
    if any(t in title for t in ["ceo", "founder", "president", "owner", "managing director"]):
        rec_role = "CEO / Founder (strategic AI investment conversation)"
    elif any(t in title for t in ["cto", "chief technology", "vp engineering", "head of engineering"]):
        rec_role = "CTO / VP Engineering (technical integration discussion)"
    elif any(t in title for t in ["coo", "operations", "process"]):
        rec_role = "COO / Operations Head (workflow automation ROI)"
    elif any(t in title for t in ["director", "vp", "head"]):
        rec_role = f"{lead.title} (key decision influencer)"
    elif any(t in title for t in ["manager", "lead"]):
        rec_role = f"{lead.title} (department-level champion)"
    else:
        rec_role = lead.title or "Senior Decision Maker"

    # AI Summary
    company_name = lead.company or "This company"
    location_str = lead.location or lead.country or "their region"
    ai_summary = (
        f"{company_name} is a {industry_str.title() or 'technology'} company based in {location_str}. "
        f"With a lead score of {score}/100, this prospect is rated {priority} priority for SIGA Systems AI outreach. "
        f"{'Strong AI/automation readiness signals detected. ' if breakdown['tech_stack'] >= 60 else ''}"
        f"Recommended services: {', '.join(services[:2])}."
    )

    # Next action
    top_service = services[0] if services else "AI Agents & Workflow Automation"
    if score >= 75:
        next_action = (
            f"High-priority lead. Send a personalised email to {rec_role} "
            f"focusing on {top_service} ROI. Follow up within 3 business days."
        )
    elif score >= 60:
        next_action = (
            f"Send a tailored outreach email highlighting {top_service} with a relevant case study. "
            f"Invite {rec_role} to a 15-minute discovery call."
        )
    elif score >= 40:
        next_action = (
            "Add to nurture sequence. Send value-focused educational content on AI automation benefits. "
            "Re-evaluate fit in 30 days."
        )
    else:
        next_action = (
            "Low-priority lead. Enrol in long-term newsletter/drip campaign. "
            "Revisit if company grows or strategic direction changes."
        )

    # Fix industry string (strip PostgreSQL array format)
    clean_industry = _clean_industry(
        raw_data.get("companyIndustry") or raw_data.get("industry") or lead.industry
    )

    return {
        "lead_score":               score,
        "score_breakdown":          breakdown,
        "priority":                 priority,
        "buying_probability":       buying_probability,
        "ai_summary":               ai_summary,
        "strengths":                strengths,
        "weaknesses":               weaknesses,
        "recommended_services":     services,
        "recommended_contact_role": rec_role,
        "next_action":              next_action,
        "industry":                 clean_industry or lead.industry,
        "source":                   lead.source or "apollo",
    }


def backfill():
    session = SessionLocal()
    try:
        leads = session.query(Lead).all()
        total = len(leads)
        print(f"Backfilling {total} leads...", flush=True)

        updated = 0
        errors = 0
        for i, lead in enumerate(leads, 1):
            try:
                fields = compute_all_fields(lead)

                lead.lead_score               = fields["lead_score"]
                lead.score_breakdown          = fields["score_breakdown"]
                lead.priority                 = fields["priority"]
                lead.buying_probability       = fields["buying_probability"]
                lead.ai_summary               = fields["ai_summary"]
                lead.strengths                = fields["strengths"]
                lead.weaknesses               = fields["weaknesses"]
                lead.recommended_services     = fields["recommended_services"]
                lead.recommended_contact_role = fields["recommended_contact_role"]
                lead.next_action              = fields["next_action"]
                lead.industry                 = fields["industry"] or lead.industry
                lead.source                   = fields["source"]
                updated += 1

                if i % 50 == 0 or i == total:
                    session.commit()
                    pct = int(i / total * 100)
                    print(f"  [{pct:3d}%] {i}/{total} leads processed ({updated} updated, {errors} errors)...", flush=True)

            except Exception as e:
                errors += 1
                print(f"  ERROR on lead ID {lead.id}: {e}", flush=True)
                session.rollback()

        session.commit()
        print(f"\n[DONE] Backfill complete. {updated}/{total} leads updated. {errors} errors.", flush=True)

    except Exception as e:
        print(f"FATAL ERROR: {e}", flush=True)
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    backfill()
