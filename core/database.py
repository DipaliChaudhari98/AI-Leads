import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.sql_models import Base
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    raise EnvironmentError("DATABASE_URL must be a postgresql connection string.")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize the database, creating all tables."""
    Base.metadata.create_all(bind=engine)
    print(f"PostgreSQL Database initialized.")
    
    # Auto-add local time columns to satisfy explicit timezone requirement
    from sqlalchemy import text
    with engine.begin() as conn:
        for col in ["initial_email_date_local", "next_followup_date_local", "last_followup_date_local"]:
            try:
                conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col} TIMESTAMP;"))
                print(f"Dynamically added column: {col}")
            except Exception:
                pass # Column likely already exists

if __name__ == "__main__":
    init_db()
