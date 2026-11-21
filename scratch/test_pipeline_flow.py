import asyncio
import os
import sys

sys.path.append(os.path.abspath("."))

from agents.website_research_agents import ApifyWorkflowOrchestrator

async def test_pipeline():
    orchestrator = ApifyWorkflowOrchestrator()
    
    # Mock lead data with LinkedIn/Apollo structure
    lead_data = {
        "id": "mock_id_123",
        "website": "https://example.com",
        "companyName": "Incomplete Website Name",
        "industry": "General",
        "company": {
            "name": "LinkedIn Awesome Company",
            "industries": [{"name": "Artificial Intelligence"}],
            "employeeCount": 150,
            "foundedOn": {"year": 2021},
            "location": {"parsed": {"text": "San Francisco, CA"}},
            "description": "We are building the future of AI agents.",
            "specialities": ["AI", "Automation", "Workflow"]
        },
        "hiring": True,
        "openToWork": False,
        "title": "CTO",
        "currentPosition": [{"position": "Chief Technology Officer"}]
    }

    def print_status(msg):
        print(f"[STATUS] {msg}")

    print("Starting Pipeline execution...")
    result = await orchestrator.execute_pipeline(lead_data, update_status_cb=print_status)
    
    print("\n" + "="*50)
    print("PIPELINE RESULT STATUS:", result.get("status"))
    print("PIPELINE RESULT MESSAGE:", result.get("message"))
    print("\n--- SCORED LEAD ---")
    import json
    if result.get("scored_lead"):
        print(json.dumps(result["scored_lead"], indent=2))
    else:
        print("No scored_lead found in result.")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
