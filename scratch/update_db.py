import os
import sys

# Add the parent directory to sys.path so we can import from core/models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from core.database import engine, SessionLocal
from models.sql_models import Lead

def update_lead_dates():
    db = SessionLocal()
    try:
        leads = db.query(Lead).filter(Lead.initial_email_date.isnot(None)).all()
        updated_count = 0
        for lead in leads:
            # Re-calculate dates based on initial_email_date
            lead.set_followup_dates()
            updated_count += 1
        
        db.commit()
        print(f"Successfully updated dates for {updated_count} leads in the database.")
    except Exception as e:
        print(f"Error updating dates: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_lead_dates()
