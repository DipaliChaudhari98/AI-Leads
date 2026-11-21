import sys
import io
import json
from datetime import datetime
from core.database import SessionLocal
from models.sql_models import Lead

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db = SessionLocal()
leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
print(f"Found {len(leads)} leads (ordered by created_at DESC):")
print("-" * 60)
for l in leads:
    print(f"ID: {l.id} | Name: {l.name} | Email: {l.email} | Title: {l.title} | Company: {l.company} | Created: {l.created_at}")

db.close()
