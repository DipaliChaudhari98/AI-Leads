"""
Migration: Add AI Lead Intelligence columns to the leads table.
Run once:  python migrate_ai_scoring.py
Safe to re-run — uses IF NOT EXISTS on every column.
"""
from sqlalchemy import text
from core.database import engine

AI_COLUMNS = [
    ("lead_score",               "INTEGER"),
    ("score_breakdown",          "JSONB"),
    ("priority",                 "VARCHAR"),
    ("buying_probability",       "VARCHAR"),
    ("ai_summary",               "TEXT"),
    ("strengths",                "JSONB"),
    ("weaknesses",               "JSONB"),
    ("recommended_services",     "JSONB"),
    ("recommended_contact_role", "VARCHAR"),
    ("pain_points",              "JSONB"),
    ("next_action",              "TEXT"),
    ("scoring_method",           "VARCHAR"),
]

def migrate():
    added = []
    skipped = []

    with engine.begin() as conn:
        for col_name, col_type in AI_COLUMNS:
            try:
                conn.execute(
                    text(f"ALTER TABLE leads ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
                )
                added.append(col_name)
            except Exception as e:
                skipped.append(f"{col_name}: {e}")

    if added:
        print(f"[OK] Migration complete. Columns added/verified: {', '.join(added)}")
    if skipped:
        print(f"[WARN] Skipped: {skipped}")

if __name__ == "__main__":
    migrate()
