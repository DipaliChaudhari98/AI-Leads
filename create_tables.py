from sqlalchemy import create_engine
from models import Base, Lead, EmailOutreach, FollowUp  # important: import all models

DATABASE_URL = "postgresql://postgres.qolbjdawltonpapbpasu:SiGaSystema%40123@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL, echo=True)

Base.metadata.create_all(bind=engine)

print("✅ All tables created successfully in Supabase!")