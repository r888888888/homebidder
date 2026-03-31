# HomeBidder: Phased Build Plan

## Context
The app currently accepts a Zillow/Redfin **URL** and returns a basic offer price recommendation. The new goal is to accept a **street address**, research all available property data from multiple free sources, and produce a structured analysis with four sections: **Property Summary**, **Offer Price**, **Risk Analysis**, and **Investment & Growth**. Built in four sequential phases so each phase can be validated independently before proceeding.

The DB schema exists but is unused. The comps, pricing, and agent loop are wired but never persisted. The frontend form, streaming display, and SSE infrastructure work.

---

## Phase 1 — Address Input + Property Research

**Goal:** Replace URL input with a street address form. Research the property using free structured APIs and return a rich Property Summary. Activate DB persistence.

### What changes

**Backend — new tool: `lookup_property_by_address`**
- `backend/agent/tools/property_lookup.py` (new file)
- Accepts `street, city, state, zip_code`
- Two sub-calls, merged into one result dict:
  1. **homeharvest** (`scrape_property(site_name=["realtor.com","redfin"], listing_type="for_sale", location=...)`) — listing details, price, DOM, price history
  2. **RentCast free API** (`GET /properties?address=...`) — property characteristics + AVM when homeharvest misses (unlisted homes)
- Returns: `address, price, bedrooms, bathrooms, sqft, year_built, lot_size, property_type, hoa_fee, days_on_market, price_history[], avm_estimate, source`

**Backend — new tool: `fetch_neighborhood_context`**
- `backend/agent/tools/neighborhood.py` (new file)
- Calls Census ACS API (free, key needed) for the ZCTA matching `zip_code`
- Returns: `median_home_value, owner_occupancy_rate, vacancy_rate, median_year_built, housing_units`
- Uses `httpx` (already in requirements)

**Backend — update `orchestrator.py`**
- Register two new tools (`lookup_property_by_address`, `fetch_neighborhood_context`)
- Remove `scrape_listing` tool (URL-based; no longer the entry point)
- Update system prompt: Step 1 is now `lookup_property_by_address` + `fetch_neighborhood_context`
- Change agent entry: `run_agent(street, city, state, zip_code, buyer_context)` instead of `(listing_url, buyer_context)`

**Backend — update `api/routes.py`**
- Replace `AnalyzeRequest(url, buyer_context)` with `AnalyzeRequest(street, city, state, zip_code, buyer_context)`
- Add a `GET /api/analyses` endpoint (list saved analyses — activate DB)
- Persist `Listing` record on first lookup; persist `Analysis` record when agent completes

**Backend — update `db/models.py`**
- Add `street, city, state, zip_code` columns to `Listing` (currently only stores `url`)
- Add `avm_estimate`, `neighborhood_context` (JSON text) to `Listing`
- Add index on `(street, city, state, zip_code)` for duplicate detection

**Frontend — update `AnalysisForm.tsx`**
- Replace single URL field with four fields: Street Address, City, State, ZIP
- Keep buyer notes textarea
- Add input validation: ZIP must be 5 digits; state 2-letter code

**Frontend — add `PropertySummaryCard.tsx`** (new component)
- Renders structured property data extracted from SSE `tool_result` events
- Fields: address, price, beds/baths/sqft, year built, lot size, property type, DOM, AVM vs. list price delta, neighborhood stats panel

**Frontend — update `AnalysisStream.tsx`**
- Parse tool results from SSE stream (currently only `tool_call` events are shown; add `tool_result` parsing)
- Render `PropertySummaryCard` when `lookup_property_by_address` result arrives

### Validation
1. Enter `123 Main St, Austin, TX, 78701` → property card renders with structured fields
2. `GET /api/analyses` returns the saved record
3. Re-submitting the same address hits DB cache (no re-scrape)
4. AVM vs. list price delta shows correctly (or "unlisted" if not on market)

---

## Phase 2 — Comps + Offer Price Recommendation

**Goal:** Fetch recent sold comps, run statistical analysis, and produce a structured offer recommendation. Save comps + analysis to DB.

### What changes

**Backend — `comps.py`** (already built, minor updates)
- Add `distance_miles` calculation: use haversine formula between geocoded subject address and each comp address
- Improve filtering: add sqft similarity filter (±25% of subject sqft) in addition to bedroom count

**Backend — `pricing.py`** (already built, update)
- Actually use `buyer_context` string: parse keywords ("multiple offers", "fast close", "below asking") and adjust posture thresholds accordingly
- Add `market_velocity` input: if DOM < 10 → hot market → push offer high; DOM > 60 → slow → push offer low

**Backend — `orchestrator.py`**
- Add `fetch_comps` and `analyze_market` and `recommend_offer` tools back (they were removed in Phase 1 refactor — keep them)
- Update system prompt to include Step 2: fetch comps, Step 3: analyze + recommend
- Emit a `tool_result` SSE event for `recommend_offer` output (currently only `tool_call` is emitted)
- Persist `Comp` records and finalize `Analysis` record with `offer_low/recommended/high`, `rationale`, `market_summary`

**Frontend — add `OfferRecommendationCard.tsx`** (new component)
- Renders when `recommend_offer` tool result arrives in SSE stream
- Shows: offer range (low / recommended / high) as a visual range slider display
- Shows: comp table (address, sold price, sqft, $/sqft, sold date, distance)
- Shows: posture badge (Competitive / At-Market / Negotiating) with color coding

**Frontend — update `AnalysisStream.tsx`**
- Render `OfferRecommendationCard` when `recommend_offer` result arrives

### Validation
1. Full flow: address → property lookup → comps → offer range renders in UI
2. Comps table shows distance_miles populated
3. `GET /api/analyses/{id}` returns saved analysis with comps array
4. Buyer context "multiple offers expected" → posture shifts to Competitive

---

## Phase 3 — Risk Analysis

**Goal:** Add a data-backed risk assessment with a risk level (Low / Medium / High) and specific risk factors.

### What changes

**Backend — new tool: `fetch_market_trends`**
- `backend/agent/tools/market_trends.py` (new file)
- Downloads Redfin Data Center zip-level TSV (free, no auth): `https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/zip_code_market_tracker.tsv000.gz`
- Filters to `zip_code`, returns last 6 months of: `median_sale_price`, `homes_sold`, `median_dom`, `price_drops`, `months_of_supply`
- Cache the TSV download in `/tmp` for 24h to avoid repeated downloads

**Backend — new tool: `fetch_fhfa_hpi`**
- `backend/agent/tools/fhfa.py` (new file)
- Fetches FHFA ZIP-level HPI CSV: `https://www.fhfa.gov/hpi/download/...` (annual, free)
- Returns: `yoy_change_pct`, `3yr_change_pct`, `hpi_trend` (appreciating/depreciating/flat)

**Backend — new tool: `assess_risk`**
- `backend/agent/tools/risk.py` (new file)
- Pure Python function (no I/O) — Claude calls it after all data is gathered
- Inputs: `property`, `comps_stats`, `market_trends`, `hpi_data`
- Computes weighted risk score from:
  - **Price risk** (spread vs. comps — if list > 10% above comps fair value → High)
  - **Market velocity** (months_of_supply > 4 → buyer's market → Lower risk; < 2 → seller's market → Higher)
  - **DOM** (> 60 days → possible issues → Medium/High)
  - **Price drops** (any price drops on listing → negotiating signal)
  - **Home age** (year_built < 1970 → higher repair risk → adds Medium factor)
  - **HPI trend** (negative YoY → adds risk)
- Returns: `risk_level` (Low/Medium/High), `risk_factors: list[{factor, severity, detail}]`

**Backend — update `orchestrator.py`** system prompt
- Add Step 4: fetch market trends, fetch FHFA HPI, assess risk

**Frontend — add `RiskAnalysisCard.tsx`** (new component)
- Risk level badge with color (green/yellow/red)
- Bullet list of risk factors with severity icons
- "What this means for your offer" short paragraph (from Claude's text output)

### Validation
1. Risk level renders with at least 3 factors
2. High-priced listing above comps → shows "Price Risk" factor
3. Older home (pre-1970) → shows "Age/Repair Risk" factor
4. Market trend data visible (months of supply, median DOM)
5. FHFA YoY change cited in risk rationale

---

## Phase 4 — Investment & Growth Analysis + Full Persistence

**Goal:** Add investment metrics (gross yield, price-to-rent ratio, appreciation projections). Complete DB persistence. Add analysis history to the UI.

### What changes

**Backend — new tool: `fetch_rental_estimate`**
- `backend/agent/tools/rentcast.py` (new file)
- Calls `GET https://api.rentcast.io/v1/avm/rent/long-term?address=...` (50 free calls/month)
- Returns: `rent_estimate`, `rent_low`, `rent_high`, `confidence`
- Falls back to: `median_rent` from Census ACS `B25064` table if RentCast quota exhausted

**Backend — new tool: `compute_investment_metrics`**
- `backend/agent/tools/investment.py` (new file)
- Pure Python — no I/O
- Inputs: `property` (price), `rental_estimate`, `hpi_trend` (from Phase 3)
- Computes:
  - `gross_yield_pct` = (annual_rent / price) × 100
  - `price_to_rent_ratio` = price / (monthly_rent × 12)
  - `monthly_cashflow_estimate` = rent - (mortgage_payment + tax_monthly + hoa + 10% vacancy + 10% maintenance)
    - Mortgage assumes 20% down, 30yr fixed at current 10yr treasury + 2.5% spread (hardcoded, noted as estimate)
  - `projected_value_1yr/3yr/5yr` based on FHFA HPI YoY trend compounded
  - `investment_rating`: Buy / Hold / Overpriced (based on gross yield vs. local median)
- Returns all metrics above

**Backend — `orchestrator.py`**
- Add Step 5: fetch rental estimate, compute investment metrics
- On agent completion (`stop_reason == "end_turn"`): write full analysis to DB
  - `Listing` upsert (by address)
  - `Analysis` insert with all fields
  - `Comp` bulk insert
- Emit `{"type": "analysis_id", "id": ...}` as final SSE event so frontend can link to saved record

**Backend — `api/routes.py`**
- Add `GET /api/analyses` — list last 20 analyses (newest first)
- Add `GET /api/analyses/{id}` — full analysis record with comps

**Frontend — add `InvestmentCard.tsx`** (new component)
- Investment rating badge
- Metrics grid: Gross Yield, Price-to-Rent Ratio, Monthly Cashflow Estimate
- Appreciation table: projected value in 1yr / 3yr / 5yr with FHFA trend assumption shown
- Disclaimer: "Based on FHFA HPI historical trend and RentCast estimate — not financial advice"

**Frontend — add `AnalysisHistory.tsx`** (new component/route)
- New route `/history` listing past analyses
- Each row: address, date, offer_recommended, risk_level, investment_rating
- Click → re-renders full analysis from saved DB record (no re-scrape)

**Frontend — update `AnalysisStream.tsx`**
- Render `InvestmentCard` when `compute_investment_metrics` result arrives
- On `analysis_id` SSE event: show "Saved — view history" link

### Validation
1. Gross yield and P/R ratio compute correctly for known property
2. 5-year projection uses FHFA trend (not fabricated)
3. `/history` route shows list of past analyses
4. Click saved analysis → all 4 sections render from DB (no live scraping)
5. RentCast quota exhausted → Census ACS fallback kicks in gracefully

---

## Files Modified Per Phase (Summary)

| File | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| `backend/agent/tools/property_lookup.py` | NEW | | | |
| `backend/agent/tools/neighborhood.py` | NEW | | | |
| `backend/agent/tools/market_trends.py` | | | NEW | |
| `backend/agent/tools/fhfa.py` | | | NEW | |
| `backend/agent/tools/risk.py` | | | NEW | |
| `backend/agent/tools/rentcast.py` | | | | NEW |
| `backend/agent/tools/investment.py` | | | | NEW |
| `backend/agent/tools/comps.py` | | UPDATE | | |
| `backend/agent/tools/pricing.py` | | UPDATE | | |
| `backend/agent/orchestrator.py` | UPDATE | UPDATE | UPDATE | UPDATE |
| `backend/api/routes.py` | UPDATE | | | UPDATE |
| `backend/db/models.py` | UPDATE | | | |
| `frontend/app/components/AnalysisForm.tsx` | UPDATE | | | |
| `frontend/app/components/AnalysisStream.tsx` | UPDATE | UPDATE | UPDATE | UPDATE |
| `frontend/app/components/PropertySummaryCard.tsx` | NEW | | | |
| `frontend/app/components/OfferRecommendationCard.tsx` | | NEW | | |
| `frontend/app/components/RiskAnalysisCard.tsx` | | | NEW | |
| `frontend/app/components/InvestmentCard.tsx` | | | | NEW |
| `frontend/app/routes/history.tsx` | | | | NEW |

---

## External APIs Used (all free)

| API | Phase | Auth | Limit |
|---|---|---|---|
| homeharvest (Realtor.com/Redfin) | P1 | None | ToS risk — use carefully |
| RentCast | P1, P4 | Free API key | 50 calls/month free |
| Census ACS | P1, P4 fallback | Free API key | No hard limit |
| Redfin Data Center TSV | P3 | None | Download file; cache 24h |
| FHFA HPI ZIP CSV | P3 | None | Download file; cache 24h |

`.env.example` will need: `RENTCAST_API_KEY`, `CENSUS_API_KEY`
