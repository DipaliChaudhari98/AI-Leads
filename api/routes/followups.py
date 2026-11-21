from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from sqlalchemy.orm import joinedload

from tools.db_tools import DatabaseManager
from pydantic import BaseModel
from typing import List, Optional
from models.sql_models import EmailOutreach

router = APIRouter()


@router.get("")
async def get_followups(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    show_rejected: bool = Query(False)
):
    from models.sql_models import Lead
    from sqlalchemy import desc
    db_manager = DatabaseManager()

    try:
        offset = (page - 1) * limit

        query = db_manager.session.query(Lead).filter(
            Lead.lead_score != None,
            Lead.lead_score <= 50
        )

        if show_rejected:
            query = query.filter(Lead.is_active == False)
        else:
            query = query.filter(Lead.is_active == True, Lead.status != 'approved')

        total = query.count()
        leads = query.order_by(desc(Lead.created_at)).offset(offset).limit(limit).all()

        results = []
        for lead in leads:
            results.append({
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "title": lead.title,
                "status": lead.status,
                "lead_score": lead.lead_score,
                "priority": lead.priority,
                "buying_probability": lead.buying_probability,
                "location": lead.location or lead.apollo_location or "N/A",
                "industry": lead.industry or "N/A",
                "pain_points": lead.pain_points or [],
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "is_active": lead.is_active
            })

        return JSONResponse(content={
            "data": results,
            "total": total,
            "page": page,
            "limit": limit
        })
    finally:
        db_manager.close()


@router.post("/{lead_id}/approve")
async def approve_lead(lead_id: int):
    import asyncio
    from models.sql_models import Lead
    from agents.email_workflow_agents import run_email_pipeline
    from models.apollo import ApolloLead

    db_manager = DatabaseManager()
    try:
        lead = db_manager.session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return JSONResponse(content={"error": "Lead not found"}, status_code=404)

        lead.status = "approved"
        lead.is_active = True
        db_manager.session.commit()

        # Re-hydrate into ApolloLead to trigger email pipeline
        apollo_lead = ApolloLead(
            name=lead.name or "Unknown",
            email=lead.email or "",
            company=lead.company or "Unknown",
            title=lead.title or "",
            apollo_id=lead.apollo_id or "",
            linkedin_url=lead.linkedin_url or "",
            location=lead.location or lead.apollo_location or "",
            raw_data=lead.lead_metadata or {}
        )

        # Launch email pipeline asynchronously
        asyncio.create_task(run_email_pipeline([apollo_lead]))

        return JSONResponse(content={"status": "success", "message": "Lead approved and email generation started."})
    finally:
        db_manager.close()


@router.post("/{lead_id}/reject")
async def reject_lead(lead_id: int):
    from models.sql_models import Lead
    db_manager = DatabaseManager()
    try:
        lead = db_manager.session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return JSONResponse(content={"error": "Lead not found"}, status_code=404)

        lead.is_active = False
        lead.status = "rejected"
        db_manager.session.commit()
        return JSONResponse(content={"status": "success", "message": "Lead rejected (soft-deleted)."})
    finally:
        db_manager.close()


@router.post("/{lead_id}/restore")
async def restore_lead(lead_id: int):
    from models.sql_models import Lead
    db_manager = DatabaseManager()
    try:
        lead = db_manager.session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return JSONResponse(content={"error": "Lead not found"}, status_code=404)

        lead.is_active = True
        if lead.status == "rejected":
            lead.status = "researched"
        db_manager.session.commit()
        return JSONResponse(content={"status": "success", "message": "Lead restored successfully."})
    finally:
        db_manager.close()


class ProcessFollowupsRequest(BaseModel):
    email_ids: List[str]

@router.post("/process")
async def process_followups(req: ProcessFollowupsRequest):
    db_manager = DatabaseManager()
    
    # Simple demo implementation for now
    for eid in req.email_ids:
        # e.g., Update status to 'processing'
        email = db_manager.session.query(EmailOutreach).filter(EmailOutreach.id == eid).first()
        if email:
            email.status = "processing"
            db_manager.session.commit()
            
    db_manager.close()
    return JSONResponse(content={"status": "success", "processed": len(req.email_ids)})

class UpdateEmailRequest(BaseModel):
    subject: str
    body: str

@router.put("/{email_id}")
async def update_email(email_id: str, req: UpdateEmailRequest):
    db_manager = DatabaseManager()
    email = db_manager.session.query(EmailOutreach).filter(EmailOutreach.id == email_id).first()
    
    if not email:
        db_manager.close()
        return JSONResponse(content={"error": "Email not found"}, status_code=404)
        
    email.subject = req.subject
    email.body = req.body
    db_manager.session.commit()
    db_manager.close()
    
    return JSONResponse(content={"status": "success", "message": "Email updated successfully"})


# ── /api/emails — newest-first email sequence viewer ────────────────────────
@router.get("/emails")
async def get_emails(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    lead_id: Optional[int] = Query(None)
):
    """Returns all outreach emails ordered newest-first (by scheduled_at DESC).
    Groups within each page are already sorted initial -> follow_up_1 -> follow_up_2.
    The page-level ordering ensures the most recently generated batches appear first.
    """
    from sqlalchemy import desc
    db_manager = DatabaseManager()
    try:
        query = db_manager.session.query(EmailOutreach)
        if lead_id is not None:
            query = query.filter(EmailOutreach.lead_id == lead_id)

        total = query.count()

        # Newest scheduled_at first so the latest campaign batch is at the top
        outreaches = (
            query
            .options(joinedload(EmailOutreach.lead))
            .order_by(desc(EmailOutreach.scheduled_at))
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        results = []
        for f in outreaches:
            lead = f.lead
            results.append({
                "email_id": str(f.id),
                "lead_name": lead.name if lead else None,
                "company": lead.company if lead else None,
                "title": lead.title if lead else None,
                "industry": lead.industry if lead else None,
                "email": lead.email if lead else None,
                "lead_status": lead.status if lead else None,
                "followup_type": f.type,
                "subject": f.subject,
                "body": f.body,
                "status": f.status,
                "scheduled_at": f.scheduled_at.isoformat() if f.scheduled_at else None,
                "sent_at": f.sent_at.isoformat() if f.sent_at else None,
                "outreach_created_at": f.scheduled_at.isoformat() if f.scheduled_at else None,
            })

        return JSONResponse(content={
            "data": results,
            "total": total,
            "page": page,
            "limit": limit
        })
    finally:
        db_manager.close()
