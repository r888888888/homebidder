"""API routes for marking properties as seen (binary bidding-intent rating)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from buying_plan.logic import (
    BIDDING_INTENT_VALUES,
    LOCATION_SCALE,
    QUALITY_SCALE,
    composite_score_from_intent,
)
from db import get_db
from db.models import Analysis, SeenProperty, User

seen_property_router = APIRouter()


class MarkSeenRequest(BaseModel):
    analysis_id: int
    bidding_intent: str
    # quality and location accept legacy clients but are no longer surfaced in
    # the new UI. Default "neutral" keeps the legacy NOT NULL columns satisfied
    # without a destructive schema migration.
    quality: str = "neutral"
    location: str = "neutral"
    notes: str | None = None

    @field_validator("bidding_intent")
    @classmethod
    def validate_bidding_intent(cls, v: str) -> str:
        if v not in BIDDING_INTENT_VALUES:
            raise ValueError(
                f"bidding_intent must be one of {sorted(BIDDING_INTENT_VALUES)}"
            )
        return v

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        if v not in QUALITY_SCALE:
            raise ValueError(f"quality must be one of {list(QUALITY_SCALE)}")
        return v

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        if v not in LOCATION_SCALE:
            raise ValueError(f"location must be one of {list(LOCATION_SCALE)}")
        return v


def _seen_property_to_dict(sp: SeenProperty) -> dict:
    return {
        "id": sp.id,
        "analysis_id": sp.analysis_id,
        "address_snapshot": sp.address_snapshot,
        "quality": sp.quality,
        "location": sp.location,
        "composite_score": sp.composite_score,
        "bidding_intent": sp.bidding_intent,
        "seen_at": sp.seen_at.isoformat() if sp.seen_at else None,
        "notes": sp.notes,
    }


@seen_property_router.post("/seen-properties", status_code=201)
async def mark_seen(
    body: MarkSeenRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Mark an analysis as physically seen, capturing the user's binary bidding intent."""
    result = await db.execute(select(Analysis).where(Analysis.id == body.analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    dup_result = await db.execute(
        select(SeenProperty).where(
            SeenProperty.user_id == user.id,
            SeenProperty.analysis_id == body.analysis_id,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="This analysis has already been marked as seen")

    from db.models import Listing
    listing_result = await db.execute(select(Listing).where(Listing.id == analysis.listing_id))
    listing = listing_result.scalar_one_or_none()
    address_snapshot = listing.address_input if listing else str(body.analysis_id)

    score = composite_score_from_intent(body.bidding_intent)
    sp = SeenProperty(
        user_id=user.id,
        analysis_id=body.analysis_id,
        address_snapshot=address_snapshot,
        quality=body.quality,
        location=body.location,
        composite_score=score,
        bidding_intent=body.bidding_intent,
        seen_at=datetime.utcnow(),
        notes=body.notes,
    )
    db.add(sp)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This analysis has already been marked as seen")
    await db.refresh(sp)

    return _seen_property_to_dict(sp)


@seen_property_router.get("/seen-properties")
async def list_seen(
    analysis_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """List all properties marked as seen by the authenticated user.

    Optionally filter by analysis_id to check if a specific analysis is already seen.
    """
    stmt = select(SeenProperty).where(SeenProperty.user_id == user.id)
    if analysis_id is not None:
        stmt = stmt.where(SeenProperty.analysis_id == analysis_id)
    stmt = stmt.order_by(SeenProperty.seen_at.desc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"seen_properties": [_seen_property_to_dict(sp) for sp in rows]}


@seen_property_router.delete("/seen-properties/{seen_id}")
async def unmark_seen(
    seen_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Remove a seen-property record."""
    result = await db.execute(select(SeenProperty).where(SeenProperty.id == seen_id))
    sp = result.scalar_one_or_none()
    if sp is None:
        raise HTTPException(status_code=404, detail="Seen property not found")
    if sp.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.delete(sp)
    await db.commit()
    return {}
