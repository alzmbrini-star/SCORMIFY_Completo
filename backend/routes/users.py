"""
User management routes
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Optional, List, Dict, Any
import uuid
import bcrypt

from routes.deps import db, now_utc

router = APIRouter(prefix="/users", tags=["Users"])

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Import auth helpers
from routes.auth import require_auth, require_super_admin, require_company_admin


@router.get("")
async def list_users(request: Request, user: Dict = Depends(require_auth)):
    """
    List users:
    - Super Admin: Can see all users
    - Company Admin: Can see users in their company
    - Editor: Cannot list users
    """
    query = {}
    
    if user.get("role") == "super_admin":
        # Super admin sees all users
        pass
    elif user.get("role") == "company_admin":
        # Company admin sees only their company's users
        query["companyId"] = user.get("companyId")
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    users = await db.users.find(
        query,
        {"_id": 0, "passwordHash": 0}
    ).to_list(1000)
    
    return users


@router.post("")
async def create_user(request: Request, user: Dict = Depends(require_company_admin)):
    """
    Create a new user:
    - Super Admin: Can create users in any company with any role
    - Company Admin: Can create users only in their company with 'editor' role
    """
    body = await request.json()
    
    email = body.get("email", "").lower().strip()
    name = body.get("name", "").strip()
    password = body.get("password", "")
    company_id = body.get("companyId")
    role = body.get("role", "editor")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    
    # Check permissions
    if user.get("role") == "company_admin":
        # Company admin can only create users in their company
        company_id = user.get("companyId")
        # Company admin can only create editors, not other admins
        if role != "editor":
            raise HTTPException(status_code=403, detail="You can only create editor users")
    elif user.get("role") == "super_admin":
        # Super admin can create users in any company
        if not company_id and role != "super_admin":
            raise HTTPException(status_code=400, detail="Company ID is required")
    
    # Check if email already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Verify company exists and is active
    if company_id:
        company = await db.companies.find_one({"id": company_id, "isActive": True})
        if not company:
            raise HTTPException(status_code=400, detail="Company not found or inactive")
        
        # Check user limit
        current_users = await db.users.count_documents({"companyId": company_id, "isActive": True})
        if current_users >= company.get("maxUsers", 10):
            raise HTTPException(status_code=400, detail="Company user limit reached")
    
    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": email,
        "name": name,
        "picture": None,
        "companyId": company_id,
        "role": role,
        "isActive": True,
        "createdAt": now_utc(),
        "updatedAt": now_utc()
    }
    
    # Add password if provided
    if password:
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        new_user["passwordHash"] = hash_password(password)
    
    await db.users.insert_one(new_user)
    new_user.pop("_id", None)
    new_user.pop("passwordHash", None)
    
    return new_user


@router.get("/{user_id}")
async def get_user(user_id: str, request: Request, user: Dict = Depends(require_auth)):
    """Get user details"""
    target_user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "passwordHash": 0}
    )
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if user.get("role") == "super_admin":
        pass  # Can view any user
    elif user.get("role") == "company_admin":
        if target_user.get("companyId") != user.get("companyId"):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        # Regular users can only view themselves
        if target_user["user_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return target_user


@router.put("/{user_id}")
async def update_user(user_id: str, request: Request, user: Dict = Depends(require_auth)):
    """
    Update user:
    - Super Admin: Can update any user
    - Company Admin: Can update users in their company (except role to admin)
    - Editor: Can only update their own profile (name only)
    """
    body = await request.json()
    
    target_user = await db.users.find_one({"user_id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {"updatedAt": now_utc()}
    
    # Determine what can be updated based on role
    if user.get("role") == "super_admin":
        # Super admin can update anything
        if "name" in body:
            update_data["name"] = body["name"]
        if "role" in body:
            update_data["role"] = body["role"]
        if "isActive" in body:
            update_data["isActive"] = body["isActive"]
        if "companyId" in body:
            update_data["companyId"] = body["companyId"]
    elif user.get("role") == "company_admin":
        # Company admin can update users in their company
        if target_user.get("companyId") != user.get("companyId"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if "name" in body:
            update_data["name"] = body["name"]
        if "isActive" in body:
            update_data["isActive"] = body["isActive"]
        # Company admin can promote to editor or demote, but not create other admins
        if "role" in body:
            if body["role"] in ["editor"]:
                update_data["role"] = body["role"]
    else:
        # Regular users can only update themselves
        if target_user["user_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if "name" in body:
            update_data["name"] = body["name"]
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    updated = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "passwordHash": 0}
    )
    
    return updated


@router.delete("/{user_id}")
async def delete_user(user_id: str, request: Request, user: Dict = Depends(require_company_admin)):
    """
    Deactivate user:
    - Super Admin: Can deactivate any user
    - Company Admin: Can deactivate users in their company
    """
    target_user = await db.users.find_one({"user_id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if user.get("role") == "company_admin":
        if target_user.get("companyId") != user.get("companyId"):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Cannot delete yourself
    if target_user["user_id"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    # Soft delete (deactivate)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"isActive": False, "updatedAt": now_utc()}}
    )
    
    # Delete all sessions for this user
    await db.user_sessions.delete_many({"user_id": user_id})
    
    return {"message": "User deactivated successfully"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(user_id: str, request: Request, user: Dict = Depends(require_company_admin)):
    """
    Reset user password (Admin only):
    Sets a new password for the user
    """
    body = await request.json()
    new_password = body.get("newPassword", "")
    
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    target_user = await db.users.find_one({"user_id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if user.get("role") == "company_admin":
        if target_user.get("companyId") != user.get("companyId"):
            raise HTTPException(status_code=403, detail="Access denied")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "passwordHash": hash_password(new_password),
            "updatedAt": now_utc()
        }}
    )
    
    return {"message": "Password reset successfully"}
