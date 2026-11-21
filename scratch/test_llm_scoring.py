import os
import sys

# Set PYTHONPATH
sys.path.append(os.path.abspath("."))

from agents.apollo_processing_agents import LeadScoringAgent

def test_llm_scoring():
    print("Initializing LeadScoringAgent...")
    agent = LeadScoringAgent()
    
    mock_company = {
        "name": "Acme Corp",
        "email": "contact@acmecorp.com",
        "companyName": "Acme Corporation",
        "title": "CTO",
        "industry": "Software",
        "employee_count": 50,
        "description": "Acme Corp is a rapidly growing startup focusing on delivering digital marketing solutions and workflow automation platforms for mid-sized businesses.",
        "technologies": ["react", "nodejs", "aws"]
    }
    
    print("Running _score_with_rules()...")
    try:
        rule_result = agent._score_with_rules(mock_company)
        print("Rule-based Scoring successful!")
        print(f"Score: {rule_result.lead_score}")
        print(f"Priority: {rule_result.priority}")
        print("-" * 20)
    except Exception as e:
        print(f"Error in rule-based scoring: {e}")

    print("Running score() (which uses LLM)...")
    try:
        result = agent.score(mock_company)
        print("LLM Scoring successful!")
        print(f"Scoring method: {result.scoring_method}")
        print(f"Score: {result.lead_score}")
        print(f"Priority: {result.priority}")
        print(f"Buying Probability: {result.buying_probability}")
        print(f"Summary: {result.summary}")
        print(f"Recommended Services: {result.recommended_services}")
    except Exception as e:
        print(f"Error during scoring: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_scoring()
