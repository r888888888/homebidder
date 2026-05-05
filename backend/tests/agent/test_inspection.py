"""
Tests for inspection.py — parse_inspection_report.
All LLM calls are mocked — no real network requests.
"""

import base64
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.renovation import RENOVATION_BENCHMARKS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SLUGS = set(RENOVATION_BENCHMARKS.keys())

_GOOD_LLM_JSON = {
    "property_address": "318 Avalon Ave, San Francisco, CA 94112",
    "inspector": "Alonzo Inspections",
    "inspection_date": "2024-03-15",
    "systems": [
        {
            "name": "Plumbing - Waste Lines",
            "status": "deficient",
            "severity": "high",
            "findings": "Bathtub waste lines actively leaking into crawlspace",
            "renovation_category": "plumbing",
        },
        {
            "name": "Windows",
            "status": "deficient",
            "severity": "moderate",
            "findings": "Multiple fogged double-pane units with failed seals",
            "renovation_category": "windows",
        },
        {
            "name": "Water Heater",
            "status": "serviceable",
            "severity": "low",
            "findings": "",
            "renovation_category": "plumbing",
        },
    ],
    "summary": "2 deficiencies found; plumbing requires immediate attention.",
}


def _make_llm_response(json_payload: dict) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_payload)
    resp = MagicMock()
    resp.content = [block]
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseInspectionReport:
    @pytest.mark.asyncio
    async def test_golden_path_returns_expected_structure(self):
        """Mock LLM returns known JSON; verify output has required keys."""
        from agent.tools.inspection import parse_inspection_report

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)

            result = await parse_inspection_report(b"%PDF-fake-bytes")

        assert result is not None
        assert result["property_address"] == "318 Avalon Ave, San Francisco, CA 94112"
        assert result["inspector"] == "Alonzo Inspections"
        assert result["inspection_date"] == "2024-03-15"
        assert isinstance(result["systems"], list)
        assert len(result["systems"]) == 3
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_sends_pdf_as_document_block(self):
        """Verify the message to Claude contains a document block with media_type application/pdf."""
        from agent.tools.inspection import parse_inspection_report

        pdf_bytes = b"%PDF-1.4 fake content"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)

            await parse_inspection_report(pdf_bytes)

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs[1].get("messages") or call_kwargs[0][0] if call_kwargs[0] else call_kwargs.kwargs["messages"]
        # Find the user message content
        content = messages[0]["content"]
        doc_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "document"]
        assert len(doc_blocks) == 1
        src = doc_blocks[0]["source"]
        assert src["media_type"] == "application/pdf"
        assert src["type"] == "base64"
        assert src["data"] == base64.b64encode(pdf_bytes).decode()

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self):
        """LLM raises an exception → returns None."""
        from agent.tools.inspection import parse_inspection_report

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API error")

            result = await parse_inspection_report(b"%PDF-fake")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_unparseable_response(self):
        """LLM returns plain text that isn't JSON → returns None."""
        from agent.tools.inspection import parse_inspection_report

        bad_block = MagicMock()
        bad_block.type = "text"
        bad_block.text = "Sorry, I cannot parse that document."
        bad_resp = MagicMock()
        bad_resp.content = [bad_block]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = bad_resp

            result = await parse_inspection_report(b"%PDF-fake")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_api_key_missing(self):
        """No ANTHROPIC_API_KEY set → returns None without calling LLM."""
        from agent.tools.inspection import parse_inspection_report

        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if present
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                result = await parse_inspection_report(b"%PDF-fake")

        assert result is None

    @pytest.mark.asyncio
    async def test_systems_have_valid_renovation_category(self):
        """Every system in the parsed output has a renovation_category that's a known slug."""
        from agent.tools.inspection import parse_inspection_report

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)

            result = await parse_inspection_report(b"%PDF-fake")

        assert result is not None
        for system in result["systems"]:
            assert system["renovation_category"] in _VALID_SLUGS, (
                f"renovation_category '{system['renovation_category']}' is not a known slug"
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_bytes(self):
        """Empty bytes → returns None immediately without calling LLM."""
        from agent.tools.inspection import parse_inspection_report

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            result = await parse_inspection_report(b"")

        mock_client.messages.create.assert_not_called()
        assert result is None

    def test_prompt_defines_high_as_uninhabitable_threshold(self):
        """The extraction prompt should reserve 'high' for uninhabitable/immediately dangerous conditions."""
        from agent.tools.inspection import _EXTRACTION_PROMPT

        prompt_lower = _EXTRACTION_PROMPT.lower()
        assert "uninhabitable" in prompt_lower, (
            "Prompt must define 'high' severity in terms of habitability"
        )
        # Must NOT equate a generic 'repair recommended' with high severity
        assert "repair recommended" not in prompt_lower or "moderate" not in prompt_lower.split("repair recommended")[0][-50:], (
            "Prompt must not map 'repair recommended' directly to 'high' severity"
        )

    @pytest.mark.asyncio
    async def test_prompt_high_severity_criteria_sent_to_llm(self):
        """Verify that the uninhabitable threshold is present in the text block sent to the LLM."""
        from agent.tools.inspection import parse_inspection_report

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.inspection.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)

            await parse_inspection_report(b"%PDF-fake")

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs[1].get("messages") or call_kwargs.kwargs["messages"]
        content = messages[0]["content"]
        text_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "text"]
        assert len(text_blocks) == 1
        assert "uninhabitable" in text_blocks[0]["text"].lower()
