"""Sentiment analyzer for debate turns using Claude API."""

import asyncio
import json
import logging
import random

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

SENTIMENT_SYSTEM_PROMPT = """You are a debate analysis expert. Analyze the sentiment and tone of debate turns on two axes:

1. **Aggression** (0.0-1.0):
   - 0.0 = cooperative, conciliatory, collaborative tone
   - 0.5 = neutral, balanced tone
   - 1.0 = aggressive, confrontational, attacking tone

2. **Confidence** (0.0-1.0):
   - 0.0 = defensive, uncertain, hedging language
   - 0.5 = moderate confidence
   - 1.0 = highly confident, assertive, declarative

Respond ONLY with valid JSON matching this exact format (no markdown, no extra text):
{
  "analyses": [
    {"turn_number": 1, "aggression": 0.7, "confidence": 0.8},
    {"turn_number": 2, "aggression": 0.5, "confidence": 0.9}
  ]
}"""


async def analyze_debate_sentiment(turns_with_side: list[tuple]) -> list[dict]:
    """
    Analyze sentiment for all debate turns using Claude API.

    Args:
        turns_with_side: List of (Turn, side) tuples from the debate

    Returns:
        List of dicts with format:
        [
          {"turn_number": 1, "side": "pro", "aggression": 0.7, "confidence": 0.8, "token_count": 150},
          ...
        ]
    """
    if not turns_with_side:
        return []

    # Build prompt with all turns
    turns_text = []
    for turn, side in turns_with_side:
        turns_text.append(
            f"Turn {turn.turn_number} ({side}):\n"
            f"Claim: {turn.claim}\n"
            f"Argument: {turn.argument}\n"
        )

    user_message = (
        "Analyze the sentiment of these debate turns:\n\n"
        + "\n---\n".join(turns_text)
        + "\n\nProvide aggression and confidence scores for each turn."
    )

    try:
        # Call Claude API with retry
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await _call_with_retry(
            client,
            model=settings.claude_model,
            max_tokens=2000,
            system=SENTIMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()

        # Parse response
        result = _parse_sentiment_response(raw_text)

        # Merge with turn metadata
        sentiment_data = []
        for turn, side in turns_with_side:
            # Find matching analysis
            analysis = next(
                (a for a in result["analyses"] if a["turn_number"] == turn.turn_number),
                None,
            )

            sentiment_data.append({
                "turn_number": turn.turn_number,
                "side": side,
                "aggression": analysis["aggression"] if analysis else 0.5,
                "confidence": analysis["confidence"] if analysis else 0.5,
                "token_count": turn.token_count or 0,
            })

        return sentiment_data

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
        # Fallback: return neutral scores
        return [
            {
                "turn_number": turn.turn_number,
                "side": side,
                "aggression": 0.5,
                "confidence": 0.5,
                "token_count": turn.token_count or 0,
            }
            for turn, side in turns_with_side
        ]


async def _call_with_retry(client: anthropic.AsyncAnthropic, max_retries: int = 4, **kwargs):
    """Call Anthropic API with exponential backoff + jitter."""
    retryable_codes = (429, 500, 502, 503, 529)
    for attempt in range(max_retries):
        try:
            return await client.messages.create(**kwargs)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            if attempt < max_retries - 1:
                base_wait = min(2 ** (attempt + 1), 30)
                jitter = random.uniform(0, base_wait * 0.5)
                wait = base_wait + jitter
                logger.warning(
                    f"API network error on {kwargs.get('model')}: {e}, "
                    f"retrying in {wait:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)
            else:
                raise
        except anthropic.APIStatusError as e:
            if e.status_code in retryable_codes and attempt < max_retries - 1:
                base_wait = min(2 ** (attempt + 1), 30)
                jitter = random.uniform(0, base_wait * 0.5)
                wait = base_wait + jitter
                logger.warning(
                    f"API {e.status_code} on {kwargs.get('model')}, "
                    f"retrying in {wait:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)
            else:
                raise


def _parse_sentiment_response(raw: str) -> dict:
    """Parse sentiment analysis JSON response."""
    # Strip markdown code blocks if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse sentiment response: {text[:200]}")
        return {"analyses": []}
