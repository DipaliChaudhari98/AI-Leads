import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres.qolbjdawltonpapbpasu:SiGaSystema%40123@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL)

def alter_table():
    with engine.begin() as conn:
        print("Altering table leads...")
        columns_to_add = [
            "apollo_location VARCHAR",
            "city VARCHAR",
            "state VARCHAR",
            "country VARCHAR",
            "timezone VARCHAR",
            "utc_offset VARCHAR",
            "business_hours_start VARCHAR DEFAULT '09:00'",
            "business_hours_end VARCHAR DEFAULT '18:00'"
        ]
        for col in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col}"))
                print(f"Successfully added column {col}.")
            except Exception as e:
                print(f"Error adding {col}: {e}")

if __name__ == "__main__":
    alter_table()
