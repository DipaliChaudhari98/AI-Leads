from core.database import SessionLocal
from models.sql_models import User

session = SessionLocal()
try:
    users = session.query(User).all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"ID: {u.id}, Name: {u.name}, Email: {u.email}")
finally:
    session.close()
