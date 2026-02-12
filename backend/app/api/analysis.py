from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.debate import Debate, DebateParticipant, Turn
from app.models.reaction import AnalysisResult
from app.schemas.turn import AnalysisResponse

router = APIRouter(prefix="/api/debates", tags=["analysis"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{debate_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(
    debate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get existing analysis result for a debate."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.debate_id == debate_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.post("/{debate_id}/analysis/generate", status_code=200)
@limiter.limit("5/minute")
async def generate_analysis(
    request: Request,
    debate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate analysis for a debate (returns 202 Accepted)."""
    # Verify debate exists
    result = await db.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    # Get all validated turns with participant info
    result = await db.execute(
        select(Turn, DebateParticipant.side)
        .join(DebateParticipant, and_(
            Turn.agent_id == DebateParticipant.agent_id,
            Turn.debate_id == DebateParticipant.debate_id,
        ))
        .where(
            Turn.debate_id == debate_id,
            DebateParticipant.debate_id == debate_id,
            Turn.status == "validated",
        )
        .order_by(Turn.turn_number)
    )
    turns_with_side = result.all()

    # Calculate sentiment_data: array of turn metadata
    sentiment_data = []
    for turn, side in turns_with_side:
        sentiment_data.append({
            "side": side,
            "turn_number": turn.turn_number,
            "token_count": turn.token_count or 0,
            "stance": turn.stance,
        })

    # Calculate citation_stats: citations per side, unique sources
    citation_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "unique_sources": set()})

    for turn, side in turns_with_side:
        if turn.citations:
            citations_list = turn.citations if isinstance(turn.citations, list) else []
            citation_stats[side]["total"] += len(citations_list)
            for citation in citations_list:
                if isinstance(citation, dict) and "url" in citation:
                    citation_stats[side]["unique_sources"].add(citation["url"])

    # Convert sets to counts for JSON serialization
    citation_stats_json = {}
    for side_key in ("pro", "con"):
        stats = citation_stats[side_key]
        citation_stats_json[side_key] = {
            "total": stats["total"],
            "unique_sources": len(stats["unique_sources"]),
        }

    # Check if analysis already exists
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.debate_id == debate_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing analysis
        existing.sentiment_data = sentiment_data
        existing.citation_stats = citation_stats_json
        existing.updated_at = func.now()
    else:
        # Create new analysis
        analysis = AnalysisResult(
            debate_id=debate_id,
            sentiment_data=sentiment_data,
            citation_stats=citation_stats_json,
        )
        db.add(analysis)

    await db.commit()

    return {"status": "accepted", "message": "Analysis generation completed"}
