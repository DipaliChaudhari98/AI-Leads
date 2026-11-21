from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models.sql_models import Base
from core.config import settings
from api.routes import leads, templates, outreach, analytics

app = FastAPI(title=settings.PROJECT_NAME)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database
@app.on_event("startup")
def startup():
    init_db()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Routes
app.include_router(leads.router, prefix="/api/leads", tags=["Leads"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(outreach.router, prefix="/api/outreach", tags=["Outreach"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Outreach Management System API"}
