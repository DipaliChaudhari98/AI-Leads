import os
import argparse
import json
import asyncio
from crewai import LLM
from agents.apollo_processing_agents import OrchestratorAgent
from tools.db_tools import DatabaseManager
from core.database import init_db
from dotenv import load_dotenv
import sys, io
import logging

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Main")

# def run_lead_generation_campaign(companies, roles, followup_strategy="hybrid", location="United States", industry=None):
#     init_db()
#     db_manager = DatabaseManager()
#     llm = get_llm()

#    # Initialize New Apollo Pipeline Orchestrator
#     orchestrator = get_orchestrator(llm, roles, location, industry)

#     print("\n--- Starting Apollo Processing Multi-Agent Pipeline ---\n")
#     result = orchestrator.kickoff()

# #  Initialize Apollo Pipeline Orchestrator
# orchestrator = OrchestratorAgent()

# print("\n--- Starting Apollo Processing Multi-Agent Pipeline ---\n")

# result = asyncio.run(
#     orchestrator.execute_pipeline(
#         roles=roles,
#         location=location,
#         industry=industry
#     )
# )

#     stats = db_manager.get_campaign_stats()
#     print("\n--- Final Campaign Stats ---")
#     print(json.dumps(stats, indent=2))
#     db_manager.close()

#     return result


def run_lead_generation_campaign(companies, roles, followup_strategy="hybrid", location="United States", industry=None, size=None, limit=10, filters=None):
    init_db()
    db_manager = DatabaseManager()
    
    logger.info("Initializing Lead Generation Orchestrator...")
    orchestrator = OrchestratorAgent()
    
    logger.info(f"Starting Campaign with parameters:")
    logger.info(f"  Companies: {companies}")
    logger.info(f"  Roles: {roles}")
    logger.info(f"  Strategy: {followup_strategy}")
    logger.info(f"  Location: {location}")
    logger.info(f"  Industry: {industry}")
    logger.info(f"  Size: {size}")
    logger.info(f"  Limit: {limit}")

    # Create a dedicated event loop for this thread so it doesn't conflict with
    # the outer FastAPI/uvicorn loop when called via asyncio.to_thread().
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            orchestrator.execute_pipeline(
                roles=roles,
                location=location,
                industry=industry,
                companies=companies,
                size=size,
                limit=limit,
                filters=filters
            )
        )
    finally:
        loop.close()

    stats = db_manager.get_campaign_stats()

    print("\n--- Final Campaign Stats ---")
    print(json.dumps(stats, indent=2))

    db_manager.close()

    return result

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/start-campaign")
async def start_campaign(request: Request):

    form = await request.form()

    companies = form.get("companies", "")
    roles = form.get("roles", "CEO, Founder")
    strategy = form.get("strategy", "hybrid")
    location = form.get("location", "United States")
    industry = form.get("industry", "Software")
    size = form.get("size", "")
    limit = int(form.get("limit", 10))
    filters = form.get("filters", "")

    companies_list = [c.strip() for c in companies.split(",")] if companies else []
    roles_list = [r.strip() for r in roles.split(",")]

    # Parse custom filters
    filters_dict = {}
    if filters:
        try:
            filters_dict = json.loads(filters)
        except json.JSONDecodeError:
            # Try key=value parsing
            for pair in filters.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    v_clean = v.strip().lower()
                    if v_clean == 'true': v_val = True
                    elif v_clean == 'false': v_val = False
                    else: v_val = v.strip()
                    filters_dict[k.strip()] = v_val

    # START YOUR AGENTS
    result = run_lead_generation_campaign(
        companies=companies_list,
        roles=roles_list,
        followup_strategy=strategy,
        location=location,
        industry=industry,
        size=size,
        limit=limit,
        filters=filters_dict
    )

    if result.get("status") == "success" and result.get("leads"):
        from agents.email_workflow_agents import run_email_pipeline
        await run_email_pipeline(result["leads"])

    return {
        "success": True,
        "message": "Crew started successfully",
        "result": str(result)
    }

    
if __name__ == "__main__":
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="Multi-Agent Lead Generation System")
    parser.add_argument("--companies", type=str, default="", help="Comma-separated list of companies")
    parser.add_argument("--roles", type=str, default="CEO, Founder", help="Comma-separated list of roles")
    parser.add_argument("--strategy", type=str, default="hybrid", help="Follow-up strategy")
    
    parser.add_argument("--direct", action="store_true", help="Run tools directly without LLM agents")
    args = parser.parse_args()
    companies_list = [c.strip() for c in args.companies.split(",")] if args.companies else []
    roles_list = [r.strip() for r in args.roles.split(",")]
    
    if args.direct:
        print("\n--- Running Apollo Data Processing in DIRECT MODE (Bypassing Agents) ---")
     
        from tools.apollo_tools import ApolloClient
        
        # Data Fetch & Process directly
        print(f"Scraping Apollo for {roles_list}...")
        scraper = ApolloClient()
        db_manager = DatabaseManager()
        leads = scraper.search_leads_advanced(titles=roles_list, limit=5)
        
        # Save handles deduplication intelligently now
        db_manager.save_leads(leads)
        
        db_manager.close()
    else:
        result = run_lead_generation_campaign(companies_list, roles_list, args.strategy)
        
        if result.get("status") == "success" and result.get("leads"):
            print("\n--- Starting Email Workflow ---")
            from agents.email_workflow_agents import run_email_pipeline
            asyncio.run(run_email_pipeline(result["leads"]))
            print("\n--- Email Workflow Complete ---")
