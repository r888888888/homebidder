from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from agent.orchestrator import run_agent

router = APIRouter()


class AnalyzeRequest(BaseModel):
    address: str
    buyer_context: str = ""


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
        async for chunk in run_agent(req.address, req.buyer_context):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
