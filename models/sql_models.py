from sqlalchemy import true
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LeadStatus(str, enum.Enum):
    NEW = "new"
    RESEARCHED = "researched"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    CLOSED = "closed"

class EmailType(str, enum.Enum):
    INITIAL = "initial"
    FOLLOW_UP_1 = "follow_up_1"
    FOLLOW_UP_2 = "follow_up_2"
    CUSTOM = "custom"

class FollowUpStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    company = Column(String)
    title = Column(String)
    apollo_id = Column(String, unique=True, nullable=True)
    linkedin_url = Column(String, nullable=True)
    status = Column(String, default=LeadStatus.NEW)
    is_active = Column(Boolean, default=True)
    
    # Enrichment Data
    industry = Column(String, nullable=True)
    employee_count = Column(String, nullable=True)
    location = Column(String, nullable=True)
    apollo_location = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    timezone = Column(String, nullable=True)
    utc_offset = Column(String, nullable=True)
    business_hours_start = Column(String, default="09:00")
    business_hours_end = Column(String, default="18:00")
    lead_metadata = Column(JSON, default={})
    
    # ── AI Lead Intelligence (populated by LLM-based LeadScoringAgent) ────────
    lead_score = Column(Integer, nullable=True)                # 0-100 composite score
    score_breakdown = Column(JSON, nullable=True)              # Per-dimension raw scores
    priority = Column(String, nullable=True)                   # Very High / High / Medium / Low / Very Low
    buying_probability = Column(String, nullable=True)         # High / Medium / Low
    ai_summary = Column(Text, nullable=True)                   # LLM-generated narrative
    strengths = Column(JSON, nullable=True)                    # List[str] positive signals
    weaknesses = Column(JSON, nullable=True)                   # List[str] risk factors
    recommended_services = Column(JSON, nullable=True)         # List[str] SIGA services to pitch
    recommended_contact_role = Column(String, nullable=True)   # Best role to contact
    pain_points = Column(JSON, nullable=True)                  # Grounded pain points [{point, evidence, relatedService}]
    next_action = Column(Text, nullable=True)                  # Suggested outreach step

    scoring_method = Column(String, nullable=True)             # "llm" or "rule_based"
    
    # Sequence Tracking
    followup_count = Column(Integer, default=0)
    max_followups = Column(Integer, default=3)
    followup_strategy = Column(String, default="hybrid")
    source = Column(String, nullable=True)
   


    initial_email_date = Column(DateTime, default=datetime.utcnow)
    initial_email_date_local = Column(DateTime, nullable=True)
    initial_email_status = Column(String, nullable=True)

    last_interaction_at = Column(DateTime, nullable=True)
    next_followup_date = Column(DateTime, nullable=True)
    next_followup_date_local = Column(DateTime, nullable=True)
    next_followup_status = Column(String, nullable=True)

    last_followup_date = Column(DateTime, nullable=True)
    last_followup_date_local = Column(DateTime, nullable=True)
    last_followup_status = Column(String, nullable=True)


    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add a method to your model class to set these dates
    def set_followup_dates(self):
        from datetime import timedelta, datetime
        import pytz
        
        if self.initial_email_date:
            next_f = self.initial_email_date + timedelta(days=3)
            last_f = self.initial_email_date + timedelta(days=7)
            
            if self.timezone:
                try:
                    tz = pytz.timezone(self.timezone)
                    
                    # Get exact local hour and minute of the initial email
                    initial_local = pytz.UTC.localize(self.initial_email_date).astimezone(tz)
                    target_hour = initial_local.hour
                    target_minute = initial_local.minute
                    
                    next_local = pytz.UTC.localize(next_f).astimezone(tz)
                    last_local = pytz.UTC.localize(last_f).astimezone(tz)
                    
                    # Force follow-ups to match that exact local time
                    next_local = next_local.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                    last_local = last_local.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                    
                    self.next_followup_date = next_local.astimezone(pytz.UTC).replace(tzinfo=None)
                    self.last_followup_date = last_local.astimezone(pytz.UTC).replace(tzinfo=None)
                    
                    self.next_followup_date_local = next_local.replace(tzinfo=None)
                    self.last_followup_date_local = last_local.replace(tzinfo=None)
                    return
                except Exception:
                    pass
                    
            self.next_followup_date = next_f
            self.last_followup_date = last_f
            
            # If we don't have timezone, local is same as UTC
            self.next_followup_date_local = next_f
            self.last_followup_date_local = last_f
    
    outreach = relationship("EmailOutreach", back_populates="lead")

class EmailOutreach(Base):
    __tablename__ = "email_outreach"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    
    subject = Column(String)
    body = Column(Text)
    status = Column(String, default="draft") # draft, pending, approved, rejected, sent, failed
    type = Column(String) # initial, follow_up_1, etc.
    
    sent_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    
    lead = relationship("Lead", back_populates="outreach")


# class FollowUpSchema(Base):
#     __tablename__="follow_up"
#     id=Column(Integer,primary_key=true)

#     lead_id=Column(Integer,ForeignKey("leads.id"))
#     lead_name=Column(String,ForeignKey("leads.name"))

#       # Follow-up 1
#     followup_1_subject = Column(String, nullable=True)
#     followup_1_body = Column(Text, nullable=True)
#     followup_1_date = Column(DateTime, nullable=True)
#     followup_1_status = Column(Enum(FollowUpStatus), default=FollowUpStatus.PENDING)

#     # Follow-up 2
#     followup_2_subject = Column(String, nullable=True)
#     followup_2_body = Column(Text, nullable=True)
#     followup_2_date = Column(DateTime, nullable=True)
#     followup_2_status = Column(Enum(FollowUpStatus), default=FollowUpStatus.PENDING)

#     # Follow-up 3
#     followup_3_subject = Column(String, nullable=True)
#     followup_3_body = Column(Text, nullable=True)
#     followup_3_date = Column(DateTime, nullable=True)
#     followup_3_status = Column(Enum(FollowUpStatus), default=FollowUpStatus.PENDING)

#     created_at = Column(DateTime, default=datetime.utcnow)
    

from sqlalchemy import event

@event.listens_for(Lead, 'before_insert')
@event.listens_for(Lead, 'before_update')
def update_lead_dates(mapper, connection, target):
    target.set_followup_dates()
