from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import os
from database import supabase
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 60))

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

@router.post("/auth/login", response_model=Token)
async def login(credentials: UserCredentials):
    # Authenticate with Supabase
    auth_response = supabase.auth.sign_in_with_password({
        "email": credentials.email,
        "password": credentials.password,
    })

    if "error" in auth_response:
        raise HTTPException(status_code=401, detail=auth_response["error"]["message"])

    # Create JWT
    token = create_access_token({"sub": credentials.email})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/auth/me", response_model=User)
async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token missing or invalid")

    try:
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Fetch user from Supabase
        user_response = supabase.auth.admin.get_user_by_email(email)
        if "error" in user_response:
            raise HTTPException(status_code=401, detail=user_response["error"]["message"])

        return {"email": email}

    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e
