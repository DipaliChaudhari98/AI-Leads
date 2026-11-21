import asyncio
import sys
import os

# Set PYTHONPATH
sys.path.append(os.path.abspath("."))

async def test_import():
    try:
        print("Importing agents.website_research_agents...")
        from agents.website_research_agents import WebsiteCrawlerAgent, WebsiteResearchAgent, CompanyEnrichmentAgent, ApifyDataCleaningAgent, ApifyWorkflowOrchestrator
        print("Import successful!")
        
        print("Instantiating orchestrator...")
        orchestrator = ApifyWorkflowOrchestrator()
        print("Instantiation successful!")
        
        print("Check completed successfully!")
    except Exception as e:
        print(f"Error during import/instantiation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_import())
