"""Minimal Render bootstrap application.

This app intentionally exposes no SCORMIFY data or business routes. Its only
purpose is to create the hosting service safely so its outbound IP ranges can
be allowlisted in MongoDB Atlas before the full API is deployed.
"""

from fastapi import FastAPI


app = FastAPI(
    title="SCORMIFY Bootstrap",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "scormify-bootstrap",
        "databaseRequired": False,
    }
