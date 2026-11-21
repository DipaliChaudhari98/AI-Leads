import asyncio
from agents.website_research_agents import WebsiteCrawlerAgent, WebsiteResearchAgent, ApifyWorkflowOrchestrator

async def test():
    print("=== TESTING PLAYWRIGHT WEBSITE CRAWLER AGENT ===")
    crawler = WebsiteCrawlerAgent()
    
    url = "https://sigasystems.com"
    result = await crawler.process(url)
    
    print(f"Crawled URL    : {result.website_url}")
    print(f"Page Title     : {result.page_title}")
    print(f"Crawled Pages  : {result.crawled_pages}")
    print(f"Metadata       : {result.metadata}")
    print(f"Content snippet: {result.clean_content[:400] if result.clean_content else 'None'}")
    
    print("\n--- Testing WebsiteResearchAgent ---")
    research_agent = WebsiteResearchAgent()
    data = await research_agent.process(result.clean_content)
    print("Extracted Research Data:", data.model_dump())

if __name__ == "__main__":
    asyncio.run(test())
