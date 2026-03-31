"""
Playwright-based scraper for Zillow and Redfin listing pages.

NOTE: Scraping Zillow/Redfin may violate their Terms of Service.
Use only for personal/research purposes, respect rate limits,
and consider migrating to a licensed data API (Attom, RealEstateAPI)
at scale.
"""

import asyncio
import json
import random
from typing import Any

from playwright.async_api import async_playwright, Page


_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


async def _human_delay(min_ms: int = 800, max_ms: int = 2500) -> None:
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)


async def scrape_listing(url: str) -> dict[str, Any]:
    """
    Scrape a single listing page and return structured data.
    Supports Zillow and Redfin URLs.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page: Page = await context.new_page()

        # Block unnecessary resources to speed up scraping
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}",
            lambda route: route.abort(),
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await _human_delay()

            if "zillow.com" in url:
                data = await _extract_zillow(page)
            elif "redfin.com" in url:
                data = await _extract_redfin(page)
            else:
                data = await _extract_generic(page)

            data["url"] = url
            return data

        finally:
            await browser.close()


async def _extract_zillow(page: Page) -> dict[str, Any]:
    # Zillow embeds listing data in a <script id="__NEXT_DATA__"> JSON blob
    raw = await page.evaluate("""() => {
        const el = document.getElementById('__NEXT_DATA__');
        return el ? el.textContent : null;
    }""")

    if raw:
        try:
            next_data = json.loads(raw)
            # Path varies by page type; try common locations
            props = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("componentProps", {})
                .get("gdpClientCache", {})
            )
            # gdpClientCache is a JSON-string inside the JSON
            if props:
                cache = json.loads(props)
                listing_data = next(iter(cache.values()), {}).get("property", {})
                if listing_data:
                    return _normalize_zillow(listing_data)
        except (json.JSONDecodeError, StopIteration, AttributeError):
            pass

    # Fallback: scrape visible DOM
    return await _extract_generic(page)


def _normalize_zillow(data: dict) -> dict[str, Any]:
    return {
        "address": data.get("streetAddress", ""),
        "city": data.get("city", ""),
        "state": data.get("state", ""),
        "zip_code": data.get("zipcode", ""),
        "price": data.get("price"),
        "bedrooms": data.get("bedrooms"),
        "bathrooms": data.get("bathrooms"),
        "sqft": data.get("livingArea"),
        "lot_size": data.get("lotSize"),
        "year_built": data.get("yearBuilt"),
        "property_type": data.get("homeType"),
        "description": data.get("description", ""),
        "hoa_fee": data.get("monthlyHoaFee"),
        "tax_annual": data.get("annualHomeownersInsurance"),
        "days_on_market": data.get("daysOnZillow"),
        "zestimate": data.get("zestimate"),
    }


async def _extract_redfin(page: Page) -> dict[str, Any]:
    # Redfin also embeds listing data in __NEXT_DATA__
    raw = await page.evaluate("""() => {
        const el = document.getElementById('__NEXT_DATA__');
        return el ? el.textContent : null;
    }""")

    if raw:
        try:
            next_data = json.loads(raw)
            listing_data = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("initialReduxState", {})
                .get("feed", {})
                .get("propertyV2", {})
            )
            if listing_data:
                return _normalize_redfin(listing_data)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: wait for visible DOM and scrape text
    try:
        await page.wait_for_selector(".HomeInfo", timeout=10_000)
    except Exception:
        pass

    return await _extract_generic(page)


def _normalize_redfin(data: dict) -> dict[str, Any]:
    basic = data.get("basicInfo", {})
    public_record = data.get("publicRecordsInfo", {})
    tax_info = public_record.get("taxInfo", {})
    return {
        "address": basic.get("streetAddress", {}).get("assembledAddress", ""),
        "city": basic.get("city", ""),
        "state": basic.get("stateName", ""),
        "zip_code": basic.get("zip", ""),
        "price": basic.get("listingPrice", {}).get("amount"),
        "bedrooms": basic.get("beds"),
        "bathrooms": basic.get("baths"),
        "sqft": basic.get("sqFt", {}).get("value"),
        "lot_size": basic.get("lotSize", {}).get("value"),
        "year_built": public_record.get("yearBuilt"),
        "property_type": basic.get("propertyType"),
        "description": data.get("remarks", {}).get("listingRemarks", ""),
        "hoa_fee": basic.get("hoaFee", {}).get("amount"),
        "tax_annual": tax_info.get("taxesDue"),
        "days_on_market": basic.get("dom"),
        "redfin_estimate": data.get("avm", {}).get("predictedValue"),
    }


async def _extract_generic(page: Page) -> dict[str, Any]:
    """Best-effort extraction from any listing page via visible text."""
    title = await page.title()
    body_text = await page.inner_text("body")
    return {
        "address": title,
        "raw_text": body_text[:8000],  # truncate for LLM context
    }
