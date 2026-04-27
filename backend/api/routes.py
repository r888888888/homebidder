import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db
from agent.orchestrator import run_agent
from api.rate_limit import check_and_record_rate_limit
from api.sanitize import sanitize_buyer_context
from api.auth import current_optional_user
from db.models import User

router = APIRouter()


class AnalyzeRequest(BaseModel):
    address: str = Field(max_length=200)
    buyer_context: str = Field(default="", max_length=500)
    force_refresh: bool = False

    @field_validator("address", "buyer_context", mode="before")
    @classmethod
    def _sanitize_text_fields(cls, v: object) -> object:
        if isinstance(v, str):
            return sanitize_buyer_context(v)
        return v


@router.post("/analyze")
async def analyze_listing(
    req: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_and_record_rate_limit),
    user: User | None = Depends(current_optional_user),
):
    """
    Stream an agent analysis for the given property address.
    Returns Server-Sent Events (text/event-stream).
    """
    user_id = user.id if user is not None else None

    async def event_stream():
        async for chunk in run_agent(req.address, req.buyer_context, db=db, force_refresh=req.force_refresh, user_id=user_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analyses")
async def list_analyses(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(current_optional_user),
):
    """List the last 20 analyses for the caller, newest first.

    Authenticated users see only their own analyses.
    Anonymous callers see only analyses with no owner (user_id IS NULL).
    """
    from db.models import Listing, Analysis
    from sqlalchemy import null

    stmt = select(Analysis, Listing.address_matched).join(Listing)
    if user is not None:
        stmt = stmt.where(Analysis.user_id == user.id)
    else:
        stmt = stmt.where(Analysis.user_id == null())
    stmt = stmt.order_by(Analysis.created_at.desc()).limit(20)

    rows = await db.execute(stmt)
    result = []
    for analysis, address in rows:
        result.append({
            "id": analysis.id,
            "address": address,
            "created_at": analysis.created_at.isoformat(),
            "offer_recommended": analysis.offer_recommended,
            "risk_level": analysis.risk_level,
            "investment_rating": analysis.investment_rating,
        })
    return result


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: int, db: AsyncSession = Depends(get_db)):
    """Get a full analysis record with comps."""
    from db.models import Analysis
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Analysis)
        .options(selectinload(Analysis.comps), selectinload(Analysis.listing))
        .where(Analysis.id == analysis_id)
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "id": analysis.id,
        "address": analysis.listing.address_matched,
        "created_at": analysis.created_at.isoformat(),
        "offer_low": analysis.offer_low,
        "offer_recommended": analysis.offer_recommended,
        "offer_high": analysis.offer_high,
        "risk_level": analysis.risk_level,
        "investment_rating": analysis.investment_rating,
        "rationale": analysis.rationale,
        "property_data": json.loads(analysis.property_data_json) if analysis.property_data_json else None,
        "neighborhood_data": json.loads(analysis.neighborhood_data_json) if analysis.neighborhood_data_json else None,
        "offer_data": json.loads(analysis.offer_data_json) if analysis.offer_data_json else None,
        "risk_data": json.loads(analysis.risk_data_json) if analysis.risk_data_json else None,
        "investment_data": json.loads(analysis.investment_data_json) if analysis.investment_data_json else None,
        "renovation_data": json.loads(analysis.renovation_data_json) if analysis.renovation_data_json else None,
        "permits_data": json.loads(analysis.permits_data_json) if analysis.permits_data_json else None,
        "crime_data": json.loads(analysis.crime_data_json) if analysis.crime_data_json else None,
        "comps": [
            {
                "address": c.address,
                "unit": c.unit,
                "city": c.city,
                "state": c.state,
                "zip_code": c.zip_code,
                "sold_price": c.sold_price,
                "list_price": c.list_price,
                "sold_date": c.sold_date,
                "bedrooms": c.bedrooms,
                "bathrooms": c.bathrooms,
                "sqft": c.sqft,
                "lot_size": c.lot_size,
                "price_per_sqft": c.price_per_sqft,
                "distance_miles": c.distance_miles,
                "pct_over_asking": c.pct_over_asking,
                "url": c.url,
                "source": c.source,
            }
            for c in analysis.comps
        ],
    }


@router.delete("/analyses/{analysis_id}", status_code=204)
async def delete_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(current_optional_user),
):
    """Delete a saved analysis record.

    Authenticated users can only delete analyses they own.
    Anonymous callers can only delete analyses with no owner (user_id IS NULL).
    """
    from db.models import Analysis

    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Ownership check
    if user is not None:
        if analysis.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this analysis")
    else:
        if analysis.user_id is not None:
            raise HTTPException(status_code=403, detail="Not authorized to delete this analysis")

    await db.delete(analysis)
    await db.commit()


class RenovationToggleUpdate(BaseModel):
    disabled_indices: list[int]


@router.patch("/analyses/{analysis_id}/renovation-toggles")
async def patch_renovation_toggles(
    analysis_id: int,
    body: RenovationToggleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(current_optional_user),
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
):
    """Persist which renovation line-item indices the user has toggled off."""
    from db.models import Analysis

    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Ownership check
    if user is not None:
        if analysis.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        # Anonymous: require matching session_id
        if analysis.user_id is not None or analysis.session_id != x_session_id:
            raise HTTPException(status_code=403, detail="Not authorized")

    if not analysis.renovation_data_json:
        raise HTTPException(status_code=404, detail="Analysis has no renovation data")

    data = json.loads(analysis.renovation_data_json)
    data["disabled_indices"] = body.disabled_indices
    analysis.renovation_data_json = json.dumps(data)
    await db.commit()

    return {"disabled_indices": body.disabled_indices}


@router.get("/health")
async def health():
    return {"status": "ok"}
