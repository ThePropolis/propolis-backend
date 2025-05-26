from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import os
from database import supabase
from dotenv import load_dotenv
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = 3600 
ALGORITHM="HS256"
router = APIRouter()

class UserCredentials(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    email: str
    full_name: str
    role: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# In your login endpoint - store user data in JWT
@router.post("/api/auth/login")
async def login(credentials: UserCredentials):
    try:
        # Authenticate with Supabase
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if response.user:
            # Get user metadata from Supabase response
            user_metadata = response.user.user_metadata or {}
            print(user_metadata)
            # Create JWT with user data included
            token_data = {
                "sub": credentials.email,
                "user_id": response.user.id,
                "full_name": user_metadata.get("full_name", ""),
                "role": user_metadata.get("role", "user"),
                "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            }
            
            access_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "email": credentials.email,
                    "full_name": user_metadata.get("full_name", ""),
                    "role": user_metadata.get("role", "user")
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")

# Updated get_current_user - no Supabase calls needed
@router.get("/api/auth/me", response_model=User)
async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token missing or invalid")
    
    try:
        # Decode JWT and extract user data
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        
        email = payload.get("sub")
        
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Return user data directly from JWT
        return {
            "email": email,
            "full_name": payload.get("full_name", ""),
            "role": payload.get("role", "user")
        }
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/api/auth/username")
async def update_username():
    response = supabase.auth.update_user({
    "data": {
        "role": "ADMIN",
        "full_name": "Misha Gurevich"
    }})
    return response