import os
from dotenv import load_dotenv
load_dotenv()
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from tools.db_tools import DatabaseManager
from models.sql_models import User

router = APIRouter()

# JWT Settings
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-jwt-key-for-local-dev")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Models
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
async def register(req: RegisterRequest):
    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
        
    allowed_domain = os.getenv("ALLOWED_EMAIL_DOMAIN", "")
    if allowed_domain and not req.email.endswith(f"@{allowed_domain.lstrip('@')}"):
        raise HTTPException(status_code=403, detail=f"Registration is restricted to @{allowed_domain.lstrip('@')} emails.")
    
    db = DatabaseManager()
    existing_user = db.session.query(User).filter(User.email == req.email).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered.")
        
    hashed_password = get_password_hash(req.password)
    new_user = User(name=req.name, email=req.email, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    
    # Generate access token for auto-login
    access_token = create_access_token(data={"sub": str(new_user.id), "email": new_user.email})
    db.close()
    
    return {
        "message": "User registered successfully.",
        "access_token": access_token,
        "token_type": "bearer",
        "email": new_user.email
    }

@router.post("/login")
async def login(req: LoginRequest):
    db = DatabaseManager()
    user = db.session.query(User).filter(User.email == req.email).first()
    db.close()
    
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"access_token": access_token, "token_type": "bearer", "email": user.email}

# Dependency to protect routes
def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
        
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("email")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
