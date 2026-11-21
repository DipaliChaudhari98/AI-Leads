"""
Run this script ONCE to create a default admin user in the database.
Usage:
    python create_admin.py
    python create_admin.py --email you@example.com --password yourpassword --name "Your Name"
"""
import argparse
import os
import sys
import bcrypt
import uuid

# Load env first
from dotenv import load_dotenv
load_dotenv()

from core.database import init_db, SessionLocal
from models.sql_models import User

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_admin(email: str, password: str, name: str):
    init_db()
    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            print(f"[SKIP] User '{email}' already exists.")
            return

        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            password_hash=get_password_hash(password)
        )
        session.add(user)
        session.commit()
        print(f"[OK] Admin user created!")
        print(f"     Email   : {email}")
        print(f"     Password: {password}")
        print(f"\nYou can now log in at http://localhost:5173/login")
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a default admin user")
    parser.add_argument("--email",    default="admin@sigasystems.com", help="Email address")
    parser.add_argument("--password", default="Admin@1234",            help="Password")
    parser.add_argument("--name",     default="Admin",                  help="Display name")
    args = parser.parse_args()

    create_admin(args.email, args.password, args.name)
