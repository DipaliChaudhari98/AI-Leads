import os
from dotenv import load_dotenv
from core.database import SessionLocal
from models.sql_models import Lead

load_dotenv()

def check_db():
    session = SessionLocal()
    try:
        leads = session.query(Lead).all()
        print(f"Total leads in database: {len(leads)}")
        if leads:
            print(f"First lead details:")
            lead = leads[0]
            print(f"ID: {lead.id}")
            print(f"Name: {lead.name}")
            print(f"Email: {lead.email}")
            print(f"Company: {lead.company}")
            print(f"Source: {lead.source}")
            print(f"Lead Score: {lead.lead_score}")
            print(f"Status: {lead.status}")
        else:
            print("No leads found in the database.")
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_db()
