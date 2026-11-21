import os
from sqlalchemy import text
from core.database import engine

def add_columns():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS initial_email_date TIMESTAMP WITHOUT TIME ZONE;"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS initial_email_status VARCHAR;"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_followup_date TIMESTAMP WITHOUT TIME ZONE;"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_followup_status VARCHAR;"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_followup_status VARCHAR;"))
        conn.commit()
        print("Columns added successfully.")

if __name__ == "__main__":
    add_columns()
