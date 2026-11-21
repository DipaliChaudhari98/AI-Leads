from core.database import engine
from sqlalchemy import text

def migrate_db():
    cols = [
        ('industry', 'VARCHAR'),
        ('employee_count', 'VARCHAR'),
        ('location', 'VARCHAR'),
        ('lead_metadata', 'JSON'),
        ('last_interaction_at', 'TIMESTAMP')
    ]
    
    with engine.connect() as conn:
        for name, col_type in cols:
            try:
                print(f"Adding column {name}...")
                conn.execute(text(f"ALTER TABLE leads ADD COLUMN {name} {col_type}"))
                print(f"Column {name} added.")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"Column {name} already exists.")
                else:
                    print(f"Error adding {name}: {e}")
        conn.commit()

if __name__ == "__main__":
    migrate_db()
