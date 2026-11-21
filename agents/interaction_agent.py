from crewai import Agent
from crewai.tools import tool
from tools.db_tools import DatabaseManager
from datetime import datetime

@tool("log_lead_interaction")
def log_lead_interaction(query: str) -> str:
    """Log an interaction with a lead. Input format: 'lead_id=1,type=open,details=optional_json'"""
    parts = {k.strip(): v.strip() for k, v in (item.split("=", 1) for item in query.split(","))}
    lead_id = int(parts.get("lead_id", 1))
    interaction_type = parts.get("type", "open")
    details = parts.get("details", "{}")

    import json
    db_manager = DatabaseManager()
    db_manager.log_interaction(
        lead_id=lead_id,
        event_type=interaction_type,
        details=json.loads(details) if isinstance(details, str) and details.startswith("{") else {"raw": details}
    )
    db_manager.close()
    return f"Interaction of type '{interaction_type}' logged for lead {lead_id}."

def create_interaction_agent(llm=None):
    return Agent(
        role="Lead Engagement Tracker",
        goal="Monitor and log all interactions from leads to provide insights for the follow-up strategy.",
        backstory=(
            "You are analytical and focused on engagement metrics. You track every open, click, "
            "and reply to ensure the follow-up cadence is perfectly tailored to each lead's behavior."
        ),
        tools=[log_lead_interaction],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
