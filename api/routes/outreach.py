from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import SessionLocal
from models.sql_models import Lead, EmailOutreach, OutreachApproval, EmailTemplate, LeadStatus
from pydantic import BaseModel
from datetime import datetime
from jinja2 import Template
import uuid

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class OutreachCreate(BaseModel):
    lead_id: int
    template_id: uuid.UUID
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None

class ApprovalAction(BaseModel):
    status: str # approved, rejected
    feedback: Optional[str] = None
    edited_subject: Optional[str] = None
    edited_body: Optional[str] = None

@router.post("/prepare", response_model=dict)
def prepare_outreach(data: OutreachCreate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    template = db.query(EmailTemplate).filter(EmailTemplate.id == data.template_id).first()
    
    if not lead or not template:
        raise HTTPException(status_code=404, detail="Lead or Template not found")

    # Render Template
    subject_jinja = Template(template.subject_template)
    body_jinja = Template(template.body_template)
    
    context = {
        "name": lead.name,
        "company": lead.company,
        "title": lead.title,
        "first_name": lead.name.split()[0] if lead.name else "there"
    }
    
    rendered_subject = data.custom_subject or subject_jinja.render(**context)
    rendered_body = data.custom_body or body_jinja.render(**context)
    
    outreach = EmailOutreach(
        lead_id=lead.id,
        template_id=template.id,
        subject=rendered_subject,
        body=rendered_body,
        status="pending_approval",
        type=template.type
    )
    db.add(outreach)
    db.flush()
    
    approval = OutreachApproval(
        lead_id=lead.id,
        email_id=outreach.id,
        status="pending"
    )
    db.add(approval)
    
    lead.status = LeadStatus.PENDING_APPROVAL
    db.commit()
    
    return {"outreach_id": str(outreach.id), "subject": rendered_subject, "body": rendered_body}

@router.post("/{outreach_id}/approve")
def approve_outreach(outreach_id: uuid.UUID, action: ApprovalAction, db: Session = Depends(get_db)):
    outreach = db.query(EmailOutreach).filter(EmailOutreach.id == outreach_id).first()
    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach not found")
        
    approval = db.query(OutreachApproval).filter(OutreachApproval.email_id == outreach_id).first()
    
    if action.status == "approved":
        outreach.status = "approved"
        if action.edited_subject: outreach.subject = action.edited_subject
        if action.edited_body: outreach.body = action.edited_body
        
        approval.status = "approved"
        approval.approved_at = datetime.utcnow()
        outreach.lead.status = LeadStatus.APPROVED
    else:
        outreach.status = "rejected"
        approval.status = "rejected"
        approval.feedback = action.feedback
        outreach.lead.status = LeadStatus.REJECTED
        
    db.commit()
    return {"status": "success", "new_status": outreach.status}
