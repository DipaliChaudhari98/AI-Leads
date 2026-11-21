import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    print("Adding initial_email_date_local column...")
    try:
        conn.execute(text("ALTER TABLE leads ADD COLUMN initial_email_date_local TIMESTAMP;"))
    except Exception as e:
        print(f"Failed or already exists: {e}")

    print("Adding next_followup_date_local column...")
    try:
        conn.execute(text("ALTER TABLE leads ADD COLUMN next_followup_date_local TIMESTAMP;"))
    except Exception as e:
        print(f"Failed or already exists: {e}")

    print("Adding last_followup_date_local column...")
    try:
        conn.execute(text("ALTER TABLE leads ADD COLUMN last_followup_date_local TIMESTAMP;"))
    except Exception as e:
        print(f"Failed or already exists: {e}")

print("Database migration completed.")
