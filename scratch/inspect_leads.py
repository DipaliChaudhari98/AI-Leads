import sys
from core.database import SessionLocal
from models.sql_models import Lead

db = SessionLocal()
try:
    leads = db.query(Lead).all()
    print(f"Total leads in DB: {len(leads)}")
    for i, lead in enumerate(leads[:1]):
        print(f"\n--- Lead {i+1}: {lead.company} ---")
        print("metadata keys:")
        for k, v in lead.lead_metadata.items():
            print(f"  {k}: {type(v).__name__} = {str(v)[:100]}")
finally:
    db.close()
