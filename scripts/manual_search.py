from tools.apollo_tools import ApolloClient
from tools.db_tools import DatabaseManager
import json

def run_advanced_search():
    client = ApolloClient()
    db_manager = DatabaseManager()
    
    # Filters based on the URL provided:
    # contactEmailStatusV2[]=verified
    # organizationIndustryTagIds[]=5567cd4773696439b10b0000
    # personLocations[]=United%20States
    # organizationNumEmployeesRanges[]=101%2C200
    # personTitles[]=ceo%20and%20founder
    
    print("\n--- Running Advanced Apollo Search ---")
    print("Filters: CEO & Founder, US, Software Industry, 101-200 Employees, Verified Emails\n")
    
    # Continue with normal parsing
    leads = []
    try:
        leads = client.search_leads_advanced(
            titles=["ceo and founder"],
            locations=["United States"],
            industry_tag_ids=["5567cd4773696439b10b0000"],
            employee_ranges=["51-200"],
            email_status=["verified"],
            limit=5
        )
    except Exception as e:
        print(f"Error fetching from Apollo API: {e}")
        print("Proceeding to show fetched leads if any...")
    
    if not leads:
        print("No leads found matching these criteria or an error occurred.")
        return

    print(f"Found {len(leads)} matching leads. Saving to database...\n")
    
    # Save leads to the database (Supabase)
    db_manager.save_leads(leads)
    
    for i, lead in enumerate(leads, 1):
        print(f"Lead {i}:")
        print(f"  Name:     {lead.name}")
        print(f"  Email:    {lead.email}")
        print(f"  Title:    {lead.title}")
        print(f"  Company:  {lead.company}")
        print(f"  Location: {lead.location}")
        print(f"  ID:       {lead.apollo_id}")
        print("-" * 30)

    print(f"\nSUCCESS: {len(leads)} leads have been stored in the database.")

if __name__ == "__main__":
    run_advanced_search()

