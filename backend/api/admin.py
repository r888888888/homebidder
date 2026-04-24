"""HTTP Basic Auth protected admin portal endpoints."""
import math
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from config import settings
from db import get_db
from db.models import User, Analysis, Listing

admin_router = APIRouter(prefix="/admin", tags=["admin"])
_security = HTTPBasic()

_PAGE_SIZE_DEFAULT = 25
_PAGE_SIZE_MAX = 100


async def _require_admin(credentials: HTTPBasicCredentials = Depends(_security)):
    admin_password = settings.admin_password
    if not admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin portal not configured. Set ADMIN_PASSWORD environment variable.",
        )
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )


def _paginate(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size else 0,
    }


@admin_router.get("/users", dependencies=[Depends(_require_admin)])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """List registered users with cursor pagination (never exposes hashed_password)."""
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(select(User).order_by(User.email).offset(offset).limit(page_size))
    ).scalars().all()

    items = [
        {
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "is_superuser": u.is_superuser,
        }
        for u in rows
    ]
    return _paginate(items, total, page, page_size)


@admin_router.get("/analyses", dependencies=[Depends(_require_admin)])
async def admin_list_analyses(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """List all analyses with the associated listing address, newest first, paginated."""
    total = (await db.execute(select(func.count()).select_from(Analysis))).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        select(Analysis, Listing.address_matched)
        .join(Listing)
        .order_by(Analysis.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = await db.execute(stmt)

    items = [
        {
            "id": analysis.id,
            "address": address,
            "user_id": str(analysis.user_id) if analysis.user_id else None,
            "offer_low": analysis.offer_low,
            "offer_high": analysis.offer_high,
            "offer_recommended": analysis.offer_recommended,
            "risk_level": analysis.risk_level,
            "investment_rating": analysis.investment_rating,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
        for analysis, address in rows
    ]
    return _paginate(items, total, page, page_size)
