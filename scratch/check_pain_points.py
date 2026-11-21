import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal
from models.sql_models import Lead

def check():
    session = SessionLocal()
    try:
        leads = session.query(Lead).all()
        null_count = 0
        non_null_count = 0
        for lead in leads:
            if lead.pain_points is None:
                null_count += 1
            else:
                non_null_count += 1
        print(f"Total leads: {len(leads)}")
        print(f"Null pain points count: {null_count}")
        print(f"Non-null pain points count: {non_null_count}")
    finally:
        session.close()

if __name__ == "__main__":
    check()
