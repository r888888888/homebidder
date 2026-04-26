"""Rate limiting for unauthenticated and authenticated visitors.

Anonymous users:   3 analyses per calendar month (IP-based, RateLimitEntry table)
Buyer tier:        5 analyses per calendar month (counted from analyses table)
Investor tier:    30 analyses per calendar month (counted from analyses table)
Agent tier:       100 analyses per calendar month (counted from analyses table)
Superusers:       unlimited
"""

import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from db.models import Analysis, RateLimitEntry, User
from api.auth import current_optional_user

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


def _month_start() -> datetime:
    now = datetime.utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _seconds_until_month_end() -> int:
    now = datetime.utcnow()
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((next_month - now).total_seconds()))


def _month_end_iso() -> str:
    now = datetime.utcnow()
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return next_month.isoformat()


async def _count_monthly_analyses(user_id: uuid.UUID, db: AsyncSession) -> int:
    """Count analyses run by this user in the current calendar month (UTC)."""
    count = await db.scalar(
        select(func.count()).where(
            Analysis.user_id == user_id,
            Analysis.created_at >= _month_start(),
        )
    )
    return count or 0


def _tier_limit(user: User) -> tuple[str, int]:
    """Return (effective_tier_label, monthly_limit) for an authenticated user."""
    if user.is_grandfathered or user.subscription_tier == "investor":
        return "investor", settings.rate_limit_investor_per_month
    if user.subscription_tier == "agent":
        return "agent", settings.rate_limit_agent_per_month
    return "buyer", settings.rate_limit_buyer_per_month


async def check_and_record_rate_limit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(current_optional_user),
) -> None:
    """FastAPI dependency: enforce the monthly analysis limit.

    - Superusers: unlimited.
    - Authenticated users: counted from the analyses table by calendar month,
      with limits determined by subscription_tier / is_grandfathered.
    - Anonymous users: counted from RateLimitEntry by calendar month.

    Raises HTTP 429 on limit breach. No insertion is performed for authenticated
    users — the analysis row itself is the source of truth.
    """
    if not settings.rate_limit_enabled:
        return

    if user is not None:
        # Superusers bypass rate limiting entirely.
        if user.is_superuser:
            return

        tier_label, limit = _tier_limit(user)
        used = await _count_monthly_analyses(user.id, db)

        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "MONTHLY_LIMIT_REACHED",
                    "tier": tier_label,
                    "limit": limit,
                    "used": used,
                    "upgrade_url": "/pricing",
                },
                headers={"Retry-After": str(_seconds_until_month_end())},
            )
        # No RateLimitEntry insertion for authenticated users.
        return

    # Anonymous path — IP-based, monthly window, RateLimitEntry table.
    identifier = get_client_identifier(request)
    limit = settings.rate_limit_anonymous_per_month

    count = await db.scalar(
        select(func.count()).where(
            RateLimitEntry.identifier == identifier,
            RateLimitEntry.created_at >= _month_start(),
        )
    )
    count = count or 0

    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "MONTHLY_LIMIT_REACHED",
                "tier": "anonymous",
                "limit": limit,
                "used": count,
                "upgrade_url": "/register",
            },
            headers={"Retry-After": str(_seconds_until_month_end())},
        )

    db.add(RateLimitEntry(identifier=identifier))
    await db.commit()


@rate_limit_router.get("/rate-limit/status")
async def rate_limit_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(current_optional_user),
):
    """Return the caller's current usage against their monthly analysis limit."""
    reset_at = _month_end_iso()

    if user is not None:
        tier_label, limit = _tier_limit(user)
        used = await _count_monthly_analyses(user.id, db)
        return {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "reset_at": reset_at,
            "tier": tier_label,
            "is_grandfathered": user.is_grandfathered,
            "window": "monthly",
        }

    # Anonymous
    identifier = get_client_identifier(request)
    limit = settings.rate_limit_anonymous_per_month
    used = await db.scalar(
        select(func.count()).where(
            RateLimitEntry.identifier == identifier,
            RateLimitEntry.created_at >= _month_start(),
        )
    ) or 0

    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "reset_at": reset_at,
        "tier": "anonymous",
        "window": "monthly",
        "upgrade_url": "/register",
    }
