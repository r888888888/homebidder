"""Rate limiting for unauthenticated visitors."""

import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from db.models import RateLimitEntry

rate_limit_router = APIRouter()


def get_client_identifier(request: Request) -> str:
    """Return a hashed identifier for the requesting client.

    Prefers the Fly-Client-IP header (set by Fly.io) over X-Forwarded-For,
    then falls back to the direct connection address.
    """
    ip = (
        request.headers.get("Fly-Client-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


async def check_and_record_rate_limit(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency: enforce the per-IP daily analysis limit.

    Raises HTTP 429 if the caller has already reached the limit. Otherwise
    records a new entry so subsequent calls count it. The entry is committed
    before the route handler runs, claiming the slot atomically.
    """
    if not settings.rate_limit_enabled:
        return

    identifier = get_client_identifier(request)
    cutoff = datetime.utcnow() - timedelta(hours=24)

    count = await db.scalar(
        select(func.count()).where(
            RateLimitEntry.identifier == identifier,
            RateLimitEntry.created_at > cutoff,
        )
    )

    if count >= settings.rate_limit_analyses_per_day:
        raise HTTPException(
            status_code=429,
            detail="Daily analysis limit reached. Please try again tomorrow.",
            headers={"Retry-After": "86400"},
        )

    db.add(RateLimitEntry(identifier=identifier))
    await db.commit()


@rate_limit_router.get("/rate-limit/status")
async def rate_limit_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the caller's current usage against the daily analysis limit.

    Used by the frontend to display a remaining-analyses counter.
    """
    identifier = get_client_identifier(request)
    limit = settings.rate_limit_analyses_per_day
    cutoff = datetime.utcnow() - timedelta(hours=24)

    used = await db.scalar(
        select(func.count()).where(
            RateLimitEntry.identifier == identifier,
            RateLimitEntry.created_at > cutoff,
        )
    )

    # reset_at = when the oldest in-window entry falls out of the 24 h window
    oldest = await db.scalar(
        select(func.min(RateLimitEntry.created_at)).where(
            RateLimitEntry.identifier == identifier,
            RateLimitEntry.created_at > cutoff,
        )
    )
    reset_at = (oldest + timedelta(hours=24)).isoformat() if oldest else None

    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "reset_at": reset_at,
    }
