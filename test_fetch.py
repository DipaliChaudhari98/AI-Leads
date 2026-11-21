import asyncio
from agents.apollo_processing_agents import InputAgent, ApolloFetchAgent, ValidationAgent, LeadScoringAgent

async def test():
    input_a = InputAgent()
    params = await input_a.process(roles=['CEO', 'Founder'], location='India', industry='Software', limit=5)
    
    fetch_a = ApolloFetchAgent()
    leads = await fetch_a.process(params)
    print(f"Fetched leads count: {len(leads)}")
    
    val_a = ValidationAgent()
    valid = await val_a.process(leads)
    print(f"Valid leads count: {len(valid)}")
    
    for l in valid:
        print(f"  - Lead: {l.name} | {l.company} | {l.email}")

if __name__ == "__main__":
    asyncio.run(test())
