import json
from agents.apollo_processing_agents import LeadScoringAgent
from tools.db_tools import DatabaseManager

sample_lead = {
  "firstName": "Marlene",
  "lastName": "Mcgill",
  "fullName": "Marlene Mcgill",
  "title": "Assistant to Global CEO",
  "position": "",
  "seniority": "entry",
  "functions": ["to ceo"],
  "email": "marlene_mcgill@blueprism.com",
  "emailStatus": "deliverable",
  "linkedinUrl": "linkedin.com/in/marlenemcgill",
  "personCity": "Miami",
  "personState": "Florida",
  "personCountry": "United States",
  "companyName": "blue prism",
  "companyDomain": "blueprism.com",
  "companyIndustry": ["Business/Productivity Software", "computer software"],
  "companyCity": "Newton-le-Willows",
  "companyState": "England",
  "companyCountry": "United Kingdom",
  "companyDescription": "Blue Prism's Robotic Process Automation (RPA) software enables business operations to be agile and cost effective...",
  "companySize": 149,
  "technologies": [
    "apache", "bootstrap_framework", "doubleclick", "google_analytics", "gravity_forms", 
    "hubspot", "outlook", "wordpress_org", "youtube"
  ],
  "annualRevenue": 7000000,
  "foundedYear": 2001
}

def test():
    agent = LeadScoringAgent()
    lead = agent.score(sample_lead)
    print("\n--- SCORED APOLLO LEAD ---")
    print(f"Lead Score: {lead.lead_score}")
    print(f"Priority: {lead.priority}")
    print(f"Buying Prob: {lead.buying_probability}")
    print(f"Score Breakdown: {json.dumps(lead.score_breakdown, indent=2)}")
    print(f"Pain Points: {json.dumps(lead.pain_points, indent=2)}")
    print(f"Recommended Services: {lead.recommended_services}")
    
    db = DatabaseManager()
    db.save_leads([lead])
    print("\nSuccessfully saved to database!")
    db.close()

if __name__ == "__main__":
    test()
