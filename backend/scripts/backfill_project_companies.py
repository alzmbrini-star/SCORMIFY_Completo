"""One-shot migration: backfill companyId/userId on projects that were
created before per-tenant filtering was enforced.

Resolution order for each project:
  1. If project already has companyId → skip.
  2. If project has agentSessionId → use session.companyId.
  3. If project has userId → use user.companyId.
  4. If project has createdByAgent=True and no session → skip (super_admin only).
  5. Otherwise (mostly old PPT/manual imports) → fall back to the default
     company id provided as DEFAULT_COMPANY_ID env var. If unset, leave
     NULL so the project stays visible only to super_admin.

Idempotent: re-runs safely because step 1 skips already-fixed docs.
"""
import os
import sys

from pymongo import MongoClient


def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    default_company_id = os.environ.get("DEFAULT_COMPANY_ID", "").strip() or None

    if not mongo_url or not db_name:
        print("ERROR: MONGO_URL / DB_NAME not set in env")
        sys.exit(1)

    client = MongoClient(mongo_url)
    db = client[db_name]

    # Pre-load users so we do N in-memory lookups instead of N queries
    users_by_id = {
        u["user_id"]: u
        for u in db.users.find({}, {"_id": 0, "user_id": 1, "companyId": 1})
        if u.get("user_id")
    }

    cursor = db.projects.find(
        {"companyId": {"$in": [None, ""]}},
        {"_id": 0, "id": 1, "agentSessionId": 1, "userId": 1, "createdByAgent": 1}
    )
    projects = list(cursor)
    print(f"Found {len(projects)} projects missing companyId")

    stats = {"via_session": 0, "via_user": 0, "via_default": 0, "skipped": 0}

    for p in projects:
        company_id = None
        user_id = p.get("userId")

        # 1. Try via agent_session
        session_id = p.get("agentSessionId")
        if session_id:
            session = db.agent_sessions.find_one(
                {"id": session_id},
                {"_id": 0, "companyId": 1, "userId": 1}
            )
            if session:
                company_id = session.get("companyId") or company_id
                user_id = user_id or session.get("userId")
                if company_id:
                    stats["via_session"] += 1

        # 2. Try via user
        if not company_id and user_id:
            u = users_by_id.get(user_id)
            if u and u.get("companyId"):
                company_id = u["companyId"]
                stats["via_user"] += 1

        # 3. Fallback to DEFAULT_COMPANY_ID
        if not company_id and default_company_id:
            company_id = default_company_id
            stats["via_default"] += 1

        if not company_id:
            stats["skipped"] += 1
            continue

        update = {"companyId": company_id}
        if user_id:
            update["userId"] = user_id
        db.projects.update_one({"id": p["id"]}, {"$set": update})

    print("Backfill complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
