"""
Claude agent orchestrator.

Runs a tool-use loop: Claude decides which tools to call, we dispatch them,
and feed results back until Claude produces a final recommendation.
"""

import asyncio
import json
import logging
import os
from typing import AsyncIterator

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

from .tools.property_lookup import lookup_property_by_address, _geocode
from .tools.neighborhood import fetch_neighborhood_context
from .tools.comps import fetch_comps
from .tools.pricing import analyze_market, recommend_offer
from .tools.mortgage_rate import get_current_mortgage_rate_pct
from .tools.mortgage_rates import fetch_mortgage_rates
from .tools.market_trends import fetch_market_trends
from .tools.fhfa import fetch_fhfa_hpi
from .tools.ca_hazards import fetch_ca_hazard_zones
from .tools.calenviroscreen import fetch_calenviroscreen_data
from .tools.sf_permits import fetch_sf_permits
from .tools.risk import assess_risk
from .tools.rentcast import fetch_rental_estimate
from .tools.ba_value_drivers import fetch_ba_value_drivers
from .tools.investment import compute_investment_metrics
from .tools.renovation import estimate_renovation_cost, _is_fixer_property

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are HomeBidder, an expert real estate analyst helping home buyers make competitive, data-driven offers in the SF Bay Area.

Call the following tools to gather data:
1. lookup_property_by_address — geocode the address and retrieve listing details.
2. fetch_neighborhood_context — use county, state, zip_code, address_matched from step 1.
3. fetch_comps — fetch recently sold comparable properties near the subject.
   When available from step 1, pass property_type as subject_property_type so comps match building type (condo/sfh/townhome).

Market analysis and offer recommendation will be computed automatically after comps are fetched.
Investment analysis will also be computed automatically after risk assessment:
- fetch_mortgage_rates
- fetch_rental_estimate
- fetch_ba_value_drivers
- compute_investment_metrics
Your job is to write a clear, data-backed narrative once all results are available.

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
            "Fetch Census ACS neighborhood statistics (median home value, housing units, vacancy rate). "
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
    {
        "name": "fetch_mortgage_rates",
        "description": "Fetch latest Freddie Mac PMMS mortgage rates (30-year and 15-year fixed) via FRED.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "fetch_rental_estimate",
        "description": "Fetch rental estimate for the matched address using RentCast with ACS fallback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "matched_address": {"type": "string"},
                "zip_code": {"type": "string"},
            },
            "required": ["matched_address", "zip_code"],
        },
    },
    {
        "name": "fetch_ba_value_drivers",
        "description": "Compute Bay Area value drivers: ADU potential, rent control implications, and transit proximity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property": {"type": "object"},
                "rental_estimate": {"type": "object"},
                "zip_code": {"type": "string"},
            },
            "required": ["property", "rental_estimate", "zip_code"],
        },
    },
    {
        "name": "compute_investment_metrics",
        "description": "Compute investment metrics (yield, cashflow, appreciation, rating) from assembled inputs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property": {"type": "object"},
                "rental_estimate": {"type": "object"},
                "mortgage_rates": {"type": "object"},
                "hpi_trend": {"type": "object"},
                "ba_value_drivers": {"type": "object"},
            },
            "required": [
                "property",
                "rental_estimate",
                "mortgage_rates",
                "hpi_trend",
                "ba_value_drivers",
            ],
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
        full = await fetch_comps(**inputs)
        return json.dumps(full["comps"]), full
    elif name == "analyze_market":
        result = analyze_market(**inputs)
        return json.dumps(result), None
    elif name == "recommend_offer":
        result = recommend_offer(**inputs)
        return json.dumps(result), result
    elif name == "fetch_mortgage_rates":
        result = await fetch_mortgage_rates()
        return json.dumps(result), result
    elif name == "fetch_rental_estimate":
        result = await fetch_rental_estimate(**inputs)
        return json.dumps(result), result
    elif name == "fetch_ba_value_drivers":
        result = await fetch_ba_value_drivers(**inputs)
        return json.dumps(result), result
    elif name == "compute_investment_metrics":
        result = compute_investment_metrics(**inputs)
        return json.dumps(result), result
    else:
        result = {"error": f"Unknown tool: {name}"}
        return json.dumps(result), None


async def _persist_analysis(
    db: AsyncSession,
    address_input: str,
    property_result: dict | None,
    neighborhood_result: dict | None,
    comps_result: list | None,
    offer_result: dict | None,
    risk_result: dict | None,
    investment_result: dict | None,
    final_text: str,
    permits_result: dict | None = None,
    renovation_result: dict | None = None,
    buyer_context: str = "",
) -> int:
    """Write Listing, Analysis, and Comp records to DB and return analysis id."""
    from sqlalchemy import select
    from db.models import Listing, Analysis, Comp

    address_matched = (property_result or {}).get("address_matched") or address_input

    # Upsert Listing
    stmt = select(Listing).where(Listing.address_matched == address_matched)
    result = await db.execute(stmt)
    listing = result.scalar_one_or_none()
    if listing is None:
        listing = Listing(
            address_input=address_input,
            address_matched=address_matched,
            latitude=(property_result or {}).get("latitude"),
            longitude=(property_result or {}).get("longitude"),
            county=(property_result or {}).get("county"),
            state=(property_result or {}).get("state"),
            zip_code=(property_result or {}).get("zip_code"),
            price=(property_result or {}).get("price"),
            bedrooms=(property_result or {}).get("bedrooms"),
            bathrooms=(property_result or {}).get("bathrooms"),
            sqft=(property_result or {}).get("sqft"),
            year_built=(property_result or {}).get("year_built"),
            property_type=(property_result or {}).get("property_type"),
            avm_estimate=(property_result or {}).get("avm_estimate"),
        )
        db.add(listing)
    else:
        listing.address_input = address_input
        if property_result:
            listing.latitude = property_result.get("latitude")
            listing.longitude = property_result.get("longitude")
            listing.county = property_result.get("county")
            listing.state = property_result.get("state")
            listing.zip_code = property_result.get("zip_code")
            listing.price = property_result.get("price")
            listing.bedrooms = property_result.get("bedrooms")
            listing.bathrooms = property_result.get("bathrooms")
            listing.sqft = property_result.get("sqft")
            listing.year_built = property_result.get("year_built")
            listing.property_type = property_result.get("property_type")
            listing.avm_estimate = property_result.get("avm_estimate")
    await db.flush()

    # Insert Analysis
    analysis = Analysis(
        listing_id=listing.id,
        offer_low=(offer_result or {}).get("offer_low"),
        offer_high=(offer_result or {}).get("offer_high"),
        offer_recommended=(offer_result or {}).get("offer_recommended"),
        rationale=final_text or None,
        risk_level=(risk_result or {}).get("overall_risk"),
        investment_rating=(investment_result or {}).get("investment_rating"),
        property_data_json=json.dumps(property_result) if property_result else None,
        neighborhood_data_json=json.dumps(neighborhood_result) if neighborhood_result else None,
        offer_data_json=json.dumps(offer_result) if offer_result else None,
        risk_data_json=json.dumps(risk_result) if risk_result else None,
        investment_data_json=json.dumps(investment_result) if investment_result else None,
        permits_data_json=json.dumps(permits_result) if permits_result else None,
        renovation_data_json=json.dumps(renovation_result) if renovation_result else None,
        buyer_context=buyer_context or None,
    )
    db.add(analysis)
    await db.flush()

    # Bulk insert Comps
    for comp in (comps_result or []):
        db.add(Comp(
            analysis_id=analysis.id,
            address=comp.get("address", ""),
            sold_price=comp.get("sold_price"),
            sold_date=comp.get("sold_date"),
            bedrooms=comp.get("bedrooms"),
            bathrooms=comp.get("bathrooms"),
            sqft=comp.get("sqft"),
            price_per_sqft=comp.get("price_per_sqft"),
            distance_miles=comp.get("distance_miles"),
            pct_over_asking=comp.get("pct_over_asking"),
        ))

    await db.commit()
    return analysis.id


async def _load_cached_analysis(db: AsyncSession, address_matched: str):
    """Return the most recent Analysis for address_matched, or None."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from db.models import Analysis, Listing

    stmt = (
        select(Analysis)
        .join(Listing)
        .options(selectinload(Analysis.comps), selectinload(Analysis.listing))
        .where(Listing.address_matched == address_matched)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _stream_cached_analysis(analysis) -> AsyncIterator[str]:
    """Replay stored Analysis as SSE events, identical in shape to the live pipeline."""
    yield f"data: {json.dumps({'type': 'status', 'text': 'Loading from cache\u2026'})}\n\n"

    tool_pairs = [
        ("lookup_property_by_address", analysis.property_data_json),
        ("fetch_neighborhood_context", analysis.neighborhood_data_json),
        ("recommend_offer", analysis.offer_data_json),
        ("assess_risk", analysis.risk_data_json),
        ("compute_investment_metrics", analysis.investment_data_json),
    ]

    # Comps: reconstruct list from Comp ORM rows
    if analysis.comps:
        comps_list = [
            {
                "address": c.address,
                "sold_price": c.sold_price,
                "sold_date": c.sold_date,
                "bedrooms": c.bedrooms,
                "bathrooms": c.bathrooms,
                "sqft": c.sqft,
                "price_per_sqft": c.price_per_sqft,
                "distance_miles": c.distance_miles,
                "pct_over_asking": c.pct_over_asking,
            }
            for c in analysis.comps
        ]
        yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'fetch_comps', 'input': {}})}\n\n"
        yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'fetch_comps', 'result': comps_list})}\n\n"

    for tool_name, json_blob in tool_pairs:
        if not json_blob:
            continue
        data = json.loads(json_blob)
        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'input': {}})}\n\n"
        yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': data})}\n\n"

    if analysis.permits_data_json:
        data = json.loads(analysis.permits_data_json)
        yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'fetch_sf_permits', 'input': {}})}\n\n"
        yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'fetch_sf_permits', 'result': data})}\n\n"

    if analysis.renovation_data_json:
        data = json.loads(analysis.renovation_data_json)
        yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'estimate_renovation_cost', 'input': {}})}\n\n"
        yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'estimate_renovation_cost', 'result': data})}\n\n"

    if analysis.rationale:
        yield f"data: {json.dumps({'type': 'text', 'text': analysis.rationale})}\n\n"

    yield f"data: {json.dumps({'type': 'analysis_id', 'id': analysis.id})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def run_agent(address: str, buyer_context: str = "", db: AsyncSession | None = None, force_refresh: bool = False) -> AsyncIterator[str]:
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

    # Cache check: geocode the address, look up the most recent Analysis in DB.
    # On a hit, replay stored events and return — skipping the full pipeline.
    if not force_refresh and db is not None:
        try:
            geo = await _geocode(address)
            address_matched = geo["address_matched"]
            cached = await _load_cached_analysis(db, address_matched)
            if cached is not None:
                async for chunk in _stream_cached_analysis(cached):
                    yield chunk
                return
        except Exception:
            pass  # geocode failed or no cache — fall through to live pipeline

    # State tracked across turns
    property_result: dict | None = None
    neighborhood_result: dict | None = None
    phase6_trends: dict | None = None
    phase6_fhfa: dict | None = None
    phase6_hazards: dict | None = None
    phase6_ejscreen: dict | None = None
    phase6_permits: dict | None = None
    phase8_investment: dict | None = None
    analysis_done = False
    # Persistence state
    comps_result: list | None = None
    offer_result_persist: dict | None = None
    risk_result_persist: dict | None = None
    renovation_result_persist: dict | None = None
    final_text_parts: list[str] = []
    # Validation mode: set when subject property was itself recently sold
    subject_sale_data: dict | None = None

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
                final_text_parts.append(block.text)
                yield f"data: {json.dumps({'type': 'text', 'text': block.text})}\n\n"

        if response.stop_reason == "end_turn":
            if db is not None and (property_result is not None or analysis_done):
                try:
                    analysis_id = await _persist_analysis(
                        db=db,
                        address_input=address,
                        property_result=property_result,
                        neighborhood_result=neighborhood_result,
                        comps_result=comps_result,
                        offer_result=offer_result_persist,
                        risk_result=risk_result_persist,
                        investment_result=phase8_investment,
                        final_text="".join(final_text_parts),
                        permits_result=phase6_permits,
                        renovation_result=renovation_result_persist,
                        buyer_context=buyer_context,
                    )
                    yield f"data: {json.dumps({'type': 'analysis_id', 'id': analysis_id})}\n\n"
                except Exception as exc:
                    log.error("Failed to persist analysis: %s", exc, exc_info=True)
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            dispatched: dict[str, object] = {}

            for block in response.content:
                if block.type == "tool_use":
                    # Supplement fetch_comps with property context Claude may have omitted
                    inputs = dict(block.input)
                    if block.name == "fetch_comps" and property_result:
                        if "subject_property_type" not in inputs and property_result.get("property_type"):
                            inputs["subject_property_type"] = property_result["property_type"]
                        if "subject_lat" not in inputs and property_result.get("latitude"):
                            inputs["subject_lat"] = property_result["latitude"]
                        if "subject_lon" not in inputs and property_result.get("longitude"):
                            inputs["subject_lon"] = property_result["longitude"]
                        if "subject_sqft" not in inputs and property_result.get("sqft"):
                            inputs["subject_sqft"] = property_result["sqft"]
                    log.info("Dispatching tool: %s  input_keys=%s", block.name, list(inputs.keys()))
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': inputs})}\n\n"
                    try:
                        result_str, parsed = await _dispatch_tool(block.name, inputs)
                        log.info("Tool %s returned %d bytes parsed=%s", block.name, len(result_str), parsed is not None)
                    except Exception as exc:
                        log.error("Tool %r raised: %s", block.name, exc, exc_info=True)
                        result_str = json.dumps({"error": f"Tool '{block.name}' failed: {exc}"})
                        parsed = None

                    if block.name == "fetch_comps" and parsed is not None:
                        # Keep subject_sale for validation; send only comps list to frontend.
                        subject_sale_data = parsed.get("subject_sale")
                        comps_only = parsed.get("comps", [])
                        dispatched[block.name] = comps_only
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': comps_only})}\n\n"
                    elif parsed is not None:
                        dispatched[block.name] = parsed
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': parsed})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            if "fetch_neighborhood_context" in dispatched:
                neighborhood_result = dispatched["fetch_neighborhood_context"]

            if "lookup_property_by_address" in dispatched:
                property_result = dispatched["lookup_property_by_address"]

                # Phase 6: auto-fetch market trends, FHFA HPI, and CA hazard zones
                # in parallel as soon as we have lat/lon and zip_code.
                # For San Francisco properties, also fetch permit history.
                zip_code = property_result.get("zip_code")
                lat = property_result.get("latitude")
                lon = property_result.get("longitude")
                county = str(property_result.get("county") or "").strip().lower()
                address_matched = str(property_result.get("address_matched") or "")
                unit = property_result.get("unit")

                phase6_tools: list[tuple[str, object, dict]] = []
                if zip_code:
                    phase6_tools.append(("fetch_market_trends", fetch_market_trends(zip_code), {}))
                    phase6_tools.append(("fetch_fhfa_hpi", fetch_fhfa_hpi(zip_code), {}))
                if lat and lon:
                    phase6_tools.append(("fetch_ca_hazard_zones", fetch_ca_hazard_zones(lat, lon), {}))
                if county == "san francisco" and address_matched:
                    permit_inputs = {"address_matched": address_matched}
                    if unit:
                        permit_inputs["unit"] = unit
                    phase6_tools.append((
                        "fetch_sf_permits",
                        fetch_sf_permits(address_matched=address_matched, unit=unit),
                        permit_inputs,
                    ))

                if phase6_tools:
                    real_tasks = [coro for _, coro, _ in phase6_tools]
                    try:
                        real_results = await asyncio.gather(*real_tasks, return_exceptions=True)
                    except Exception:
                        real_results = []

                    for (tool_name, _, tool_input), result in zip(phase6_tools, real_results):
                        if result is None or isinstance(result, Exception):
                            if isinstance(result, Exception):
                                log.warning("Phase 6 tool %s failed: %s", tool_name, result)
                            continue
                        # Cache in state for downstream assess_risk
                        if tool_name == "fetch_market_trends":
                            phase6_trends = result
                        elif tool_name == "fetch_fhfa_hpi":
                            phase6_fhfa = result
                        elif tool_name == "fetch_ca_hazard_zones":
                            phase6_hazards = result
                        elif tool_name == "fetch_sf_permits":
                            phase6_permits = result
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'input': tool_input})}\n\n"
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': result})}\n\n"
                        log.info("Phase 6 auto-computed %s", tool_name)

                # fetch_calenviroscreen_data is synchronous (in-memory shapely lookup) —
                # call it directly after the async gather to avoid crashing asyncio.gather.
                if lat and lon:
                    try:
                        ces_result = fetch_calenviroscreen_data(lat, lon)
                        if ces_result is not None:
                            phase6_ejscreen = ces_result
                            yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'fetch_calenviroscreen_data', 'input': {}})}\n\n"
                            yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'fetch_calenviroscreen_data', 'result': ces_result})}\n\n"
                            log.info("Phase 6 auto-computed fetch_calenviroscreen_data")
                    except Exception as exc:
                        log.warning("Phase 6 fetch_calenviroscreen_data failed: %s", exc)

            # Phase 2: auto-compute analyze_market + recommend_offer after comps arrive
            if "fetch_comps" in dispatched and not analysis_done:
                comps = dispatched["fetch_comps"]
                comps_result = comps  # persist outer scope
                listing = property_result or {}

                # analyze_market
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'analyze_market', 'input': {'comps': f'[{len(comps)} comps]'}})}\n\n"
                market_stats = analyze_market(comps) if comps else {"error": "no comps"}
                log.info("Auto-computed analyze_market: %s", list(market_stats.keys()))
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'analyze_market', 'result': market_stats})}\n\n"

                # recommend_offer
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'recommend_offer', 'input': {'listing': '...', 'market_stats': '...'}})}\n\n"
                mortgage_rate_pct = await get_current_mortgage_rate_pct()
                offer_result = recommend_offer(
                    listing,
                    market_stats,
                    buyer_context,
                    mortgage_rate_pct=mortgage_rate_pct,
                )
                offer_result_persist = offer_result  # persist outer scope
                log.info("Auto-computed recommend_offer: posture=%s", offer_result.get("posture"))
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'recommend_offer', 'result': offer_result})}\n\n"

                # Validation mode: compare estimate against actual sale price when known.
                if subject_sale_data is not None:
                    actual = subject_sale_data["sold_price"]
                    estimate = offer_result.get("fair_value_estimate")
                    ci = offer_result.get("fair_value_confidence_interval") or {}
                    ci_low, ci_high = ci.get("low"), ci.get("high")
                    if estimate is not None and actual > 0:
                        error_dollars = round(estimate - actual)
                        error_pct = round((error_dollars / actual) * 100, 1)
                        within_ci = (
                            ci_low is not None
                            and ci_high is not None
                            and ci_low <= actual <= ci_high
                        )
                        validation_payload = {
                            "actual_sold_price": actual,
                            "estimated_price": estimate,
                            "error_dollars": error_dollars,
                            "error_pct": error_pct,
                            "within_ci": within_ci,
                            "sold_date": subject_sale_data.get("sold_date"),
                            "address": subject_sale_data.get("address"),
                        }
                        log.info(
                            "Validation mode: estimate=%s actual=%s error_pct=%s within_ci=%s",
                            estimate, actual, error_pct, within_ci,
                        )
                        yield f"data: {json.dumps({'type': 'validation_result', 'result': validation_payload})}\n\n"

                # Phase 7: auto-compute risk assessment
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'assess_risk', 'input': {}})}\n\n"
                risk_result = assess_risk(
                    listing=listing,
                    market_stats=market_stats,
                    offer_result=offer_result,
                    neighborhood=neighborhood_result,
                    market_trends=phase6_trends,
                    fhfa_hpi=phase6_fhfa,
                    hazard_zones=phase6_hazards,
                    ejscreen=phase6_ejscreen,
                )
                risk_result_persist = risk_result  # persist outer scope
                log.info("Auto-computed assess_risk: overall=%s score=%s", risk_result.get("overall_risk"), risk_result.get("score"))
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'assess_risk', 'result': risk_result})}\n\n"

                # Phase 8: auto-compute investment analysis inputs in parallel,
                # then compute investment metrics.
                listing_zip = str(listing.get("zip_code") or "")
                matched_address = str(listing.get("address_matched") or address)

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'fetch_mortgage_rates', 'input': {}})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'fetch_rental_estimate', 'input': {'matched_address': matched_address, 'zip_code': listing_zip}})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'fetch_ba_value_drivers', 'input': {'property': '...', 'rental_estimate': '...', 'zip_code': listing_zip}})}\n\n"

                phase8_results = await asyncio.gather(
                    fetch_mortgage_rates(),
                    fetch_rental_estimate(matched_address, listing_zip),
                    fetch_ba_value_drivers(listing, {}, listing_zip),
                    return_exceptions=True,
                )

                mortgage_rates_result = phase8_results[0] if not isinstance(phase8_results[0], Exception) else {"error": str(phase8_results[0])}
                rental_estimate_result = phase8_results[1] if not isinstance(phase8_results[1], Exception) else {"error": str(phase8_results[1])}
                ba_drivers_result = phase8_results[2] if not isinstance(phase8_results[2], Exception) else {"error": str(phase8_results[2])}

                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'fetch_mortgage_rates', 'result': mortgage_rates_result})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'fetch_rental_estimate', 'result': rental_estimate_result})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'fetch_ba_value_drivers', 'result': ba_drivers_result})}\n\n"

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'compute_investment_metrics', 'input': {'property': '...', 'rental_estimate': '...', 'mortgage_rates': '...', 'hpi_trend': '...', 'ba_value_drivers': '...'}})}\n\n"
                phase8_investment = compute_investment_metrics(
                    property=listing,
                    rental_estimate=rental_estimate_result if isinstance(rental_estimate_result, dict) else {},
                    mortgage_rates=mortgage_rates_result if isinstance(mortgage_rates_result, dict) else {},
                    hpi_trend=phase6_fhfa if isinstance(phase6_fhfa, dict) else {},
                    ba_value_drivers=ba_drivers_result if isinstance(ba_drivers_result, dict) else {},
                )
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'compute_investment_metrics', 'result': phase8_investment})}\n\n"

                # Phase 9: fixer vs turn-key comparison (fixer properties only)
                is_fixer = _is_fixer_property(listing)
                fv_estimate = offer_result.get("fair_value_estimate")
                log.info("Phase 9 guard: is_fixer=%s fair_value_estimate=%s", is_fixer, fv_estimate)
                if is_fixer and fv_estimate:
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'estimate_renovation_cost', 'input': {}})}\n\n"
                    try:
                        renovation_result = await estimate_renovation_cost(listing, offer_result, buyer_context=buyer_context)
                    except Exception as exc:
                        log.warning("Phase 9 estimate_renovation_cost failed: %s", exc)
                        renovation_result = None
                    log.info("Phase 9 renovation_result=%s", "present" if renovation_result else "None")
                    if renovation_result is not None:
                        renovation_result_persist = renovation_result
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'estimate_renovation_cost', 'result': renovation_result})}\n\n"
                        log.info("Phase 9 renovation verdict=%s savings=%s", renovation_result.get("verdict"), renovation_result.get("savings_mid"))

                # Inject results into conversation as a concise summary (avoids re-sending full comps)
                summary = (
                    "The following analysis has been automatically computed.\n\n"
                    f"**Market Analysis:**\n{json.dumps(market_stats)}\n\n"
                    f"**Offer Recommendation:**\n{json.dumps(offer_result)}\n\n"
                    f"**Risk Assessment:**\n{json.dumps(risk_result)}\n\n"
                    f"**Permit History (SF only):**\n{json.dumps(phase6_permits)}\n\n"
                    f"**Investment Analysis:**\n{json.dumps(phase8_investment)}\n\n"
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
