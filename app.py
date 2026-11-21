import os
import sys
import asyncio
from pydantic import BaseModel
from datetime import datetime
import io
from api.routes.followups import router as followups_router
# Force UTF-8 encoding to prevent CrewAI emoji printing crashes on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tools.apollo_tools import ApolloClient
from tools.db_tools import DatabaseManager
from core.database import init_db, SessionLocal
from models.sql_models import Lead
from typing import List, Optional
import json
import uvicorn

from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth import router as auth_router, get_current_user

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Auth"]
)
app.include_router(
    followups_router,
    prefix="/api/follow_ups",
    tags=["Followups"],
    dependencies=[Depends(get_current_user)]
)
# Ensure database is initialized
init_db()

# Mount static files
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# Campaign status tracker (simple in-memory for demo)
campaign_status = {
    "is_running": False,
    "last_result": None,
    "current_step": "Idle"
}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html"
    )

def format_local_time(dt, tz_name):
    if not dt:
        return None
    try:
        import pytz
        # dt is naive UTC from DB. Localize it to UTC first.
        utc_dt = pytz.UTC.localize(dt)
        # Convert to target timezone
        local_tz = pytz.timezone(tz_name) if tz_name else pytz.UTC
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime("%b %d, %Y, %I:%M %p")
    except Exception:
        return dt.isoformat() + "Z"

@app.get("/api/leads", dependencies=[Depends(get_current_user)])
async def get_leads(
    page: int = Query(1, ge=1), 
    limit: int = Query(50, ge=1),
    location: Optional[str] = None,
    industry: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
):
    db_manager = DatabaseManager()
    try:
        from sqlalchemy.orm import joinedload
        
        query = db_manager.session.query(Lead).options(joinedload(Lead.outreach))
        
        if location:
            query = query.filter(Lead.location.ilike(f"%{location}%"))
        if industry:
            query = query.filter(Lead.industry.ilike(f"%{industry}%"))
        if date_from:
            query = query.filter(Lead.created_at >= date_from)
        if date_to:
            query = query.filter(Lead.created_at <= date_to)

        total = query.count()
        leads = query.order_by(Lead.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        results = []
        for lead in leads:
            outreaches = [{"id": str(o.id), "type": o.type, "subject": o.subject, "body": o.body, "status": o.status} for o in lead.outreach]
            results.append({
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "title": lead.title,
                "status": lead.status,
                "source": lead.source,
                "industry": lead.industry,
                "employee_count": lead.employee_count,
                "location": lead.location or lead.apollo_location,
                "city": lead.city,
                "state": lead.state,
                "country": lead.country,
                "apollo_id": lead.apollo_id,
                "linkedin_url": lead.linkedin_url,
                "timezone": lead.timezone,
                "utc_offset": lead.utc_offset,
                "business_hours_start": lead.business_hours_start,
                "business_hours_end": lead.business_hours_end,
                "created_at": lead.created_at.isoformat() + "Z" if lead.created_at else None,
                "next_followup_date": lead.next_followup_date_local.strftime("%b %d, %Y, %I:%M %p") if getattr(lead, 'next_followup_date_local', None) else format_local_time(lead.next_followup_date, lead.timezone),
                "initial_email_date": lead.initial_email_date_local.strftime("%b %d, %Y, %I:%M %p") if getattr(lead, 'initial_email_date_local', None) else format_local_time(lead.initial_email_date, lead.timezone),
                "initial_email_status": lead.initial_email_status,
                "last_followup_date": lead.last_followup_date_local.strftime("%b %d, %Y, %I:%M %p") if getattr(lead, 'last_followup_date_local', None) else format_local_time(lead.last_followup_date, lead.timezone),
                "next_followup_status": lead.next_followup_status,
                "last_followup_status": lead.last_followup_status,
                "emails": outreaches,
                # ── AI Lead Scoring ───────────────────────────────────────────
                "lead_score": lead.lead_score,
                "priority": lead.priority,
                "buying_probability": lead.buying_probability,
                "ai_summary": lead.ai_summary,
                "strengths": lead.strengths or [],
                "weaknesses": lead.weaknesses or [],
                "pain_points": lead.pain_points or [],
                "recommended_services": lead.recommended_services or [],
                "recommended_contact_role": lead.recommended_contact_role,
                "next_action": lead.next_action,
                "scoring_method": lead.scoring_method,
                "score_breakdown": lead.score_breakdown or {},
            })
        return JSONResponse(content={
            "data": results,
            "total": total,
            "page": page,
            "limit": limit
        })
    finally:
        db_manager.close()

class UpdateDateRequest(BaseModel):
    initial_date: str

@app.put("/api/leads/{lead_id}/initial-date", dependencies=[Depends(get_current_user)])
async def update_initial_date(lead_id: int, req: Request):
    data = await req.json()
    new_date_str = data.get("initial_date")
    
    if not new_date_str:
        return JSONResponse(content={"error": "initial_date is required"}, status_code=400)
        
    db_manager = DatabaseManager()
    try:
        lead = db_manager.session.query(Lead).filter(Lead.id == lead_id).first()
        
        if not lead:
            return JSONResponse(content={"error": "Lead not found"}, status_code=404)
            
        # Parse the date. It could be ISO format or YYYY-MM-DD
        if "T" in new_date_str:
            new_date = datetime.fromisoformat(new_date_str.replace("Z", "+00:00"))
        else:
            new_date = datetime.strptime(new_date_str, "%Y-%m-%d")
            
        lead.initial_email_date = new_date
        lead.set_followup_dates()
        db_manager.session.commit()
        return JSONResponse(content={"status": "success", "message": "Date updated"})
    except ValueError as e:
        return JSONResponse(content={"error": f"Invalid date format: {e}"}, status_code=400)
    finally:
        db_manager.close()

@app.post("/api/leads/{lead_id}/score", dependencies=[Depends(get_current_user)])
async def rescore_lead(lead_id: int):
    """Trigger LLM re-scoring for a specific lead and persist results."""
    db_manager = DatabaseManager()
    try:
        lead = db_manager.session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return JSONResponse(content={"error": "Lead not found"}, status_code=404)

        from agents.apollo_processing_agents import LeadScoringAgent
        from models.apollo import ApolloLead

        # Re-hydrate the lead into an ApolloLead for scoring
        apollo_lead = ApolloLead(
            name=lead.name or "Unknown",
            email=lead.email or "",
            company=lead.company,
            title=lead.title,
            apollo_id=lead.apollo_id or "",
            linkedin_url=lead.linkedin_url,
            phone=None,
            location=lead.location or lead.apollo_location,
            country=lead.country,
            raw_data=lead.lead_metadata or {},
        )

        agent = LeadScoringAgent()
        scored = await asyncio.to_thread(agent._score_single, apollo_lead, 1, 1)

        # Persist the updated scores
        lead.lead_score = scored.lead_score
        lead.priority = scored.priority
        lead.buying_probability = scored.buying_probability
        lead.score_breakdown = scored.score_breakdown
        lead.ai_summary = scored.ai_summary
        lead.strengths = scored.strengths
        lead.weaknesses = scored.weaknesses
        lead.pain_points = scored.pain_points
        lead.recommended_services = scored.recommended_services
        lead.recommended_contact_role = scored.recommended_contact_role
        lead.next_action = scored.next_action
        lead.scoring_method = scored.scoring_method
        db_manager.session.commit()

        return JSONResponse(content={
            "status": "success",
            "lead_score": scored.lead_score,
            "priority": scored.priority,
            "buying_probability": scored.buying_probability,
            "ai_summary": scored.ai_summary,
            "strengths": scored.strengths or [],
            "weaknesses": scored.weaknesses or [],
            "pain_points": scored.pain_points or [],
            "recommended_services": scored.recommended_services or [],
            "recommended_contact_role": scored.recommended_contact_role,
            "next_action": scored.next_action,
            "scoring_method": scored.scoring_method,
            "score_breakdown": scored.score_breakdown or {},
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db_manager.close()

@app.get("/api/stats", dependencies=[Depends(get_current_user)])
async def get_stats():
    db_manager = DatabaseManager()
    try:
        stats = db_manager.get_campaign_stats()
        return JSONResponse(content=stats)
    finally:
        db_manager.close()

async def run_campaign_task(companies: List[str], roles: List[str], strategy: str, location: str, industry: str, size: str, limit: int, filters: dict, mode: str):
    global campaign_status
    campaign_status["is_running"] = True
    campaign_status["current_step"] = "Initializing Apollo Pipeline..."
    
    def update_status(step_msg: str):
        campaign_status["current_step"] = step_msg
        
    try:
        import asyncio
        from main import run_lead_generation_campaign
        from agents.email_workflow_agents import run_email_pipeline
        
        update_status("Running Orchestrator from main.py...")
        # Since run_lead_generation_campaign is synchronous (uses asyncio.run internally),
        # we run it in a separate thread to prevent blocking or event loop conflicts.
        result = await asyncio.to_thread(
            run_lead_generation_campaign,
            companies=companies,
            roles=roles,
            followup_strategy=strategy,
            location=location,
            industry=industry,
            size=size,
            limit=limit,
            filters=filters
        )
        
        if result.get("status") == "success" and result.get("leads"):
            update_status("Starting Email Workflow...")
            await run_email_pipeline(result["leads"], update_status_cb=update_status)
            
        
    except Exception as e:
        campaign_status["current_step"] = f"Pipeline Error: {str(e)}"
    finally:
        campaign_status["is_running"] = False

@app.post("/api/start-campaign", dependencies=[Depends(get_current_user)])
async def start_campaign(
    background_tasks: BackgroundTasks,
    companies: Optional[str] = Form(""),
    roles: str = Form(...),
    strategy: str = Form("hybrid"),
    location: Optional[str] = Form("United States"),
    industry: Optional[str] = Form(""),
    size: Optional[str] = Form(""),
    limit: int = Form(10),
    filters: Optional[str] = Form(""),
    mode: str = Form("agent")
):
    if campaign_status["is_running"]:
        return JSONResponse(content={"error": "A campaign is already running"}, status_code=400)
    
    companies_list = [c.strip() for c in companies.split(",")] if companies else []
    roles_list = [r.strip() for r in roles.split(",")]
    
    filters_dict = {}
    if filters:
        try:
            filters_dict = json.loads(filters)
        except json.JSONDecodeError:
            for pair in filters.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    v_clean = v.strip().lower()
                    if v_clean == 'true': v_val = True
                    elif v_clean == 'false': v_val = False
                    else: v_val = v.strip()
                    filters_dict[k.strip()] = v_val
    
    background_tasks.add_task(run_campaign_task, companies_list, roles_list, strategy, location, industry, size, limit, filters_dict, mode)
    
    return JSONResponse(content={"message": "Campaign started in background"})

@app.get("/api/campaign-status")
async def get_campaign_status():
    return JSONResponse(content=campaign_status)

@app.post("/api/webhooks/sendgrid")
async def sendgrid_webhook(request: Request):
    """Handle SendGrid Event Webhooks for opens, clicks, etc."""
    events = await request.json()
    db_manager = DatabaseManager()
    
    for event in events:
        event_type = event.get("event") # open, click, delivered, bounce, etc.
        email = event.get("email")
        sg_id = event.get("sg_message_id")
        
        # Find lead by email
        lead = db_manager.session.query(Lead).filter(Lead.email == email).first()
        if lead:
            db_manager.log_interaction(
                lead_id=lead.id,
                event_type=event_type,
                details=event,
                email_id=sg_id
            )
            print(f"Webhook: Logged {event_type} for {email}")
            
    db_manager.close()
    return JSONResponse(content={"status": "processed"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

