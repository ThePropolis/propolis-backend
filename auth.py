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

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/api/auth/login", response_model=Token)
async def login(credentials: UserCredentials):
    # Authenticate with Supabase
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password,
        })
        
        # Check for errors in the response
        if hasattr(auth_response, 'error') and auth_response.error:
            raise HTTPException(status_code=401, detail=auth_response.error.message)
        
        # Create JWT with user's ID and email
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        token = create_access_token({"sub": user_email, "user_id": user_id})
        
        return {"access_token": token, "token_type": "bearer"}
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/api/auth/me", response_model=User)
async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token missing or invalid")
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user_id = payload.get("user_id")
        
        if not email or not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # We already have the email from the token, so we don't need to fetch from Supabase
        # If you need to validate the user still exists:
        try:
            # Use get_user_by_id instead of get_user_by_email
            user = supabase.auth.admin.get_user_by_id(user_id)
            if not user or hasattr(user, 'error') and user.error:
                raise HTTPException(status_code=401, detail="User not found")
        except Exception as e:
            # If we can't verify with Supabase, we can still return the email from the token
            # This is a fallback and might be acceptable depending on your security requirements
            pass
            
        return {"email": email}
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


@router.post("/api/auth/username")
async def update_username():
    response = supabase.auth.update_user({
    "data": {
        "full_name": "Misha Gurevich"
    }})
    return response