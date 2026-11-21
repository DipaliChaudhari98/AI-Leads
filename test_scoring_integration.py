import os
import json
import logging
from dotenv import load_dotenv
load_dotenv()

from agents.apollo_processing_agents import LeadScoringAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestScoring")

# Mock client for fallback testing
class BrokenLLMClient:
    def complete(self, prompt: str) -> str:
        raise RuntimeError("LLM Service Unavailable (Simulated Error)")

# Mock client that returns invalid arithmetic to test drift fallback
class MismatchingLLMClient:
    def complete(self, prompt: str) -> str:
        # returns leadScore = 90 but sum of breakdown = 10 (mismatch > 5)
        return json.dumps({
            "scoreBreakdown": {
                "industry": {"points": 2, "rationale": "Mock"},
                "companySize": {"points": 1, "rationale": "Mock"},
                "techAdoption": {"points": 1, "rationale": "Mock"},
                "aiReadiness": {"points": 1, "rationale": "Mock"},
                "decisionMaker": {"points": 2, "rationale": "Mock"},
                "websiteEmail": {"points": 1, "rationale": "Mock"},
                "targetMarket": {"points": 1, "rationale": "Mock"},
                "growthIndicators": {"points": 1, "rationale": "Mock"}
            },
            "leadScore": 90,
            "buyingProbability": "Low",
            "summary": "This should trigger drift mismatch fallback.",
            "strengths": [],
            "weaknesses": [],
            "recommendedServices": ["Workflow Automation"],
            "recommendedContactRole": "CTO",
            "nextAction": "Test next action"
        })

# 3 Test Companies
high_fit_company = {
    "name": "Sarah Connor",
    "email": "sarah@cyberdyne.com",
    "company": "Cyberdyne Systems",
    "contact_title": "CTO",
    "website": "https://cyberdyne.com",
    "email_verified": True,
    "location": "San Francisco, CA",
    "country": "USA",
    "industry": "Software, AI & Robotics",
    "employeeCount": 1200,
    "technologies": ["AWS", "React", "Python", "Docker", "Kubernetes", "Salesforce"],
    "description": "Leading artificial intelligence and neural network systems developer.",
    "recent_funding": "Series E, hiring multiple research roles"
}

low_fit_company = {
    "name": "Jane Baker",
    "email": "jane@janescakes.com",
    "company": "Jane's Bakery",
    "contact_title": "Owner",
    "website": "https://janescakes.com",
    "email_verified": True,
    "location": "Paris, France",
    "country": "France",
    "industry": "Food & Beverage",
    "employeeCount": 3,
    "technologies": ["WordPress"],
    "description": "Local bakery offering artisan bread and custom cakes."
}

def run_tests():
    # 1. Test High Fit Company (using actual LLM if API key available, else it will fallback gracefully)
    print("\n=== TEST 1: HIGH FIT COMPANY ===")
    agent = LeadScoringAgent()
    result = agent.score(high_fit_company)
    print(f"Scoring Method: {result.scoring_method}")
    print(f"Lead Score    : {result.lead_score}")
    print(f"Priority      : {result.priority}")
    print(f"Buying Prob   : {result.buying_probability}")
    print(f"AI Summary    : {result.ai_summary}")
    print(f"Recommended   : {result.recommended_services}")
    assert result.lead_score is not None, "Lead score should not be None"
    assert result.lead_score >= 50, f"Expected high-fit score >= 50, got {result.lead_score}"
    assert result.priority in ["High", "Very High", "Medium"], f"Expected reasonable priority, got {result.priority}"

    # 2. Test Low Fit Company
    print("\n=== TEST 2: LOW FIT COMPANY ===")
    result_low = agent.score(low_fit_company)
    print(f"Scoring Method: {result_low.scoring_method}")
    print(f"Lead Score    : {result_low.lead_score}")
    print(f"Priority      : {result_low.priority}")
    assert result_low.lead_score < 40, f"Expected low score, got {result_low.lead_score}"
    assert result_low.priority in ["Low", "Very Low"], f"Expected low priority, got {result_low.priority}"

    # 3. Test Fallback Path via Broken LLM
    print("\n=== TEST 3: BROKEN LLM FALLBACK ===")
    broken_agent = LeadScoringAgent(llm_client=BrokenLLMClient())
    result_fallback = broken_agent.score(high_fit_company)
    print(f"Scoring Method: {result_fallback.scoring_method}")
    print(f"Lead Score    : {result_fallback.lead_score}")
    print(f"Priority      : {result_fallback.priority}")
    assert result_fallback.scoring_method == "rule_based", "Expected fallback to rule_based scoring"
    assert result_fallback.ai_summary is None, "AI-only fields should remain None on rule_based path"

    # 4. Test Fallback Path via Score Drift
    print("\n=== TEST 4: SCORE DRIFT FALLBACK ===")
    mismatch_agent = LeadScoringAgent(llm_client=MismatchingLLMClient())
    result_mismatch = mismatch_agent.score(high_fit_company)
    print(f"Scoring Method: {result_mismatch.scoring_method}")
    print(f"Lead Score    : {result_mismatch.lead_score}")
    print(f"Priority      : {result_mismatch.priority}")
    assert result_mismatch.scoring_method == "rule_based", "Expected fallback to rule_based due to score drift"

    print("\n[PASS] All tests passed successfully!")

if __name__ == "__main__":
    run_tests()
