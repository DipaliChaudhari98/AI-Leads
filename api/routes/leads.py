from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
# from database import SessionLocal
from models.sql_models import Lead
from pydantic import BaseModel
import uuid
from typing import Optional
from datetime import datetime

router = APIRouter()
from fastapi.responses import JSONResponse
from tools.db_tools import DatabaseManager
from models.sql_models import EmailOutreach
from sqlalchemy.orm import joinedload

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LeadSchema(BaseModel):
    id: int
    name: str
    email: str
    company: str
    title: str
    status: str
    industry: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    apollo_id: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[LeadSchema])
def get_leads(
    skip: int = 0, 
    limit: int = 100, 
    location: Optional[str] = None,
    industry: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Lead)
    if location:
        query = query.filter(Lead.location.ilike(f"%{location}%"))
    if industry:
        query = query.filter(Lead.industry.ilike(f"%{industry}%"))
    if date_from:
        query = query.filter(Lead.created_at >= date_from)
    if date_to:
        query = query.filter(Lead.created_at <= date_to)
        
    leads = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()
    return leads

@router.get("/{lead_id}", response_model=LeadSchema)
def get_lead(lead_id: int, db: Session = Depends(get_db)):

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

