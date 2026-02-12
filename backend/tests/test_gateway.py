"""Tests for ClaudeDebateAgent gateway (JSON parsing and formatting)."""

import pytest
from unittest.mock import MagicMock

from app.agents.claude_agent import ClaudeDebateAgent
from app.models.agent import Agent
from app.models.debate import Turn


@pytest.fixture
def claude_agent(sample_agent) -> ClaudeDebateAgent:
    """Create a ClaudeDebateAgent instance for testing."""
    return ClaudeDebateAgent(agent=sample_agent, side="pro")


def test_parse_response_with_valid_json(claude_agent):
    """Test _parse_response with valid JSON."""
    raw_response = """{
  "stance": "pro",
  "claim": "AI regulation is necessary",
  "argument": "We need oversight for safety",
  "citations": [
    {
      "url": "https://example.com",
      "title": "AI Safety",
      "quote": "Regulation helps"
    }
  ],
  "rebuttal_target": null
}"""

    result = claude_agent._parse_response(raw_response)

    assert result["stance"] == "pro"
    assert result["claim"] == "AI regulation is necessary"
    assert result["argument"] == "We need oversight for safety"
    assert len(result["citations"]) == 1
    assert result["citations"][0]["url"] == "https://example.com"
    assert result["rebuttal_target"] is None


def test_parse_response_with_markdown_code_blocks(claude_agent):
    """Test _parse_response strips markdown code blocks."""
    raw_response = """```json
{
  "stance": "con",
  "claim": "AI regulation is premature",
  "argument": "Too early for regulation",
  "citations": [
    {
      "url": "https://example.com/innovation",
      "title": "Innovation",
      "quote": "Let technology develop"
    }
  ],
  "rebuttal_target": null
}
```"""

    result = claude_agent._parse_response(raw_response)

    assert result["stance"] == "con"
    assert result["claim"] == "AI regulation is premature"
    assert result["argument"] == "Too early for regulation"
    assert len(result["citations"]) == 1


def test_parse_response_with_trailing_commas(claude_agent):
    """Test _parse_response fixes trailing commas."""
    raw_response = """{
  "stance": "pro",
  "claim": "Test claim",
  "argument": "Test argument",
  "citations": [
    {
      "url": "https://example.com",
      "title": "Source",
      "quote": "Quote",
    },
  ],
  "rebuttal_target": null,
}"""

    result = claude_agent._parse_response(raw_response)

    # Should successfully parse despite trailing commas
    assert result["stance"] == "pro"
    assert result["claim"] == "Test claim"
    assert len(result["citations"]) == 1


def test_parse_response_with_invalid_text_returns_fallback(claude_agent):
    """Test _parse_response with completely invalid text returns fallback."""
    raw_response = "This is not JSON at all, just random text."

    result = claude_agent._parse_response(raw_response)

    # Should return fallback response
    assert result["stance"] == "pro"  # Uses agent's side
    assert "[Parse error" in result["claim"]
    assert "This is not JSON" in result["argument"]
    assert len(result["citations"]) == 1
    assert result["citations"][0]["url"] == "https://error.agonai.dev"


def test_parse_response_with_malformed_json_returns_fallback(claude_agent):
    """Test _parse_response with malformed JSON that can't be fixed."""
    raw_response = """{
  "stance": "pro"
  "claim": "Missing comma here"
  "argument": "Also broken"
}"""

    result = claude_agent._parse_response(raw_response)

    # Should return fallback response
    assert result["stance"] == "pro"
    assert "[Parse error" in result["claim"]
    assert "Missing comma" in result["argument"]


def test_count_tokens_returns_reasonable_values(claude_agent):
    """Test _count_tokens returns reasonable token counts."""
    # Short text
    short_text = "Hello world"
    short_count = claude_agent._count_tokens(short_text)
    assert 1 <= short_count <= 5

    # Medium text
    medium_text = " ".join(["word"] * 50)
    medium_count = claude_agent._count_tokens(medium_text)
    assert 40 <= medium_count <= 60

    # Long text
    long_text = " ".join(["word"] * 200)
    long_count = claude_agent._count_tokens(long_text)
    assert 180 <= long_count <= 220


def test_count_tokens_handles_exceptions(claude_agent):
    """Test _count_tokens fallback when tiktoken fails."""
    # Empty string should not raise
    result = claude_agent._count_tokens("")
    assert result >= 0


def test_format_previous_turns_with_mixed_sides(claude_agent, sample_agent_pro, sample_agent_con):
    """Test _format_previous_turns formats correctly with opponent and team markers."""
    turns = [
        Turn(
            turn_number=1,
            stance="pro",
            claim="First claim",
            argument="First argument",
            status="validated",
        ),
        Turn(
            turn_number=2,
            stance="con",
            claim="Second claim",
            argument="Second argument",
            status="validated",
        ),
        Turn(
            turn_number=3,
            stance="pro",
            claim="Third claim",
            argument="Third argument",
            status="validated",
        ),
    ]

    result = claude_agent._format_previous_turns(turns, "pro")

    # Check that YOUR_TEAM and OPPONENT_TURN markers are present
    assert "[YOUR_TEAM Turn 1]" in result
    assert "[OPPONENT_TURN Turn 2]" in result
    assert "[YOUR_TEAM Turn 3]" in result
    assert "First claim" in result
    assert "Second claim" in result
    assert "Third claim" in result
    assert "[/YOUR_TEAM]" in result
    assert "[/OPPONENT_TURN]" in result


def test_format_previous_turns_with_empty_list(claude_agent):
    """Test _format_previous_turns with no previous turns."""
    result = claude_agent._format_previous_turns([], "pro")

    assert result == ""


def test_format_previous_turns_with_modified_stance(claude_agent):
    """Test _format_previous_turns treats 'modified' stance as YOUR_TEAM."""
    turns = [
        Turn(
            turn_number=1,
            stance="modified",
            claim="Modified claim",
            argument="Modified argument",
            status="validated",
        ),
    ]

    result = claude_agent._format_previous_turns(turns, "pro")

    # Modified stance should be treated as YOUR_TEAM
    assert "[YOUR_TEAM Turn 1]" in result
    assert "Modified claim" in result


def test_parse_response_preserves_complex_citations(claude_agent):
    """Test _parse_response handles citations with special characters."""
    raw_response = """{
  "stance": "pro",
  "claim": "Test",
  "argument": "Test argument",
  "citations": [
    {
      "url": "https://example.com/path?query=value&other=123",
      "title": "Title with 'quotes' and \\"escapes\\"",
      "quote": "Quote with \\nnewlines\\nand special chars: $@#"
    }
  ],
  "rebuttal_target": null
}"""

    result = claude_agent._parse_response(raw_response)

    assert len(result["citations"]) == 1
    assert "query=value" in result["citations"][0]["url"]
    assert "quotes" in result["citations"][0]["title"]


def test_parse_response_with_json_language_marker(claude_agent):
    """Test _parse_response strips ```json specifically."""
    raw_response = """```json
{"stance": "pro", "claim": "Test", "argument": "Test", "citations": []}
```"""

    result = claude_agent._parse_response(raw_response)

    assert result["stance"] == "pro"
    assert result["claim"] == "Test"
