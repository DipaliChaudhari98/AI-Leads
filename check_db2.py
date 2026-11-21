import os
from dotenv import load_dotenv
from core.database import SessionLocal
from models.sql_models import Lead

load_dotenv()

def check_db():
    session = SessionLocal()
    try:
        leads = session.query(Lead).order_by(Lead.id.desc()).limit(5).all()
        print(f"Latest 5 leads in database:")
        for lead in leads:
            print(f"ID: {lead.id}, Name: {lead.name}, Email: {lead.email}, Score: {lead.lead_score}, Date: {lead.created_at}")
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_db()
