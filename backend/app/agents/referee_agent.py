"""Referee agent for fact-checking debate turn citations."""

import logging

import anthropic
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CONTENT_MATCH_PROMPT = """You are a fact-checking assistant. Compare the following quote attributed to a source with the actual page content.

Claimed quote: "{quote}"

Actual page content (truncated):
{content}

Does the page content support or contain the claimed quote? Answer with a JSON object:
{{"match": true/false, "explanation": "brief reason"}}

Respond ONLY with the JSON object, no other text."""

LOGIC_CHECK_PROMPT = """You are a fact-checking assistant. Evaluate whether the following claim logically follows from the cited evidence.

Claim: "{claim}"

Citations and evidence:
{evidence}

Does the claim logically follow from the cited evidence? Answer with a JSON object:
{{"valid": true/false, "explanation": "brief reason"}}

Respond ONLY with the JSON object, no other text."""


class RefereeAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.http_client = httpx.AsyncClient(timeout=5.0, follow_redirects=True)

    async def verify_claim(self, claim: str, citations: list[dict]) -> dict:
        """Verify a claim against its citations.

        Returns dict with: verdict, citation_url, citation_accessible,
                          content_match, logic_valid, details
        """
        results = []
        all_accessible = True
        all_match = True
        evidence_texts = []

        for citation in citations:
            url = citation.get("url", "")
            quote = citation.get("quote", "")
            title = citation.get("title", "")

            # Step 1: Check if citation URL is accessible
            accessible = False
            page_content = ""
            try:
                resp = await self.http_client.get(url)
                accessible = resp.status_code == 200
                if accessible:
                    page_content = resp.text[:5000]
            except Exception as e:
                logger.warning(f"Failed to fetch citation URL {url}: {e}")
                accessible = False

            if not accessible:
                all_accessible = False
                results.append({
                    "url": url,
                    "title": title,
                    "accessible": False,
                    "content_match": None,
                    "explanation": "Source URL could not be accessed",
                })
                continue

            # Step 2: Check content match using Claude
            content_match = False
            match_explanation = ""
            if page_content and quote:
                try:
                    resp_msg = await self.client.messages.create(
                        model=settings.claude_model,
                        max_tokens=200,
                        messages=[{
                            "role": "user",
                            "content": CONTENT_MATCH_PROMPT.format(
                                quote=quote,
                                content=page_content[:3000],
                            ),
                        }],
                    )
                    import json
                    raw = resp_msg.content[0].text.strip()
                    parsed = json.loads(raw)
                    content_match = parsed.get("match", False)
                    match_explanation = parsed.get("explanation", "")
                except Exception as e:
                    logger.warning(f"Content match check failed for {url}: {e}")
                    content_match = False
                    match_explanation = "Analysis failed"

            if not content_match:
                all_match = False

            evidence_texts.append(f"[{title}] ({url}): {quote}")
            results.append({
                "url": url,
                "title": title,
                "accessible": True,
                "content_match": content_match,
                "explanation": match_explanation,
            })

        # Step 3: Check logical validity using Claude
        logic_valid = False
        logic_explanation = ""
        if evidence_texts:
            try:
                resp_msg = await self.client.messages.create(
                    model=settings.claude_model,
                    max_tokens=200,
                    messages=[{
                        "role": "user",
                        "content": LOGIC_CHECK_PROMPT.format(
                            claim=claim,
                            evidence="\n".join(evidence_texts),
                        ),
                    }],
                )
                import json
                raw = resp_msg.content[0].text.strip()
                parsed = json.loads(raw)
                logic_valid = parsed.get("valid", False)
                logic_explanation = parsed.get("explanation", "")
            except Exception as e:
                logger.warning(f"Logic check failed: {e}")
                logic_valid = False
                logic_explanation = "Analysis failed"

        # Step 4: Determine verdict
        if not all_accessible:
            verdict = "source_inaccessible"
        elif not all_match:
            verdict = "source_mismatch"
        elif all_accessible and all_match and logic_valid:
            verdict = "verified"
        else:
            verdict = "inconclusive"

        # Pick first citation URL for the summary field
        first_url = citations[0]["url"] if citations else None

        return {
            "verdict": verdict,
            "citation_url": first_url,
            "citation_accessible": all_accessible,
            "content_match": all_match,
            "logic_valid": logic_valid,
            "details": {
                "citation_results": results,
                "logic_explanation": logic_explanation,
            },
        }

    async def close(self):
        await self.http_client.aclose()
