from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Outreach Management System"
    DATABASE_URL: str
    SENDGRID_API_KEY: str
    APOLLO_API_KEY: str
    OPENROUTER_API_KEY: str
    
    FORCE_LIVE_EMAIL: bool = False
    SENDER_EMAIL: str
    SENDER_NAME: str = "Outreach Team"
    
    # Supabase Settings (for Auth/Realtime if needed)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
