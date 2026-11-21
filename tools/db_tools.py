from datetime import datetime, timedelta
from core.database import SessionLocal
from models.sql_models import Lead, EmailOutreach, LeadStatus
from models.apollo import ApolloLead
from typing import List, Union, Optional

class DatabaseManager:
    def __init__(self):
        self.session = SessionLocal()

    @staticmethod
    def _clean_industry(raw_val) -> "str | None":
        """Normalise industry strings from Apollo/PostgreSQL array format.

        Apollo sometimes returns: '{Analytics,Computer,"Network Management Software"}'
        This strips the curly-brace array wrapping and returns a clean string.
        """
        if not raw_val:
            return None
        import re as _re
        val = str(raw_val).strip()
        if val.startswith("{") and val.endswith("}"):
            val = val[1:-1]
            parts = _re.findall(r'"([^"]+)"|([^,]+)', val)
            items = [p[0] or p[1].strip() for p in parts if (p[0] or p[1].strip())]
            return ", ".join(items) if items else None
        return val

    def save_leads(self, profiles: List[ApolloLead]):
        """
        Deduplicate incoming scraped leads, remove any existing duplicates from the database,
        and then insert the fresh scraped leads.
        """
        # 1. Deduplicate incoming scraped data (keep first occurrence)
        unique_profiles = []
        seen_emails = set()
        seen_apollo_ids = set()
        
        for p in profiles:
            email = getattr(p, "email", None)
            apollo_id = getattr(p, "apollo_id", None)
            
            if (email and email in seen_emails) or (apollo_id and apollo_id in seen_apollo_ids):
                continue # Skip duplicate in scraped data
                
            if email: seen_emails.add(email)
            if apollo_id: seen_apollo_ids.add(apollo_id)
            unique_profiles.append(p)

        # 2. Process unique profiles
        for profile in unique_profiles:
            apollo_id = getattr(profile, "apollo_id", None)
            email = getattr(profile, "email", None)
            
            # Try to find existing lead by apollo_id or email
            existing_lead = None
            if apollo_id:
                existing_lead = self.session.query(Lead).filter(Lead.apollo_id == apollo_id).first()
            
            if not existing_lead and email:
                existing_lead = self.session.query(Lead).filter(Lead.email == email).first()
            
            if existing_lead:
                # Intelligent Merge: Keep existing data if new data is null
                existing_lead.name = profile.name or existing_lead.name
                existing_lead.company = profile.company or existing_lead.company
                existing_lead.title = profile.title or existing_lead.title
                existing_lead.linkedin_url = getattr(profile, "linkedin_url", None) or existing_lead.linkedin_url
                if getattr(profile, "raw_data", None):
                    existing_lead.lead_metadata = getattr(profile, "raw_data")
                if apollo_id:
                    existing_lead.apollo_id = apollo_id
                
                # Assign enriched data for existing lead
                existing_lead.apollo_location = getattr(profile, "apollo_location", None) or existing_lead.apollo_location
                existing_lead.location = getattr(profile, "location", None) or existing_lead.location
                existing_lead.city = getattr(profile, "city", None) or existing_lead.city
                existing_lead.state = getattr(profile, "state", None) or existing_lead.state
                existing_lead.country = getattr(profile, "country", None) or existing_lead.country
                
                new_tz = getattr(profile, "timezone", None)
                if new_tz and new_tz != "UTC":
                    existing_lead.timezone = new_tz
                elif not existing_lead.timezone:
                    existing_lead.timezone = new_tz or "UTC"
                    
                new_offset = getattr(profile, "utc_offset", None)
                if new_offset and new_offset != "UTC+00:00":
                    existing_lead.utc_offset = new_offset
                elif not existing_lead.utc_offset:
                    existing_lead.utc_offset = new_offset or "UTC+00:00"
                    
                existing_lead.business_hours_start = getattr(profile, "business_hours_start", "09:00") or existing_lead.business_hours_start
                existing_lead.business_hours_end = getattr(profile, "business_hours_end", "18:00") or existing_lead.business_hours_end
                
                raw = getattr(profile, "raw_data", {}) or {}
                raw_industry = raw.get("companyIndustry") or raw.get("industry")
                if raw_industry:
                    existing_lead.industry = self._clean_industry(raw_industry) or existing_lead.industry
                if raw.get("companyNumEmployees"):
                    existing_lead.employee_count = raw.get("companyNumEmployees") or existing_lead.employee_count

                existing_lead.source = getattr(profile, "source", None) or existing_lead.source or "apollo"
                
                # Merge AI scoring fields — only overwrite if new run produced a value
                if getattr(profile, "lead_score", None) is not None:
                    existing_lead.lead_score = profile.lead_score
                if getattr(profile, "score_breakdown", None):
                    existing_lead.score_breakdown = profile.score_breakdown
                if getattr(profile, "priority", None):
                    existing_lead.priority = profile.priority
                if getattr(profile, "buying_probability", None):
                    existing_lead.buying_probability = profile.buying_probability
                if getattr(profile, "ai_summary", None):
                    existing_lead.ai_summary = profile.ai_summary
                if getattr(profile, "scoring_method", None):
                    existing_lead.scoring_method = profile.scoring_method
                if getattr(profile, "strengths", None):
                    existing_lead.strengths = profile.strengths
                if getattr(profile, "weaknesses", None):
                    existing_lead.weaknesses = profile.weaknesses
                if getattr(profile, "recommended_services", None):
                    existing_lead.recommended_services = profile.recommended_services
                if getattr(profile, "recommended_contact_role", None):
                    existing_lead.recommended_contact_role = profile.recommended_contact_role
                if getattr(profile, "pain_points", None):
                    existing_lead.pain_points = profile.pain_points
                if getattr(profile, "next_action", None):
                    existing_lead.next_action = profile.next_action
                
                # If existing lead has no initial date, set it to today and recalculate
                if not existing_lead.initial_email_date:
                    scheduled_utc, scheduled_local = self._calculate_scheduled_date(existing_lead)
                    existing_lead.initial_email_date = scheduled_utc
                    existing_lead.initial_email_date_local = scheduled_local
                    existing_lead.set_followup_dates()
                    
            else:
                # Create new lead from fresh scraped data
                new_lead = Lead(
                    name=profile.name or "Unknown",
                    email=email,
                    company=profile.company or "Unknown",
                    title=profile.title or "Unknown",
                    apollo_id=apollo_id,
                    linkedin_url=getattr(profile, "linkedin_url", None),
                    status=LeadStatus.RESEARCHED,
                    source=getattr(profile, "source", None) or "apollo",
                    lead_metadata=getattr(profile, "raw_data", {"source": "apollo"}),
                    location=getattr(profile, "location", None),
                    apollo_location=getattr(profile, "apollo_location", None),
                    city=getattr(profile, "city", None),
                    state=getattr(profile, "state", None),
                    country=getattr(profile, "country", None),
                    timezone=getattr(profile, "timezone", None),
                    utc_offset=getattr(profile, "utc_offset", None),
                    business_hours_start=getattr(profile, "business_hours_start", "09:00"),
                    business_hours_end=getattr(profile, "business_hours_end", "18:00"),
                    industry=self._clean_industry(
                        getattr(profile, "raw_data", {}).get("companyIndustry")
                        or getattr(profile, "raw_data", {}).get("industry")
                    ),
                    employee_count=getattr(profile, "raw_data", {}).get("companyNumEmployees"),
                    # AI Lead Intelligence
                    lead_score=getattr(profile, "lead_score", None),
                    score_breakdown=getattr(profile, "score_breakdown", None),
                    priority=getattr(profile, "priority", None),
                    buying_probability=getattr(profile, "buying_probability", None),
                    ai_summary=getattr(profile, "ai_summary", None),
                    scoring_method=getattr(profile, "scoring_method", None),
                    strengths=getattr(profile, "strengths", None),
                    weaknesses=getattr(profile, "weaknesses", None),
                    pain_points=getattr(profile, "pain_points", None),
                    recommended_services=getattr(profile, "recommended_services", None),
                    recommended_contact_role=getattr(profile, "recommended_contact_role", None),
                    next_action=getattr(profile, "next_action", None),
                )
                scheduled_utc, scheduled_local = self._calculate_scheduled_date(new_lead)
                new_lead.initial_email_date = scheduled_utc
                new_lead.initial_email_date_local = scheduled_local
                new_lead.set_followup_dates()
                self.session.add(new_lead)
        
        self.session.commit()

    def _calculate_scheduled_date(self, lead: Lead) -> datetime:
        import pytz
        
        utc_now = datetime.utcnow()
        if not lead.timezone or lead.timezone == "UTC":
            return utc_now + timedelta(days=1), utc_now + timedelta(days=1)
            
        try:
            tz = pytz.timezone(lead.timezone)
            # We must determine current time in lead's local timezone
            local_time = pytz.UTC.localize(utc_now).astimezone(tz)
            
            bh_start_str = lead.business_hours_start or "09:00"
            bh_end_str = lead.business_hours_end or "18:00"
            
            start_hour, start_minute = map(int, bh_start_str.split(':'))
            end_hour, end_minute = map(int, bh_end_str.split(':'))
            
            bh_start_time = local_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            bh_end_time = local_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            
            if local_time < bh_start_time:
                scheduled_local = bh_start_time + timedelta(minutes=30)
            elif local_time > bh_end_time:
                scheduled_local = bh_start_time + timedelta(days=1, minutes=30)
            else:
                scheduled_local = local_time + timedelta(hours=1)
                if scheduled_local > bh_end_time:
                    scheduled_local = bh_start_time + timedelta(days=1, minutes=30)
                    
            return scheduled_local.astimezone(pytz.UTC).replace(tzinfo=None), scheduled_local.replace(tzinfo=None)
        except Exception as e:
            return utc_now + timedelta(days=1), utc_now + timedelta(days=1)

    def get_leads_to_personalize(self, status: str = "researched") -> List[Lead]:
        return self.session.query(Lead).filter(Lead.status == status, Lead.is_active == True).all()

    def get_leads_by_status(self, status: str) -> List[Lead]:
        return self.session.query(Lead).filter(Lead.status == status, Lead.is_active == True).all()

    def get_lead_details(self, lead_id: int) -> Optional[Lead]:
        return self.session.query(Lead).filter(Lead.id == lead_id).first()

    def log_email_sent(self, lead_id: int, subject: str, body: str, sendgrid_id: str, email_type: str = "initial"):
        # Create outreach entry
        outreach = EmailOutreach(
            lead_id=lead_id,
            subject=subject,
            body=body,
            sendgrid_message_id=sendgrid_id,
            sent_at=datetime.utcnow(),
            status="sent",
            type=email_type
        )
        self.session.add(outreach)
        
        # Update lead status
        lead = self.session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = LeadStatus.SENT
            lead.last_interaction_at = datetime.utcnow()
            # If this is the initial email, set the initial date and recalculate
            if email_type == "initial" and not lead.initial_email_date:
                lead.initial_email_date = datetime.utcnow()
                lead.set_followup_dates()
            else:
                lead.next_followup_date = datetime.utcnow() + timedelta(days=3)
            # followup_count is not reset to 0 here because it might be a follow-up email itself
            
        self.session.commit()

    def get_leads_needing_followup(self):
        now = datetime.utcnow()
        return self.session.query(Lead).filter(
            Lead.is_active == True,
            Lead.next_followup_date <= now,
            Lead.followup_count < Lead.max_followups
        ).all()

    def schedule_followup(self, lead_id: int, days_delay: int):
        lead = self.session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.next_followup_date = datetime.utcnow() + timedelta(days=days_delay)
            self.session.commit()

    def update_lead_status(self, lead_id: int, status: str):
        lead = self.session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = status
            self.session.commit()

    def log_interaction(self, lead_id: int, event_type: str, details: dict = None, email_id: str = None):
        """Log a lead interaction (open, click, reply) and update lead status accordingly."""
        # Update lead state based on interaction
        lead = self.session.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.last_interaction_at = datetime.utcnow()
            if event_type == "reply":
                lead.status = LeadStatus.REPLIED
            elif event_type == "click" and lead.status not in [LeadStatus.REPLIED, LeadStatus.CLICKED]:
                lead.status = LeadStatus.CLICKED
            elif event_type == "open" and lead.status not in [LeadStatus.REPLIED, LeadStatus.CLICKED, LeadStatus.OPENED]:
                lead.status = LeadStatus.OPENED
        
        self.session.commit()

    def get_campaign_stats(self):
        total_leads = self.session.query(Lead).count()
        total_emails = self.session.query(EmailOutreach).count()
        
        # Count by status
        from sqlalchemy import func
        status_counts = self.session.query(Lead.status, func.count(Lead.status)).group_by(Lead.status).all()
        
        stats = {
            "total_leads": total_leads,
            "total_emails_sent": total_emails,
            "statuses": {status: count for status, count in status_counts}
        }
        return stats

    def close(self):
        self.session.close()

    def __del__(self):
        try:
            self.session.close()
        except:
            pass
