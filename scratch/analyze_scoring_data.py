import os
from dotenv import load_dotenv
from core.database import SessionLocal
from models.sql_models import Lead

load_dotenv()

def analyze():
    session = SessionLocal()
    try:
        leads = session.query(Lead).all()
        total = len(leads)
        print(f"Total leads: {total}")
        
        scored_leads = [l for l in leads if l.lead_score is not None]
        print(f"Leads with lead_score populated: {len(scored_leads)} / {total}")
        
        ranges = {
            "None": 0,
            "0-39 (Very Low)": 0,
            "40-59 (Low)": 0,
            "60-74 (Medium)": 0,
            "75-89 (High)": 0,
            "90-100 (Very High)": 0
        }
        
        priority_counts = {}
        bp_counts = {}
        
        has_summary = 0
        has_strengths = 0
        has_weaknesses = 0
        has_services = 0
        has_next_action = 0
        
        for l in leads:
            # Score
            if l.lead_score is None:
                ranges["None"] += 1
            else:
                score = l.lead_score
                if score < 40:
                    ranges["0-39 (Very Low)"] += 1
                elif score < 60:
                    ranges["40-59 (Low)"] += 1
                elif score < 75:
                    ranges["60-74 (Medium)"] += 1
                elif score < 90:
                    ranges["75-89 (High)"] += 1
                else:
                    ranges["90-100 (Very High)"] += 1
            
            # Priority
            p = l.priority
            priority_counts[p] = priority_counts.get(p, 0) + 1
            
            # Buying Probability
            bp = l.buying_probability
            bp_counts[bp] = bp_counts.get(bp, 0) + 1
            
            # AI fields
            if l.ai_summary: has_summary += 1
            if l.strengths: has_strengths += 1
            if l.weaknesses: has_weaknesses += 1
            if l.recommended_services: has_services += 1
            if l.next_action: has_next_action += 1
            
        print("\n--- Lead Score Distribution ---")
        for k, v in ranges.items():
            print(f"  {k}: {v}")
            
        print("\n--- Priority Distribution ---")
        for k, v in priority_counts.items():
            print(f"  {k}: {v}")
            
        print("\n--- Buying Probability Distribution ---")
        for k, v in bp_counts.items():
            print(f"  {k}: {v}")
            
        print("\n--- AI Fields Completeness ---")
        print(f"  AI Summary: {has_summary} / {total}")
        print(f"  Strengths: {has_strengths} / {total}")
        print(f"  Weaknesses: {has_weaknesses} / {total}")
        print(f"  Recommended Services: {has_services} / {total}")
        print(f"  Next Action: {has_next_action} / {total}")
        
        # Sort scored leads to show examples
        scored_leads.sort(key=lambda x: x.lead_score, reverse=True)
        if scored_leads:
            print("\n--- Top 3 Scored Leads ---")
            for l in scored_leads[:3]:
                print(f"  ID: {l.id} | Name: {l.name} | Company: {l.company} | Score: {l.lead_score} | Priority: {l.priority} | Buying Prob: {l.buying_probability}")
                print(f"    Summary: {l.ai_summary}")
                print(f"    Services: {l.recommended_services}")
                print(f"    Next Action: {l.next_action}")
                print("-" * 50)
                
            print("\n--- Bottom 3 Scored Leads ---")
            for l in scored_leads[-3:]:
                print(f"  ID: {l.id} | Name: {l.name} | Company: {l.company} | Score: {l.lead_score} | Priority: {l.priority} | Buying Prob: {l.buying_probability}")
                print(f"    Summary: {l.ai_summary}")
                print(f"    Services: {l.recommended_services}")
                print(f"    Next Action: {l.next_action}")
                print("-" * 50)
                
    finally:
        session.close()

if __name__ == "__main__":
    analyze()
