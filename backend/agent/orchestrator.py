"""
Claude agent orchestrator.

Runs a tool-use loop: Claude decides which tools to call, we dispatch them,
and feed results back until Claude produces a final recommendation.
"""

import json
import os
from typing import AsyncIterator

import anthropic

from .tools.scraper import scrape_listing
from .tools.comps import fetch_comps
from .tools.pricing import analyze_market, recommend_offer

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are HomeBidder, an expert real estate analyst helping home buyers make competitive, data-driven offers.

Your job:
1. Scrape the target listing to understand the property details.
2. Fetch comparable sold listings (comps) nearby.
3. Analyze the comp market data statistically.
4. Recommend a realistic offer price range with clear rationale.

Be specific, cite the comp data, and explain your reasoning in plain language a first-time buyer can understand.
Always present: a low (conservative), recommended, and high (aggressive) offer figure.
"""

TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "scrape_listing",
        "description": "Scrape a Zillow or Redfin listing URL to extract property details (price, beds, baths, sqft, year built, description, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL of the listing page"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "fetch_comps",
        "description": "Search for recently sold comparable properties near the subject address. Returns a list of comp sales with price, sqft, and price-per-sqft.",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "zip_code": {"type": "string"},
                "bedrooms": {"type": "integer", "description": "Filter comps to similar bedroom count"},
                "radius_miles": {"type": "number", "default": 0.5},
                "max_results": {"type": "integer", "default": 10},
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
                "listing": {"type": "object", "description": "Listing data from scrape_listing"},
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


async def _dispatch_tool(name: str, inputs: dict) -> str:
    if name == "scrape_listing":
        result = await scrape_listing(**inputs)
    elif name == "fetch_comps":
        result = await fetch_comps(**inputs)
    elif name == "analyze_market":
        result = analyze_market(**inputs)
    elif name == "recommend_offer":
        result = recommend_offer(**inputs)
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result)


async def run_agent(listing_url: str, buyer_context: str = "") -> AsyncIterator[str]:
    """
    Run the full agent loop for a listing URL.
    Yields SSE-formatted text chunks as the agent reasons.
    """
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[anthropic.types.MessageParam] = [
        {
            "role": "user",
            "content": (
                f"Please analyze this listing and recommend an offer price.\n\n"
                f"Listing URL: {listing_url}\n"
                + (f"Buyer notes: {buyer_context}\n" if buyer_context else "")
            ),
        }
    ]

    yield f"data: {json.dumps({'type': 'status', 'text': 'Starting analysis...'})}\n\n"

    while True:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Stream any text content to client
        for block in response.content:
            if block.type == "text" and block.text:
                yield f"data: {json.dumps({'type': 'text', 'text': block.text})}\n\n"

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"
                    result_str = await _dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            # Append assistant turn + tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason
            break

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
