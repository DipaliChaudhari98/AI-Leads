from core.database import SessionLocal
from models.sql_models import Lead, EmailOutreach
from datetime import datetime

def check_leads():
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        print(f"Total Leads: {len(leads)}")
        for lead in leads:
            print(f"Lead: {lead.name} ({lead.email}) | Status: {lead.status} | Follow-ups: {lead.followup_count}/{lead.max_followups} | Next Follow-up: {lead.next_followup_date}")
            
        outreaches = db.query(EmailOutreach).all()
        print(f"\nTotal Outreaches: {len(outreaches)}")
        for o in outreaches:
            print(f"Outreach to {o.lead_id}: {o.subject} | Status: {o.status} | Sent At: {o.sent_at} | Scheduled At: {o.scheduled_at}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_leads()
