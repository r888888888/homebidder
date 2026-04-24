"""HTTP Basic Auth protected admin portal endpoints."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from db import get_db
from db.models import User, Analysis, Listing

admin_router = APIRouter(prefix="/admin", tags=["admin"])
_security = HTTPBasic()


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


@admin_router.get("/users", dependencies=[Depends(_require_admin)])
async def admin_list_users(db: AsyncSession = Depends(get_db)):
    """List all registered users (never exposes hashed_password)."""
    result = await db.execute(select(User).order_by(User.email))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "is_superuser": u.is_superuser,
        }
        for u in users
    ]


@admin_router.get("/analyses", dependencies=[Depends(_require_admin)])
async def admin_list_analyses(db: AsyncSession = Depends(get_db)):
    """List all analyses with the associated listing address, newest first."""
    stmt = (
        select(Analysis, Listing.address_matched)
        .join(Listing)
        .order_by(Analysis.created_at.desc())
    )
    rows = await db.execute(stmt)
    return [
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
