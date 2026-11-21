import os
from dotenv import load_dotenv
from core.database import SessionLocal
from models.sql_models import Lead

load_dotenv()

def audit_db():
    session = SessionLocal()
    try:
        total = session.query(Lead).count()
        missing_score = session.query(Lead).filter(Lead.lead_score == None).count()
        missing_priority = session.query(Lead).filter(Lead.priority == None).count()
        missing_buying_prob = session.query(Lead).filter(Lead.buying_probability == None).count()
        missing_ai_summary = session.query(Lead).filter(Lead.ai_summary == None).count()
        missing_strengths = session.query(Lead).filter(Lead.strengths == None).count()
        missing_weaknesses = session.query(Lead).filter(Lead.weaknesses == None).count()
        missing_rec_services = session.query(Lead).filter(Lead.recommended_services == None).count()
        missing_rec_role = session.query(Lead).filter(Lead.recommended_contact_role == None).count()
        missing_next_action = session.query(Lead).filter(Lead.next_action == None).count()
        missing_score_breakdown = session.query(Lead).filter(Lead.score_breakdown == None).count()
        missing_industry = session.query(Lead).filter(Lead.industry == None).count()
        missing_location = session.query(Lead).filter(Lead.location == None).count()
        missing_timezone = session.query(Lead).filter(Lead.timezone == None).count()
        missing_source = session.query(Lead).filter(Lead.source == None).count()

        print(f"=== DATABASE FIELD AUDIT ===")
        print(f"Total leads          : {total}")
        print(f"--- AI Intelligence Fields ---")
        print(f"Missing lead_score          : {missing_score}")
        print(f"Missing score_breakdown     : {missing_score_breakdown}")
        print(f"Missing priority            : {missing_priority}")
        print(f"Missing buying_probability  : {missing_buying_prob}")
        print(f"Missing ai_summary          : {missing_ai_summary}")
        print(f"Missing strengths           : {missing_strengths}")
        print(f"Missing weaknesses          : {missing_weaknesses}")
        print(f"Missing recommended_services: {missing_rec_services}")
        print(f"Missing rec_contact_role    : {missing_rec_role}")
        print(f"Missing next_action         : {missing_next_action}")
        print(f"--- Enrichment Fields ---")
        print(f"Missing industry            : {missing_industry}")
        print(f"Missing location            : {missing_location}")
        print(f"Missing timezone            : {missing_timezone}")
        print(f"Missing source              : {missing_source}")
        
        # Sample a lead to see data
        sample = session.query(Lead).filter(Lead.lead_score != None).first()
        if sample:
            print(f"\n--- Sample Lead (ID: {sample.id}) ---")
            print(f"Name        : {sample.name}")
            print(f"Score       : {sample.lead_score}")
            print(f"Breakdown   : {sample.score_breakdown}")
            print(f"Priority    : {sample.priority}")
            print(f"Probability : {sample.buying_probability}")
            print(f"Summary     : {sample.ai_summary}")
            print(f"Strengths   : {sample.strengths}")
            print(f"Services    : {sample.recommended_services}")
            print(f"Next Action : {sample.next_action}")
            print(f"Industry    : {sample.industry}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    audit_db()
