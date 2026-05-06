"""API routes for the Buying Plan (secretary-problem optimal stopping)."""

from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from buying_plan.logic import derive_plan, plan_status
from db import get_db
from db.models import BuyingPlan, SeenProperty, User

buying_plan_router = APIRouter()


def _require_investor_plus(user: User) -> None:
    """Raise 403 if the user is not on the Investor or Agent tier."""
    if user.is_superuser:
        return
    if user.subscription_tier in ("investor", "agent"):
        return
    raise HTTPException(status_code=403, detail="Buying Plan requires Investor or Agent plan")


class PatchPlanRequest(BaseModel):
    is_paused: bool


class CreatePlanRequest(BaseModel):
    buy_by_date: str  # ISO date string: YYYY-MM-DD
    viewings_per_week: float

    @field_validator("buy_by_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("buy_by_date must be a valid ISO date (YYYY-MM-DD)")
        return v

    @field_validator("viewings_per_week")
    @classmethod
    def validate_viewings(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("viewings_per_week must be greater than 0")
        return v


def _plan_to_dict(plan: BuyingPlan) -> dict:
    return {
        "id": plan.id,
        "buy_by_date": plan.buy_by_date,
        "viewings_per_week": plan.viewings_per_week,
        "total_n": plan.total_n,
        "explore_threshold": plan.explore_threshold,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "is_paused": bool(plan.is_paused),
    }


def _seen_to_dict(sp: SeenProperty) -> dict:
    return {
        "id": sp.id,
        "analysis_id": sp.analysis_id,
        "address_snapshot": sp.address_snapshot,
        "quality": sp.quality,
        "location": sp.location,
        "composite_score": sp.composite_score,
        "seen_at": sp.seen_at.isoformat() if sp.seen_at else None,
        "notes": sp.notes,
    }


async def _get_plan_status(plan: BuyingPlan, db: AsyncSession) -> tuple[dict, list[dict]]:
    """Fetch seen properties for the plan owner and compute status."""
    result = await db.execute(
        select(SeenProperty)
        .where(SeenProperty.user_id == plan.user_id)
        .order_by(SeenProperty.seen_at.asc())
    )
    seen_rows = result.scalars().all()
    seen_dicts = [_seen_to_dict(sp) for sp in seen_rows]

    status = plan_status(
        explore_threshold=plan.explore_threshold,
        seen_properties=[{"composite_score": sp.composite_score} for sp in seen_rows],
    )
    status["explore_threshold"] = plan.explore_threshold
    return status, seen_dicts


@buying_plan_router.post("/buying-plan", status_code=201)
async def create_plan(
    body: CreatePlanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Create or replace the user's buying plan. Requires Investor+ tier."""
    _require_investor_plus(user)

    today = date.today()
    derived = derive_plan(date.fromisoformat(body.buy_by_date), body.viewings_per_week, today=today)

    # Delete any existing plan for this user (upsert via delete + insert).
    await db.execute(delete(BuyingPlan).where(BuyingPlan.user_id == user.id))

    plan = BuyingPlan(
        user_id=user.id,
        buy_by_date=body.buy_by_date,
        viewings_per_week=body.viewings_per_week,
        total_n=derived["total_n"],
        explore_threshold=derived["explore_threshold"],
        created_at=datetime.utcnow(),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    status, seen_dicts = await _get_plan_status(plan, db)
    return {"plan": _plan_to_dict(plan), "status": status, "seen_properties": seen_dicts}


@buying_plan_router.get("/buying-plan")
async def get_plan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Return the authenticated user's current buying plan and status."""
    result = await db.execute(select(BuyingPlan).where(BuyingPlan.user_id == user.id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="No buying plan found")

    status, seen_dicts = await _get_plan_status(plan, db)
    return {"plan": _plan_to_dict(plan), "status": status, "seen_properties": seen_dicts}


@buying_plan_router.patch("/buying-plan")
async def patch_plan(
    body: PatchPlanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Pause or resume the authenticated user's buying plan."""
    result = await db.execute(select(BuyingPlan).where(BuyingPlan.user_id == user.id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="No buying plan found")

    plan.is_paused = body.is_paused
    await db.commit()
    await db.refresh(plan)

    status, seen_dicts = await _get_plan_status(plan, db)
    return {"plan": _plan_to_dict(plan), "status": status, "seen_properties": seen_dicts}


@buying_plan_router.delete("/buying-plan")
async def delete_plan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Delete the authenticated user's buying plan."""
    result = await db.execute(select(BuyingPlan).where(BuyingPlan.user_id == user.id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="No buying plan found")
    await db.delete(plan)
    await db.commit()
    return {}
