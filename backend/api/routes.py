import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db
from agent.orchestrator import run_agent

router = APIRouter()


class AnalyzeRequest(BaseModel):
    address: str
    buyer_context: str = ""
    force_refresh: bool = False


@router.post("/analyze")
async def analyze_listing(
    req: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream an agent analysis for the given property address.
    Returns Server-Sent Events (text/event-stream).
    """

    async def event_stream():
        async for chunk in run_agent(req.address, req.buyer_context, db=db, force_refresh=req.force_refresh):
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
async def list_analyses(db: AsyncSession = Depends(get_db)):
    """List the last 20 analyses, newest first."""
    from db.models import Listing, Analysis
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Analysis, Listing.address_matched)
        .join(Listing)
        .order_by(Analysis.created_at.desc())
        .limit(20)
    )
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
        "comps": [
            {
                "address": c.address,
                "sold_price": c.sold_price,
                "sold_date": c.sold_date,
                "sqft": c.sqft,
                "price_per_sqft": c.price_per_sqft,
                "distance_miles": c.distance_miles,
                "pct_over_asking": c.pct_over_asking,
            }
            for c in analysis.comps
        ],
    }


@router.delete("/analyses/{analysis_id}", status_code=204)
async def delete_analysis(analysis_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a saved analysis record."""
    from db.models import Analysis

    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    await db.delete(analysis)
    await db.commit()


@router.get("/health")
async def health():
    return {"status": "ok"}
