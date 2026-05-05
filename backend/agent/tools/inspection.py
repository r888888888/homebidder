"""
Inspection report PDF parser — sends PDF to Claude as a document block
and extracts structured findings.
"""

import base64
import json
import logging
import re
from typing import Any

import anthropic

from config import settings

DEFAULT_MODEL = "claude-sonnet-4-6"
log = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are a real estate inspection report analyst. Extract structured data from this home inspection report.

Return a single JSON object with this exact schema:
{
  "property_address": "<full address from report>",
  "inspector": "<inspector name or company>",
  "inspection_date": "<ISO date string YYYY-MM-DD, or empty string if not found>",
  "systems": [
    {
      "name": "<system/component name, e.g. 'Plumbing - Waste Lines'>",
      "status": "<one of: serviceable | deficient | safety_hazard>",
      "severity": "<one of: low | moderate | high>",
      "findings": "<concise description of deficiency, or empty string if serviceable>",
      "renovation_category": "<one of the slugs below>"
    }
  ],
  "summary": "<1-2 sentence summary of major findings>"
}

Valid renovation_category slugs (pick the closest match):
kitchen, bathroom, flooring, paint, roof, electrical, plumbing, hvac,
foundation, seismic, windows, siding, hazmat_encap, hazmat_partial,
hazmat_full, sewer_lateral, insulation, termite_dryrot, deck_porch, chimney

Rules:
- Only include systems that have a finding worth flagging (serviceable items with no issues can be omitted,
  unless they are explicitly called out as noteworthy).
- Map severity using this strict threshold:
    high     → condition makes the home uninhabitable NOW or imminently uninhabitable when exposed to
               bad weather (e.g. major active roof failure or large breach open to the elements,
               foundation at imminent collapse risk, no functioning heat in a cold climate,
               live electrical hazard with imminent fire/electrocution risk, active sewage backup
               inside living space, condemned-level structural failure). Very few issues reach this bar.
    moderate → significant deficiency requiring repair but the home remains safely livable
               (e.g. active plumbing leak, failed HVAC, partial roof wear, deteriorated siding,
               substantial dry rot, panel upgrades, sewer lateral issues).
    low      → monitor or minor repair (e.g. fogged windows, cosmetic cracks, minor grading issues).
- status follows severity: safety_hazard → high; deficient → moderate or low; serviceable → low.
- Use the renovation_category slug that best matches the affected building system.
- Return JSON only — no markdown, no preamble.
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


async def parse_inspection_report(pdf_bytes: bytes) -> dict[str, Any] | None:
    """
    Parse a home inspection report PDF using Claude's native document understanding.

    Returns a structured dict with inspector metadata and per-system findings,
    or None if parsing fails or input is invalid.
    """
    if not pdf_bytes:
        return None

    try:
        api_key = settings.anthropic_api_key
    except RuntimeError:
        log.warning("parse_inspection_report: ANTHROPIC_API_KEY not set — skipping")
        return None

    model = DEFAULT_MODEL
    client = anthropic.AsyncAnthropic(api_key=api_key)

    encoded = base64.b64encode(pdf_bytes).decode()

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": encoded,
                            },
                        },
                        {
                            "type": "text",
                            "text": _EXTRACTION_PROMPT,
                        },
                    ],
                }
            ],
        )
    except Exception as exc:
        log.warning("parse_inspection_report: LLM call failed: %s", exc)
        return None

    text_parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))

    payload = _extract_json_object("\n".join(text_parts))
    if not payload:
        log.warning("parse_inspection_report: could not parse LLM JSON response")
        return None

    if "systems" not in payload or not isinstance(payload.get("systems"), list):
        log.warning("parse_inspection_report: 'systems' missing or not a list in LLM response")
        return None

    return payload
