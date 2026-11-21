import asyncio
from tools.apollo_tools import ApolloClient

client = ApolloClient()
leads = client.search_leads_advanced(titles=["CEO"], locations=["USA"], industries=["Software"], limit=3)
if leads:
    for idx, lead in enumerate(leads):
        print(f"\n=== Lead {idx+1}: {lead.name} | {lead.company} ===")
        print("Class properties:")
        print(lead.model_dump(exclude={"raw_data"}))
        print("\nraw_data keys and values:")
        for k, v in lead.raw_data.items():
            print(f"  {k}: {type(v).__name__} = {v}")
else:
    print("No leads fetched")
