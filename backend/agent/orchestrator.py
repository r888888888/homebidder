"""
Claude agent orchestrator.

Runs a tool-use loop: Claude decides which tools to call, we dispatch them,
and feed results back until Claude produces a final recommendation.
"""

import json
import logging
import os
from typing import AsyncIterator

import anthropic

log = logging.getLogger(__name__)

from .tools.property_lookup import lookup_property_by_address
from .tools.neighborhood import fetch_neighborhood_context
from .tools.comps import fetch_comps
from .tools.pricing import analyze_market, recommend_offer

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are HomeBidder, an expert real estate analyst helping home buyers make competitive, data-driven offers in the SF Bay Area.

Call the following tools to gather data:
1. lookup_property_by_address — geocode the address and retrieve listing details.
2. fetch_neighborhood_context — use county, state, zip_code, address_matched from step 1.
3. fetch_comps — fetch recently sold comparable properties near the subject.
   When available from step 1, pass property_type as subject_property_type so comps match building type (condo/sfh/townhome).

Market analysis and offer recommendation will be computed automatically after comps are fetched.
Your job is to write a clear, data-backed narrative once all results are available.

For Bay Area properties: always surface the Prop 13 tax shock — compare the seller's current annual tax to the buyer's estimated annual tax at purchase price (purchase_price × 1.25%).
Be specific, cite the comp data, and explain your reasoning in plain language a first-time buyer can understand.
Interpret the offer recommendation output and add qualitative context — do not simply restate the numbers.
"""

TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "lookup_property_by_address",
        "description": (
            "Geocode a free-text address via the Census Geocoder, then scrape listing "
            "details from Realtor.com/Redfin via homeharvest. Falls back to RentCast AVM "
            "for unlisted/off-market properties. Returns matched address, coordinates, "
            "price, beds/baths/sqft, year built, lot size, property type, HOA fee, "
            "days on market, price history, and AVM estimate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Free-text address string, e.g. '450 Sanchez St, San Francisco, CA 94114'",
                },
            },
            "required": ["address"],
        },
    },
    {
        "name": "fetch_neighborhood_context",
        "description": (
            "Fetch Prop 13 assessed-value data from the county assessor (SF, Alameda, Santa Clara) "
            "and Census ACS neighborhood statistics (median home value, housing units, vacancy rate). "
            "Call after lookup_property_by_address using its county, state, zip_code, and address_matched."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "county":          {"type": "string"},
                "state":           {"type": "string"},
                "zip_code":        {"type": "string"},
                "address_matched": {"type": "string"},
            },
            "required": ["county", "state", "zip_code", "address_matched"],
        },
    },
    {
        "name": "fetch_comps",
        "description": (
            "Search for recently sold comparable properties near the subject address. "
            "Returns comps with sold_price, sqft, price_per_sqft, pct_over_asking, and distance_miles. "
            "Pass subject_lat, subject_lon from lookup_property_by_address, subject_sqft when known, "
            "and subject_property_type (e.g. CONDO/SINGLE_FAMILY/TOWNHOUSE) to filter by building type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address":      {"type": "string"},
                "city":         {"type": "string"},
                "state":        {"type": "string"},
                "zip_code":     {"type": "string"},
                "subject_lat":  {"type": "number", "description": "Subject property latitude from lookup_property_by_address"},
                "subject_lon":  {"type": "number", "description": "Subject property longitude from lookup_property_by_address"},
                "subject_sqft": {"type": "integer", "description": "Subject sqft; filters comps to ±25% when provided"},
                "subject_property_type": {"type": "string", "description": "Subject property type; filters comps to matching type (condo/sfh/townhome) when provided"},
                "bedrooms":     {"type": "integer", "description": "Filter comps to similar bedroom count"},
                "max_results":  {"type": "integer", "default": 100},
            },
            "required": ["address", "city", "state", "zip_code"],
        },
    },
    {
        "name": "analyze_market",
        "description": "Compute median/mean price-per-sqft and price statistics from a list of comps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "comps": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of comp objects returned by fetch_comps",
                },
            },
            "required": ["comps"],
        },
    },
    {
        "name": "recommend_offer",
        "description": "Generate a preliminary offer price range (low / recommended / high) based on listing data and market stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "listing": {"type": "object", "description": "Listing data from lookup_property_by_address"},
                "market_stats": {"type": "object", "description": "Output of analyze_market"},
                "buyer_context": {
                    "type": "string",
                    "description": "Optional buyer notes, e.g. 'must close fast', 'flexible timeline', 'multiple offers expected'",
                },
            },
            "required": ["listing", "market_stats"],
        },
    },
]


async def _dispatch_tool(name: str, inputs: dict) -> tuple[str, dict | None]:
    """
    Dispatch a tool call and return (json_result_string, parsed_result_or_None).
    parsed_result is set for tools whose result should be streamed as tool_result events.
    """
    if name == "lookup_property_by_address":
        result = await lookup_property_by_address(**inputs)
        return json.dumps(result), result
    elif name == "fetch_neighborhood_context":
        result = await fetch_neighborhood_context(**inputs)
        return json.dumps(result), result
    elif name == "fetch_comps":
        result = await fetch_comps(**inputs)
        return json.dumps(result), result
    elif name == "analyze_market":
        result = analyze_market(**inputs)
        return json.dumps(result), None
    elif name == "recommend_offer":
        result = recommend_offer(**inputs)
        return json.dumps(result), result
    else:
        result = {"error": f"Unknown tool: {name}"}
        return json.dumps(result), None


async def run_agent(address: str, buyer_context: str = "") -> AsyncIterator[str]:
    """
    Run the full agent loop for a property address.
    Yields SSE-formatted text chunks as the agent reasons.

    Pipeline:
      Phase 1 — Claude calls lookup_property_by_address, fetch_neighborhood_context, fetch_comps.
      Phase 2 — Orchestrator auto-computes analyze_market + recommend_offer (avoids Claude
                 re-serializing the full comps array, which hits max_tokens).
      Phase 3 — Final Claude call (no tools) writes the narrative.
    """
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[anthropic.types.MessageParam] = [
        {
            "role": "user",
            "content": (
                f"Please analyze this property and recommend an offer price.\n\n"
                f"Property address: {address}\n"
                + (f"Buyer notes: {buyer_context}\n" if buyer_context else "")
            ),
        }
    ]

    yield f"data: {json.dumps({'type': 'status', 'text': 'Starting analysis...'})}\n\n"

    # State tracked across turns
    property_result: dict | None = None
    analysis_done = False

    # Data-gathering tools Claude is allowed to call
    DATA_TOOLS = [t for t in TOOLS if t["name"] in ("lookup_property_by_address", "fetch_neighborhood_context", "fetch_comps")]

    while True:
        active_tools = DATA_TOOLS if not analysis_done else []

        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=8000,
                system=SYSTEM_PROMPT,
                tools=active_tools,
                messages=messages,
            )
        except anthropic.RateLimitError as exc:
            retry_after: int | None = None
            try:
                retry_after = int(exc.response.headers.get("retry-after", ""))
            except (AttributeError, ValueError):
                pass

            log.warning("Anthropic rate limit hit (retry-after=%s)", retry_after)

            msg = (
                "The analysis service is currently at capacity. "
                + (f"Please try again in {retry_after} seconds." if retry_after else "Please try again in a moment.")
            )
            yield f"data: {json.dumps({'type': 'error', 'text': msg, 'retry_after': retry_after})}\n\n"
            break

        except anthropic.BadRequestError as exc:
            log.error("Anthropic bad request (400): %s", exc.message)
            yield f"data: {json.dumps({'type': 'error', 'text': 'The request could not be completed. Please try a different address or contact support if the problem persists.', 'retry_after': None})}\n\n"
            break

        log.info("Claude stop_reason=%s content_blocks=%d analysis_done=%s", response.stop_reason, len(response.content), analysis_done)

        # Stream any text content to client
        for block in response.content:
            if block.type == "text" and block.text:
                yield f"data: {json.dumps({'type': 'text', 'text': block.text})}\n\n"

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            dispatched: dict[str, object] = {}

            for block in response.content:
                if block.type == "tool_use":
                    log.info("Dispatching tool: %s  input_keys=%s", block.name, list(block.input.keys()))
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"
                    try:
                        result_str, parsed = await _dispatch_tool(block.name, block.input)
                        log.info("Tool %s returned %d bytes parsed=%s", block.name, len(result_str), parsed is not None)
                    except Exception as exc:
                        log.error("Tool %r raised: %s", block.name, exc, exc_info=True)
                        result_str = json.dumps({"error": f"Tool '{block.name}' failed: {exc}"})
                        parsed = None

                    if parsed is not None:
                        dispatched[block.name] = parsed
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': parsed})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            if "lookup_property_by_address" in dispatched:
                property_result = dispatched["lookup_property_by_address"]

            # Phase 2: auto-compute analyze_market + recommend_offer after comps arrive
            if "fetch_comps" in dispatched and not analysis_done:
                comps = dispatched["fetch_comps"]
                listing = property_result or {}

                # analyze_market
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'analyze_market', 'input': {'comps': f'[{len(comps)} comps]'}})}\n\n"
                market_stats = analyze_market(comps) if comps else {"error": "no comps"}
                log.info("Auto-computed analyze_market: %s", list(market_stats.keys()))
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'analyze_market', 'result': market_stats})}\n\n"

                # recommend_offer
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'recommend_offer', 'input': {'listing': '...', 'market_stats': '...'}})}\n\n"
                offer_result = recommend_offer(listing, market_stats, buyer_context)
                log.info("Auto-computed recommend_offer: posture=%s", offer_result.get("posture"))
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'recommend_offer', 'result': offer_result})}\n\n"

                # Inject results into conversation as a concise summary (avoids re-sending full comps)
                summary = (
                    "The following analysis has been automatically computed.\n\n"
                    f"**Market Analysis:**\n{json.dumps(market_stats)}\n\n"
                    f"**Offer Recommendation:**\n{json.dumps(offer_result)}\n\n"
                    "Please now write your final narrative for the buyer."
                )
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                messages.append({"role": "assistant", "content": "I have all the data I need. Let me write the analysis."})
                messages.append({"role": "user", "content": summary})
                analysis_done = True
                continue

            # Normal turn: append assistant + tool results and loop
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            log.warning("Unexpected stop_reason=%r — ending loop", response.stop_reason)
            break

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
