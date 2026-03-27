"""
Company management routes (Super Admin only)
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Optional, List, Dict, Any
import uuid
import re

from routes.deps import db, now_utc

router = APIRouter(prefix="/companies", tags=["Companies"])

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text

# Import auth helpers
from routes.auth import require_super_admin, require_auth


@router.get("")
async def list_companies(request: Request, user: Dict = Depends(require_super_admin)):
    """List all companies (Super Admin only)"""
    companies = await db.companies.find({}, {"_id": 0}).to_list(1000)
    
    if companies:
        company_ids = [c['id'] for c in companies]
        user_counts = await db.users.aggregate([
            {'$match': {'companyId': {'$in': company_ids}}},
            {'$group': {'_id': '$companyId', 'count': {'$sum': 1}}}
        ]).to_list(1000)
        user_map = {item['_id']: item['count'] for item in user_counts}
        
        project_counts = await db.projects.aggregate([
            {'$match': {'companyId': {'$in': company_ids}}},
            {'$group': {'_id': '$companyId', 'count': {'$sum': 1}}}
        ]).to_list(1000)
        project_map = {item['_id']: item['count'] for item in project_counts}
        
        for company in companies:
            company["userCount"] = user_map.get(company["id"], 0)
            company["projectCount"] = project_map.get(company["id"], 0)
    
    return companies


@router.post("")
async def create_company(request: Request, user: Dict = Depends(require_super_admin)):
    """Create a new company (Super Admin only)"""
    body = await request.json()
    
    name = body.get("name", "").strip()
    slug = body.get("slug", "").strip() or slugify(name)
    
    if not name:
        raise HTTPException(status_code=400, detail="Company name is required")
    
    # Check if slug is unique
    existing = await db.companies.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=400, detail="Company with this slug already exists")
    
    company = {
        "id": f"company_{uuid.uuid4().hex[:12]}",
        "name": name,
        "slug": slug,
        "logo": body.get("logo"),
        "permissions": body.get("permissions", {
            "agentAccess": False,
            "heygen": False,
            "elevenlabs": False
        }),
        "maxUsers": body.get("maxUsers", 10),
        "maxProjects": body.get("maxProjects", 100),
        "isActive": True,
        "createdAt": now_utc(),
        "updatedAt": now_utc()
    }
    
    await db.companies.insert_one(company)
    company.pop("_id", None)
    
    return company


@router.get("/{company_id}")
async def get_company(company_id: str, request: Request, user: Dict = Depends(require_auth)):
    """Get company details"""
    # Super admin can view any company, others can only view their own
    if user.get("role") != "super_admin" and user.get("companyId") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Add stats
    company["userCount"] = await db.users.count_documents({"companyId": company_id})
    company["projectCount"] = await db.projects.count_documents({"companyId": company_id})
    
    return company


@router.put("/{company_id}")
async def update_company(company_id: str, request: Request, user: Dict = Depends(require_super_admin)):
    """Update company (Super Admin only)"""
    body = await request.json()
    
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = {"updatedAt": now_utc()}
    
    if "name" in body and body["name"]:
        update_data["name"] = body["name"].strip()
    if "logo" in body:
        update_data["logo"] = body["logo"]
    if "permissions" in body:
        update_data["permissions"] = body["permissions"]
    if "maxUsers" in body:
        update_data["maxUsers"] = body["maxUsers"]
    if "maxProjects" in body:
        update_data["maxProjects"] = body["maxProjects"]
    if "isActive" in body:
        update_data["isActive"] = body["isActive"]
    
    await db.companies.update_one(
        {"id": company_id},
        {"$set": update_data}
    )
    
    updated = await db.companies.find_one({"id": company_id}, {"_id": 0})
    return updated


@router.delete("/{company_id}")
async def delete_company(company_id: str, request: Request, user: Dict = Depends(require_super_admin)):
    """Delete company (Super Admin only) - Also deactivates all users"""
    company = await db.companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Deactivate all users in this company
    await db.users.update_many(
        {"companyId": company_id},
        {"$set": {"isActive": False, "updatedAt": now_utc()}}
    )
    
    # Soft delete company (mark as inactive)
    await db.companies.update_one(
        {"id": company_id},
        {"$set": {"isActive": False, "updatedAt": now_utc()}}
    )
    
    return {"message": "Company deactivated successfully"}
