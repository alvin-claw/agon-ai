from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.agents.sentiment_analyzer import analyze_debate_sentiment
from app.database import get_db
from app.models.debate import Debate, DebateParticipant, Turn
from app.models.reaction import AnalysisResult
from app.schemas.turn import AnalysisResponse

router = APIRouter(prefix="/api/debates", tags=["analysis"])
limiter = Limiter(key_func=get_remote_address)


def classify_citation_url(url: str) -> str:
    """Classify citation URL by source type based on domain patterns."""
    url_lower = url.lower()

    # Academic sources
    academic_patterns = [
        "scholar.google", "arxiv", "doi.org", "ncbi", "pubmed", "jstor",
        "ssrn", "ieee", "springer", "nature.com", "science.org", "wiley",
        "researchgate", ".edu", "academic"
    ]
    if any(pattern in url_lower for pattern in academic_patterns):
        return "academic"

    # News sources
    news_patterns = [
        "reuters", "bbc", "cnn", "nytimes", "washingtonpost", "theguardian",
        "apnews", "bloomberg", "economist", "wsj"
    ]
    if any(pattern in url_lower for pattern in news_patterns):
        return "news"

    # Wiki sources
    if "wikipedia" in url_lower or "wikimedia" in url_lower:
        return "wiki"

    # Government sources
    gov_patterns = [
        ".gov", ".go.kr", "europa.eu", "un.org", "who.int", "oecd.org"
    ]
    if any(pattern in url_lower for pattern in gov_patterns):
        return "government"

    return "other"


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

    # Analyze sentiment using Claude API
    sentiment_data = await analyze_debate_sentiment(turns_with_side)

    # Calculate citation_stats: citations per side, unique sources, source types
    citation_stats: dict[str, dict] = defaultdict(
        lambda: {
            "total": 0,
            "unique_sources": set(),
            "source_types": {"academic": 0, "news": 0, "wiki": 0, "government": 0, "other": 0}
        }
    )

    for turn, side in turns_with_side:
        if turn.citations:
            citations_list = turn.citations if isinstance(turn.citations, list) else []
            citation_stats[side]["total"] += len(citations_list)
            for citation in citations_list:
                if isinstance(citation, dict) and "url" in citation:
                    url = citation["url"]
                    citation_stats[side]["unique_sources"].add(url)
                    source_type = classify_citation_url(url)
                    citation_stats[side]["source_types"][source_type] += 1

    # Convert sets to counts for JSON serialization
    citation_stats_json = {}
    for side_key in ("pro", "con"):
        stats = citation_stats[side_key]
        citation_stats_json[side_key] = {
            "total": stats["total"],
            "unique_sources": len(stats["unique_sources"]),
            "source_types": stats["source_types"],
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
