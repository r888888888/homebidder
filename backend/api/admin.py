"""Superuser-protected admin portal endpoints."""
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db import get_db
from db.models import User, Analysis, Listing
from api.auth import current_active_user

admin_router = APIRouter(prefix="/admin", tags=["admin"])

_PAGE_SIZE_DEFAULT = 25
_PAGE_SIZE_MAX = 100


async def _require_superuser(user: User = Depends(current_active_user)) -> User:
    """Raise 403 if the authenticated user is not a superuser."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required.",
        )
    return user


def _paginate(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size else 0,
    }


@admin_router.get("/users", dependencies=[Depends(_require_superuser)])
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


@admin_router.get("/analyses", dependencies=[Depends(_require_superuser)])
async def admin_list_analyses(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
):
    """List all analyses with the associated listing address, newest first, paginated."""
    total = (await db.execute(select(func.count()).select_from(Analysis))).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        select(Analysis, Listing.address_matched, User.email)
        .join(Listing)
        .outerjoin(User, Analysis.user_id == User.id)
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
            "user_email": user_email,
            "offer_low": analysis.offer_low,
            "offer_high": analysis.offer_high,
            "offer_recommended": analysis.offer_recommended,
            "risk_level": analysis.risk_level,
            "investment_rating": analysis.investment_rating,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
        for analysis, address, user_email in rows
    ]
    return _paginate(items, total, page, page_size)
