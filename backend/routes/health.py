"""Health checks for the Scormify app.

Two endpoints:
  - GET /api/health           -> public, ultra-light (no DB, no external calls).
                                 Intended for K8s `readinessProbe`/`livenessProbe`.
  - GET /api/admin/integrations-health  -> super_admin only. Pings every
                                           third-party integration and returns
                                           status + latency for each.

The integration-health endpoint caches results for 60 seconds so the admin
panel can refresh without hammering the APIs (and Leonardo's paid credits).
"""
import os
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from routes.deps import db, ELEVENLABS_API_KEY
from routes.auth import require_auth, has_role

logger = logging.getLogger("server")

router = APIRouter(tags=["Health"])


# ---------------------------------------------------------------------------
# Public readiness/liveness
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    """Ultra-light health check. Used by Kubernetes readiness/liveness probes.

    Does NOT touch MongoDB or any external service — returns immediately so
    probes can tell `pod started` from `pod crashed` even during cold-start
    warmup (MongoDB Atlas handshake, background migrations, etc).
    """
    return {"status": "ok", "service": "scormify-api"}


# ---------------------------------------------------------------------------
# Integration-health (super_admin only, cached)
# ---------------------------------------------------------------------------

_CACHE: dict[str, Any] = {"at": 0.0, "data": None}
_CACHE_TTL = 60.0  # seconds


async def _check_mongodb() -> dict:
    t0 = time.monotonic()
    try:
        # `ping` is the cheapest admin command
        await asyncio.wait_for(db.command("ping"), timeout=5.0)
        return {"status": "ok", "latencyMs": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_openai() -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return {
            "status": "not_configured",
            "provider": "OpenAI",
            "error": "OPENAI_API_KEY not set",
        }
    t0 = time.monotonic()
    try:
        # Official OpenAI endpoint: validates server-side Bearer authentication
        # without generating content or consuming model tokens.
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        latency = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            return {
                "status": "ok",
                "latencyMs": latency,
                "provider": "OpenAI",
                "model": os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o"),
            }
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_leonardo() -> dict:
    key = os.environ.get("LEONARDO_API_KEY", "").strip()
    if not key:
        return {"status": "not_configured", "error": "LEONARDO_API_KEY not set"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://cloud.leonardo.ai/api/rest/v1/me",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
        latency = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            # Surface subscription tokens so admin sees credit remaining
            body = resp.json().get("user_details", [{}])[0]
            return {
                "status": "ok",
                "latencyMs": latency,
                "balance": {
                    "apiPaidTokens": body.get("apiPaidTokens"),
                    "apiSubscriptionTokens": body.get("apiSubscriptionTokens"),
                    "subscriptionTokens": body.get("subscriptionTokens"),
                    "apiConcurrencySlots": body.get("apiConcurrencySlots"),
                },
            }
        if resp.status_code == 401 or "authorization" in resp.text.lower():
            return {
                "status": "error",
                "error": "Chave invalida ou expirada. Verifique em cloud.leonardo.ai.",
                "latencyMs": latency,
            }
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_heygen() -> dict:
    from routes.deps import HEYGEN_API_KEY as key
    if not key:
        return {"status": "not_configured", "error": "HEYGEN_API_KEY not set"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # HeyGen v2: /v2/voices is cheap and proves auth works
            resp = await client.get(
                "https://api.heygen.com/v2/voices",
                headers={"X-Api-Key": key},
            )
        latency = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            body = resp.json()
            voices = body.get("data", {}).get("voices", [])
            # Also fetch remaining credits
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    q = await client.get(
                        "https://api.heygen.com/v1/user/remaining_quota",
                        headers={"X-Api-Key": key},
                    )
                    if q.status_code == 200:
                        qdata = q.json().get("data", {})
                        return {
                            "status": "ok",
                            "latencyMs": latency,
                            "balance": {
                                "remainingQuota": qdata.get("remaining_quota"),
                                "voicesAvailable": len(voices),
                            },
                        }
            except Exception:
                pass
            return {"status": "ok", "latencyMs": latency, "balance": {"voicesAvailable": len(voices)}}
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_elevenlabs() -> dict:
    # Use the same normalized value as narration/TTS. This removes accidental
    # wrapper quotes and whitespace commonly pasted into Render secrets.
    key = ELEVENLABS_API_KEY
    if not key:
        return {"status": "not_configured", "error": "ELEVENLABS_API_KEY not set"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # ElevenLabs: /v1/user returns subscription info + character quota
            resp = await client.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": key},
            )
        latency = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            body = resp.json()
            sub = body.get("subscription", {})
            return {
                "status": "ok",
                "latencyMs": latency,
                "balance": {
                    "charactersUsed": sub.get("character_count"),
                    "characterLimit": sub.get("character_limit"),
                    "tier": sub.get("tier"),
                },
            }
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_resend() -> dict:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        return {"status": "not_configured", "error": "RESEND_API_KEY not set"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Resend: /emails POST without body returns 422 (validation error)
            # if key is valid, or 401 if invalid. This works even for
            # "restricted" keys that only have send-email permission.
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={},  # empty body → 422 validation error when key is OK
            )
        latency = int((time.monotonic() - t0) * 1000)
        # 422 (Unprocessable Entity) = chave valida, so faltou o body
        # 400 (Bad Request)           = idem para algumas respostas do Resend
        # 401                          = chave invalida
        if resp.status_code in (400, 422):
            return {"status": "ok", "latencyMs": latency}
        if resp.status_code == 200:
            return {"status": "ok", "latencyMs": latency}
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_convertapi() -> dict:
    key = os.environ.get("CONVERTAPI_SECRET", "").strip()
    if not key:
        return {"status": "not_configured", "error": "CONVERTAPI_SECRET not set"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # ConvertAPI: /user returns remaining seconds
            resp = await client.get(f"https://v2.convertapi.com/user?Secret={key}")
        latency = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            body = resp.json()
            return {
                "status": "ok",
                "latencyMs": latency,
                "balance": {
                    "secondsLeft": body.get("SecondsLeft"),
                },
            }
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_krea() -> dict:
    """Validate Krea AI credentials. Uses GET /jobs/<dummy-id>:
    - 404 "Job not found or unauthorized" => auth OK, key valid
    - 500 "Internal Error" => invalid key format
    - 401/403 => invalid key
    """
    key = os.environ.get("KREA_API_KEY", "").strip()
    if not key:
        return {"status": "not_configured", "error": "KREA_API_KEY not set"}
    if ":" not in key:
        return {"status": "error", "error": "KREA_API_KEY must be 'api_id:api_secret' format"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.krea.ai/jobs/scormify-health-check-ping",
                headers={"Authorization": f"Bearer {key}"},
            )
        latency = int((time.monotonic() - t0) * 1000)
        # 404 with "Job not found" is the happy path — auth succeeded
        if resp.status_code == 404 and "not found" in resp.text.lower():
            # Try to count curated models from our service catalog
            try:
                from services import krea_ai
                models_count = len(krea_ai.KREA_IMAGE_MODELS)
            except Exception:
                models_count = None
            return {
                "status": "ok",
                "latencyMs": latency,
                "balance": {"modelsAvailable": models_count} if models_count else None,
            }
        if resp.status_code in (401, 403):
            return {
                "status": "error",
                "error": "Chave Krea invalida ou expirada. Verifique em krea.ai/api.",
                "latencyMs": latency,
            }
        if resp.status_code == 500:
            return {
                "status": "error",
                "error": "Formato da chave invalido (esperado 'api_id:api_secret').",
                "latencyMs": latency,
            }
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def _check_kling() -> dict:
    """Validate the current single-key Kling API 2.0 authentication."""
    from services import kling_ai

    key = kling_ai.api_key()
    if not key:
        return {"status": "not_configured", "error": "KLING_API_KEY not set"}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                f"{kling_ai.base_url().rstrip('/')}/tasks",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                params={"task_ids": "scormify-health-check"},
            )
        latency = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            return {
                "status": "ok",
                "latencyMs": latency,
                "balance": {"model": "kling-3.0", "maxDurationSeconds": 15},
            }
        if resp.status_code in (401, 403):
            return {
                "status": "error",
                "error": "Chave Kling invalida ou expirada. Gere outra chave no console Kling AI.",
                "latencyMs": latency,
            }
        return {
            "status": "error",
            "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            "latencyMs": latency,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


@router.get("/admin/integrations-health")
async def integrations_health(
    _t: Optional[str] = None,
    user: dict = Depends(require_auth),
):
    """Return the health status of every third-party integration used by Scormify.

    Super-admin only. Cached for 60s to avoid paying for unnecessary API calls
    (Leonardo, HeyGen etc. don't charge for `/me` or quota endpoints, but the
    cache still matters for latency on dashboard refresh).
    """
    if not has_role(user, "super_admin"):
        raise HTTPException(status_code=403, detail="Super admin only")

    now = time.monotonic()
    if not _t and _CACHE["data"] and (now - _CACHE["at"]) < _CACHE_TTL:
        cached = dict(_CACHE["data"])
        cached["cached"] = True
        cached["cacheAgeSeconds"] = int(now - _CACHE["at"])
        return cached

    # Run all checks in parallel
    results = await asyncio.gather(
        _check_mongodb(),
        _check_openai(),
        _check_leonardo(),
        _check_heygen(),
        _check_elevenlabs(),
        _check_resend(),
        _check_convertapi(),
        _check_krea(),
        _check_kling(),
        return_exceptions=True,
    )

    def _norm(r):
        if isinstance(r, Exception):
            return {"status": "error", "error": str(r)[:200]}
        return r

    payload = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "integrations": {
            "mongodb": _norm(results[0]),
            "openai": _norm(results[1]),
            "leonardo": _norm(results[2]),
            "heygen": _norm(results[3]),
            "elevenlabs": _norm(results[4]),
            "resend": _norm(results[5]),
            "convertapi": _norm(results[6]),
            "krea": _norm(results[7]),
            "kling": _norm(results[8]),
        },
        "cached": False,
    }

    # Overall status: ok if all non-configured or ok; degraded if any error
    statuses = [v["status"] for v in payload["integrations"].values()]
    if any(s == "error" for s in statuses):
        payload["overall"] = "degraded"
    elif all(s in ("ok", "not_configured") for s in statuses):
        payload["overall"] = "ok"
    else:
        payload["overall"] = "unknown"

    _CACHE["data"] = payload
    _CACHE["at"] = now
    return payload
