import uuid
from core.database import SessionLocal, init_db
from models.sql_models import EmailTemplate

def seed_templates():
    init_db()
    db = SessionLocal()
    
    templates = [
        {
            "name": "standard_followup",
            "type": "follow_up_1",
            "subject_template": "Quick question for {{ name }}",
            "body_template": "Hi {{ name }},\n\nI'm following up on my previous email. I'd love to chat about how we can help {{ company }} grow.\n\nBest,\nGrowth Team",
            "variables": ["name", "company"]
        },
        {
            "name": "high_intent_followup",
            "type": "follow_up_1",
            "subject_template": "Saw you clicked the link, {{ name }}!",
            "body_template": "Hi {{ name }},\n\nI noticed you were interested in our previous email. Would you like to schedule a quick call to discuss further?\n\nBest,\nGrowth Team",
            "variables": ["name", "company"]
        },
        {
            "name": "reengagement_followup",
            "type": "follow_up_2",
            "subject_template": "Is the timing right for {{ company }}?",
            "body_template": "Hi {{ name }},\n\nI know you're busy, but I wanted to check in one last time to see if you're interested in streamlining your lead gen at {{ company }}.\n\nBest,\nGrowth Team",
            "variables": ["name", "company"]
        },
        {
            "name": "follow_up_1",
            "type": "follow_up_1",
            "subject_template": "Thought you'd like this, {{ name }}",
            "body_template": "Hi {{ name }},\n\nJust wanted to share some insights with you regarding {{ company }}.\n\nBest,\nGrowth Team",
            "variables": ["name", "company"]
        }
    ]

    for t_data in templates:
        existing = db.query(EmailTemplate).filter(EmailTemplate.name == t_data["name"]).first()
        if not existing:
            template = EmailTemplate(
                id=uuid.uuid4(),
                name=t_data["name"],
                type=t_data["type"],
                subject_template=t_data["subject_template"],
                body_template=t_data["body_template"],
                variables=t_data["variables"]
            )
            db.add(template)
            print(f"Added template: {t_data['name']}")
    
    db.commit()
    db.close()

if __name__ == "__main__":
    seed_templates()
