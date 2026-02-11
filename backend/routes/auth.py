"""
Authentication routes for multi-tenant SCORM authoring tool
Supports both email/password and Google OAuth authentication
"""
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import os
import uuid
import httpx
import bcrypt

router = APIRouter(prefix="/auth", tags=["Authentication"])

# MongoDB connection (will be set from main server)
db = None

def set_db(database):
    """Set the database connection from main server"""
    global db
    db = database

def now_utc():
    return datetime.now(timezone.utc)

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current user from session token.
    Checks cookies first, then Authorization header.
    """
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        return None
    
    # Find session
    session = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session:
        return None
    
    # Check expiry
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < now_utc():
        return None
    
    # Get user
    user = await db.users.find_one(
        {"user_id": session["user_id"]},
        {"_id": 0, "passwordHash": 0}
    )
    
    if not user or not user.get("isActive", True):
        return None
    
    # Get company info if user belongs to one
    if user.get("companyId"):
        company = await db.companies.find_one(
            {"id": user["companyId"]},
            {"_id": 0}
        )
        if company:
            user["company"] = company
    
    return user

async def require_auth(request: Request) -> Dict[str, Any]:
    """Dependency that requires authentication"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

async def require_super_admin(request: Request) -> Dict[str, Any]:
    """Dependency that requires super admin role"""
    user = await require_auth(request)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user

async def require_company_admin(request: Request) -> Dict[str, Any]:
    """Dependency that requires company admin or super admin role"""
    user = await require_auth(request)
    if user.get("role") not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def create_session_response(response: Response, session_token: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Set session cookie and return user data"""
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    return user_data


# ============================================
# Authentication Endpoints
# ============================================

@router.post("/login")
async def login(request: Request, response: Response):
    """Login with email and password"""
    body = await request.json()
    email = body.get("email", "").lower().strip()
    password = body.get("password", "")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    
    # Find user
    user = await db.users.find_one(
        {"email": email},
        {"_id": 0}
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.get("isActive", True):
        raise HTTPException(status_code=401, detail="Account is deactivated")
    
    if not user.get("passwordHash"):
        raise HTTPException(status_code=401, detail="Please use Google login for this account")
    
    if not verify_password(password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_token = f"session_{uuid.uuid4().hex}"
    expires_at = now_utc() + timedelta(days=7)
    
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": now_utc()
    })
    
    # Update last login
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"lastLogin": now_utc()}}
    )
    
    # Remove sensitive data
    user.pop("passwordHash", None)
    
    # Get company info
    if user.get("companyId"):
        company = await db.companies.find_one(
            {"id": user["companyId"]},
            {"_id": 0}
        )
        if company:
            user["company"] = company
    
    return create_session_response(response, session_token, {"user": user, "token": session_token})


@router.post("/google")
async def google_auth(request: Request, response: Response):
    """
    Process Google OAuth session from Emergent Auth
    Frontend calls this with session_id from URL fragment
    """
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")
    
    # Call Emergent Auth to get user data
    async with httpx.AsyncClient() as client:
        try:
            auth_response = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
                timeout=10.0
            )
            
            if auth_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            google_data = auth_response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Auth service error: {str(e)}")
    
    email = google_data.get("email", "").lower()
    name = google_data.get("name", "")
    picture = google_data.get("picture", "")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")
    
    # Check if user exists
    existing_user = await db.users.find_one(
        {"email": email},
        {"_id": 0}
    )
    
    if existing_user:
        # Update existing user
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "name": name,
                "picture": picture,
                "lastLogin": now_utc(),
                "updatedAt": now_utc()
            }}
        )
        user = existing_user
        user["name"] = name
        user["picture"] = picture
    else:
        # For new users via Google OAuth, they need to be invited to a company first
        # Or we create them without a company (pending assignment)
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "companyId": None,  # No company until assigned
            "role": "editor",  # Default role
            "isActive": True,
            "createdAt": now_utc(),
            "updatedAt": now_utc()
        }
        await db.users.insert_one(user)
    
    # Create session
    session_token = f"session_{uuid.uuid4().hex}"
    expires_at = now_utc() + timedelta(days=7)
    
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": now_utc()
    })
    
    # Remove sensitive data
    user.pop("passwordHash", None)
    user.pop("_id", None)
    
    # Get company info
    if user.get("companyId"):
        company = await db.companies.find_one(
            {"id": user["companyId"]},
            {"_id": 0}
        )
        if company:
            user["company"] = company
    
    return create_session_response(response, session_token, {"user": user, "token": session_token})


@router.get("/me")
async def get_me(request: Request):
    """Get current authenticated user"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}


@router.post("/change-password")
async def change_password(request: Request):
    """Change password for current user"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    body = await request.json()
    current_password = body.get("currentPassword", "")
    new_password = body.get("newPassword", "")
    
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    # Get user with password hash
    user_doc = await db.users.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0}
    )
    
    # If user has a password, verify current one
    if user_doc.get("passwordHash"):
        if not current_password:
            raise HTTPException(status_code=400, detail="Current password required")
        if not verify_password(current_password, user_doc["passwordHash"]):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Update password
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "passwordHash": hash_password(new_password),
            "updatedAt": now_utc()
        }}
    )
    
    return {"message": "Password changed successfully"}
