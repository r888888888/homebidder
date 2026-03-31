"""
Fetch comparable sales (comps) for a given property address.
Scrapes recently sold listings from Zillow search results.
"""

import asyncio
import json
import random
from typing import Any
from urllib.parse import urlencode

from playwright.async_api import async_playwright

from .scraper import _USER_AGENTS, _human_delay


async def fetch_comps(
    address: str,
    city: str,
    state: str,
    zip_code: str,
    bedrooms: int | None = None,
    radius_miles: float = 0.5,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    Search Zillow for recently sold comps near the subject property.
    Returns a list of comparable sales with price/sqft data.
    """
    location = f"{city}, {state} {zip_code}".strip(", ")
    params = {
        "searchQueryState": json.dumps({
            "pagination": {},
            "isMapVisible": False,
            "mapZoom": 14,
            "filterState": {
                "sort": {"value": "globalrelevanceex"},
                "rs": {"value": True},   # recently sold
                "fsba": {"value": False},
                "fsbo": {"value": False},
                "nc": {"value": False},
                "cmsn": {"value": False},
                "auc": {"value": False},
                "fore": {"value": False},
                "doz": {"value": "6"},   # sold within 6 months
            },
            "isListVisible": True,
        }),
        "searchTerm": location,
    }

    search_url = f"https://www.zillow.com/homes/recently_sold/{urlencode({'q': location})}/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = await context.new_page()
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}",
            lambda route: route.abort(),
        )

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
            await _human_delay(1000, 3000)

            raw = await page.evaluate("""() => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? el.textContent : null;
            }""")

            if raw:
                comps = _parse_zillow_search_results(raw, max_results)
                if comps:
                    return comps

            # Fallback: parse visible card text
            return await _scrape_cards(page, max_results)

        finally:
            await browser.close()


def _parse_zillow_search_results(raw: str, max_results: int) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
        results = (
            data.get("props", {})
            .get("pageProps", {})
            .get("searchPageState", {})
            .get("cat1", {})
            .get("searchResults", {})
            .get("listResults", [])
        )
        comps = []
        for r in results[:max_results]:
            sqft = r.get("area")
            sold_price = r.get("unformattedPrice") or r.get("price")
            comps.append({
                "address": r.get("address", ""),
                "sold_price": sold_price,
                "sold_date": r.get("soldDate", ""),
                "bedrooms": r.get("beds"),
                "bathrooms": r.get("baths"),
                "sqft": sqft,
                "price_per_sqft": round(sold_price / sqft, 2) if sold_price and sqft else None,
                "url": r.get("detailUrl", ""),
            })
        return comps
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []


async def _scrape_cards(page, max_results: int) -> list[dict[str, Any]]:
    """Fallback: extract address/price text from listing cards."""
    cards = await page.query_selector_all("[data-test='property-card']")
    comps = []
    for card in cards[:max_results]:
        text = await card.inner_text()
        comps.append({"raw_text": text.strip()[:500]})
    return comps
