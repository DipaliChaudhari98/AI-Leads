import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models.sql_models import Lead
from models.apollo import ApolloLead
from services.enrichment import enrich_lead_location_and_tz
from tools.db_tools import DatabaseManager

def backfill():
    print("Starting backfill for existing leads...")
    db_manager = DatabaseManager()
    session = db_manager.session
    
    leads_to_update = session.query(Lead).filter(Lead.timezone == None).all()
    print(f"Found {len(leads_to_update)} leads to backfill.")
    
    count = 0
    for lead in leads_to_update:
        loc = lead.location or lead.apollo_location
        if not loc:
            if lead.lead_metadata and isinstance(lead.lead_metadata, dict):
                loc = lead.lead_metadata.get("location")
                
        if loc:
            apollo_lead = ApolloLead(
                name=lead.name or "Unknown",
                email=lead.email or "unknown@example.com",
                apollo_id=lead.apollo_id or "unknown",
                location=loc
            )
            
            enriched = enrich_lead_location_and_tz(apollo_lead)
            
            lead.location = loc # keep original
            lead.apollo_location = enriched.apollo_location
            lead.city = enriched.city
            lead.state = enriched.state
            lead.country = enriched.country
            lead.timezone = enriched.timezone
            lead.utc_offset = enriched.utc_offset
            lead.business_hours_start = enriched.business_hours_start
            lead.business_hours_end = enriched.business_hours_end
            
            if lead.initial_email_date:
                lead.set_followup_dates()
                
            count += 1
            
    session.commit()
    print(f"Successfully backfilled {count} leads.")

if __name__ == "__main__":
    backfill()
