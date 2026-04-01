# HomeBidder: Phased Build Plan

## Context
The app currently accepts a Zillow/Redfin **URL** and returns a basic offer price recommendation. The new goal is to accept a **street address**, research all available property data from multiple free sources, and produce a structured analysis with four sections: **Property Summary**, **Offer Price**, **Risk Analysis**, and **Investment & Growth**. Built in nine sequential phases so each phase can be validated independently before proceeding.

**Primary target market: SF Bay Area** (San Francisco, Alameda, Santa Clara, San Mateo, Contra Costa, Marin counties). The plan accommodates other metros but Bay Area-specific data sources, market dynamics, and risk factors are first-class.

The DB schema exists but is unused. The comps, pricing, and agent loop are wired but never persisted. The frontend form, streaming display, and SSE infrastructure work.

---

## SF Bay Area Market Context

Key dynamics that shape all phases:

- **Offers routinely go 10–30%+ over asking** in competitive neighborhoods; comp-based value matters more than list price
- **Offer review dates** are the norm: sellers set a date, collect all offers, respond once — the app must detect this and advise accordingly
- **Clean offers win**: buyers routinely waive appraisal and loan contingencies; the app should flag when this is expected
- **Disclosure packages** (NHD, TDS, SPQ, Statewide Buyer and Seller Advisory) are shared before offers; natural hazard flags are often already disclosed
- **Prop 13 tax shock**: California property taxes are re-assessed at purchase price, not market value; a property with a Prop 13 basis of $200K assessed on a $2M sale means the buyer faces a 10× tax increase — this is a critical cost and risk factor
- **Micro-market pricing**: SF neighborhoods (Noe Valley vs. Sunset vs. Bayview) and East Bay cities (Piedmont vs. Oakland flatlands) can differ by 50–100% in $/sqft within a 3-mile radius — comp radius must be tight
- **Earthquake, fire, and flood exposure** is legally disclosed in every CA transaction and directly impacts insurability, lender requirements, and resale value

---

## Phase 1 — Address Input + DB Schema

**Goal:** Replace the URL input with a single address string. Wire the API route and DB model to accept it. No agent changes yet — this phase only establishes the data contract that all later phases build on.

### What changes

**Backend — update `api/routes.py`**
- Replace `AnalyzeRequest(url, buyer_context)` with `AnalyzeRequest(address, buyer_context)` — single free-text string
- No geocoding here; pass `address` straight through to the agent for now

**Backend — update `db/models.py`**
- Replace `url` column on `Listing` with:
  - `address_input` — raw string as entered by the user
  - `address_matched` — Census geocoder normalized form (populated in Phase 2)
  - `latitude`, `longitude`, `county`, `state`, `zip_code` (populated in Phase 2)
- Add `avm_estimate` (float), `neighborhood_context` (JSON text) columns
- Add `prop13_assessed_value` (float), `prop13_base_year` (int), `prop13_annual_tax` (float)
- Add unique index on `address_matched` for cache lookups (nullable until Phase 2 populates it)

**Frontend — update `AnalysisForm.tsx`**
- Replace URL field with a single **Address** text input (placeholder: "450 Sanchez St, San Francisco, CA 94114")
- No client-side address parsing or ZIP/state validation — submit raw string as-is
- Keep buyer notes textarea

### Validation
1. Form renders with single address field
2. Submitting an address POSTs `{address, buyer_context}` to the API (no 422 validation error)
3. DB migration runs cleanly; `Listing` table has the new columns

---

## Phase 2 — Property Lookup Tool

**Goal:** Implement `lookup_property_by_address` — geocode the address, scrape listing data, and render a basic property card. First end-to-end flow from address to structured output.

### What changes

**Backend — new tool: `lookup_property_by_address`**
- `backend/agent/tools/property_lookup.py` (new file)
- Step 1: **geocode** via Census Geocoder API (`geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=...&benchmark=Public_AR_Current&format=json`) — free, no key. Returns `matched_address`, `latitude`, `longitude`, `county`, `state`, `zip_code`.
- Step 2: two data sub-calls merged into one result dict:
  1. **homeharvest** (`scrape_property(site_name=["realtor.com","redfin"], listing_type="for_sale", location=matched_address)`) — price, DOM, price history, beds/baths/sqft, year built, lot size, HOA fee
  2. **RentCast** (`GET /properties?address=matched_address`) — AVM and property characteristics when homeharvest misses (unlisted homes)
- Returns: `address` (matched), `latitude`, `longitude`, `county`, `state`, `zip_code`, `price`, `bedrooms`, `bathrooms`, `sqft`, `year_built`, `lot_size`, `property_type`, `hoa_fee`, `days_on_market`, `price_history[]`, `avm_estimate`, `source`
- Write `address_matched`, `latitude`, `longitude`, `county`, `state`, `zip_code` back to the `Listing` DB record

**Backend — update `orchestrator.py`**
- Register `lookup_property_by_address` tool
- Remove `scrape_listing` tool (URL-based entry point is gone)
- Update agent entry: `run_agent(address, buyer_context)`
- System prompt Step 1: call `lookup_property_by_address`

**Frontend — add `PropertySummaryCard.tsx`** (new component, core fields only)
- Renders when the `lookup_property_by_address` tool result arrives in the SSE stream
- Fields: matched address, price, beds/baths/sqft, year built, lot size, property type, DOM, AVM vs. list price delta (or "not listed" if no list price)

**Frontend — update `AnalysisStream.tsx`**
- Add `tool_result` SSE event parsing (currently only `tool_call` events are shown)
- Render `PropertySummaryCard` when `lookup_property_by_address` result arrives

### Validation
1. Enter `450 Sanchez St, San Francisco, CA 94114` → geocoder normalizes, property card renders with structured fields
2. `address_matched`, `latitude`, `longitude` are written to the `Listing` DB record
3. Re-submitting the same address hits DB cache (no re-scrape)
4. Unlisted address → AVM shown from RentCast; "not listed" for list price

---

## Phase 3 — Neighborhood Context & Prop 13

**Goal:** Add the `fetch_neighborhood_context` tool to pull county assessor data (Prop 13 assessed value) and Census ACS neighborhood stats. Extend `PropertySummaryCard` with a Prop 13 tax impact panel.

### What changes

**Backend — new tool: `fetch_neighborhood_context`**
- `backend/agent/tools/neighborhood.py` (new file)
- Uses `county`, `state`, `zip_code`, `address_matched` from the Phase 2 geocoder result
- **Primary path — Bay Area county assessors:**
  - **San Francisco** (`county == "San Francisco"`): DataSF Assessor-Recorder API (`data.sfgov.org/resource/wv5m-vpq2.json`) — returns `assessedland`, `assessedimpr`, `yrbuilt`
  - **Alameda County**: ArcGIS REST query on `data.acgov.org` parcel layer
  - **Santa Clara County**: `sccassessor.org` open data endpoint
  - **San Mateo, Contra Costa, Marin**: skip to fallback
- **Fallback path** (all other counties): Census ACS API (`CENSUS_API_KEY`) for the ZCTA matching `zip_code` — tables `B25077` (median home value), `B25001` (housing units), `B25004` (vacancy), `B25035` (median year built)
- Returns: `median_home_value`, `owner_occupancy_rate`, `vacancy_rate`, `median_year_built`, `housing_units`, `prop13_assessed_value`, `prop13_base_year`, `prop13_annual_tax` (null if county not supported)
- Persist `prop13_assessed_value`, `prop13_base_year`, `prop13_annual_tax`, `neighborhood_context` to `Listing`

**Backend — update `orchestrator.py`**
- Register `fetch_neighborhood_context` tool
- System prompt: after `lookup_property_by_address`, call `fetch_neighborhood_context`
- Compute and surface `buyer_annual_tax_estimate` = purchase_price × 1.25% (CA effective rate)

**Frontend — update `PropertySummaryCard.tsx`**
- Add neighborhood stats panel: median home value, owner-occupancy rate, vacancy rate
- **Prop 13 Tax Impact panel** (shown when `prop13_assessed_value` is non-null):
  - Seller's estimated annual tax (based on Prop 13 assessed value)
  - Buyer's estimated annual tax (based on purchase price × 1.25%)
  - Delta flagged in amber/red if increase > $5K/yr

### Validation
1. SF address → Prop 13 panel shows seller's tax vs. buyer's estimated tax at purchase price
2. Non-Bay-Area address → panel absent; Census ACS neighborhood stats shown instead
3. `prop13_assessed_value` written to `Listing` DB record

---

## Phase 4 — Comps

**Goal:** Fetch recent sold comps with Bay Area-tuned radius and surface them in the UI. No offer calculation yet — just the data layer.

### What changes

**Backend — update `comps.py`**
- Add `distance_miles` calculation: haversine formula between subject `latitude/longitude` and each comp's coordinates
- **Bay Area adaptive radius**: 0.3 miles for dense SF/Oakland ZIPs; 0.75 miles for suburbs; 1.5 miles for low-density. Use a hardcoded ZIP density lookup for Bay Area ZIPs; default to 1.0 miles outside Bay Area.
- Add sqft similarity filter: ±25% of subject sqft in addition to bedroom count
- Add `pct_over_asking` on each comp: `(sold_price - list_price) / list_price × 100` — the primary Bay Area market signal (null if list price unknown)
- Source prioritization: Bay Area county assessor sale records (when available from Phase 3 data) > homeharvest Redfin/Realtor.com

**Backend — update `orchestrator.py`**
- Register `fetch_comps` tool
- System prompt: after neighborhood context, call `fetch_comps`
- Emit `tool_result` SSE event for `fetch_comps` output

**Frontend — add `OfferRecommendationCard.tsx`** (partial — comp table only for now)
- Renders when `fetch_comps` tool result arrives
- Comp table: address, sold price, sqft, $/sqft, sold date, distance, % over asking
- No offer range yet (added in Phase 5)

**Frontend — update `AnalysisStream.tsx`**
- Render `OfferRecommendationCard` when `fetch_comps` result arrives

### Validation
1. SF address → comps table renders with `pct_over_asking` column populated
2. Dense SF ZIP (e.g. 94110) → 0.3 mile radius used; South Bay suburb → 0.75 mile radius
3. Sqft filter active: comps within ±25% of subject sqft

---

## Phase 5 — Offer Recommendation

**Goal:** Add pricing logic and produce a structured offer recommendation. Complete the `OfferRecommendationCard` with Bay Area-specific offer strategy output.

### What changes

**Backend — update `pricing.py`**
- Parse `buyer_context` string for keywords: "multiple offers" / "fast close" / "below asking" → adjust posture thresholds
- Add `market_velocity` input: DOM < 7 → offer review period likely → hot posture; DOM > 45 → slow → negotiating posture
- Add land-aware market statistics from comps: `median_lot_size` and `median_comp_sqft`
- Replace `ppsf * subject_sqft` as primary fair-value method with a **median-comp anchored hybrid**:
  - Anchor fair value to `median_sale_price`
  - Apply bounded lot-size adjustment (higher weight) and bounded sqft adjustment (lower weight)
  - Apply a light RentCast AVM blend when available to stabilize sparse/noisy comp sets
  - Keep `ppsf * sqft` only as fallback when comp median is unavailable
- Return `fair_value_breakdown` in `recommend_offer` output so UI can explain the estimate:
  - method (`median_comp_anchor` / `ppsf_fallback` / `list_price_fallback`)
  - lot and sqft adjustment percentages
  - AVM blend usage flag
- Replace fixed ±3% competitive range with dynamic uncertainty band (`offer_range_band_pct`):
  - starts at 3%
  - widens with higher comp price dispersion (`price_stdev / median_sale_price`)
  - widens when comp count is low; tightens when comp count is high
  - bounded to a safe interval (2% to 6%)
- Use `median_pct_over_asking` as an **aggression signal** within that band (positioning recommendation toward upper bound), not as a direct multiplier on fair value
- **Bay Area offer strategy:**
  - If median `pct_over_asking` across comps > 5%: posture = Competitive; `recommended_offer` is pushed toward the upper uncertainty band (not full overbid multiplication)
  - Offer review date detection: if DOM ≤ 7 and listed on Tue/Wed → advisory "Seller likely reviewing offers [day+5]; submit by [date]"
  - `contingency_recommendation`: `waive_appraisal` when market is > 10% over asking; `waive_loan` when buyer has strong pre-approval; always `keep_inspection` unless buyer is flagged as investor in `buyer_context`

**Backend — update `orchestrator.py`**
- Register `recommend_offer` tool
- System prompt Step 3: after comps, call `recommend_offer`
- Emit `tool_result` SSE event for `recommend_offer`
- Persist `Comp` records and write `offer_low`, `offer_recommended`, `offer_high`, `rationale`, `market_summary` to `Analysis`

**Frontend — complete `OfferRecommendationCard.tsx`**
- Offer range display: low / recommended / high as a visual range bar
- Posture badge: Competitive / At-Market / Negotiating with color coding
- Contingency recommendation panel: which to waive/keep with one-line rationale
- Offer review date advisory (if detected)

### Validation
1. Full flow: address → property → comps → offer range renders
2. Buyer context "multiple offers expected" → Competitive posture; appraisal waiver suggested
3. DOM ≤ 7 → offer review date advisory shown
4. `GET /api/analyses/{id}` returns saved analysis with comps array

---

## Phase 6 — Market Trends & CA Hazard Zones

**Goal:** Add two independent data-gathering tools that feed Phase 7's risk scoring. No new UI yet — just the tools and orchestrator wiring.

### What changes

**Backend — new tool: `fetch_market_trends`**
- `backend/agent/tools/market_trends.py` (new file)
- Downloads Redfin Data Center ZIP-level TSV (free, no auth): `https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/zip_code_market_tracker.tsv000.gz`
- Filters to subject `zip_code`, returns last 6 months of: `median_sale_price`, `homes_sold`, `median_dom`, `price_drops`, `months_of_supply`, `pct_homes_sold_above_list`
- Cache downloaded file in `/tmp/redfin_market.tsv.gz` for 24h

**Backend — new tool: `fetch_fhfa_hpi`**
- `backend/agent/tools/fhfa.py` (new file)
- Downloads FHFA ZIP-level HPI CSV (free, no auth, annual release)
- Returns: `yoy_change_pct`, `3yr_change_pct`, `hpi_trend` (appreciating/depreciating/flat)
- Cache in `/tmp/fhfa_hpi.csv` for 7 days

**Backend — new tool: `fetch_ca_hazard_zones`**
- `backend/agent/tools/ca_hazards.py` (new file)
- Shapefiles downloaded once to `backend/data/` at setup time (commit to repo):
  - CGS Alquist-Priolo Fault Zones (GeoJSON from `maps.conservation.ca.gov`)
  - CGS Seismic Hazard Zones — liquefaction layer (GeoJSON)
  - CalFire FHSZ (GeoJSON from `gis.data.cnra.ca.gov`)
- Load all three with `shapely` at app startup (not per-request)
- At query time: `point.within(polygon)` checks using `latitude, longitude`
- Flood zone: live API call to FEMA Flood Map Service (`msc.fema.gov/arcgis/rest/services/`) — point query, returns `FLD_ZONE`
- Returns: `alquist_priolo: bool`, `liquefaction_risk: Low/Moderate/High`, `fire_hazard_zone: Very High/High/Moderate/None`, `flood_zone: str`

**Backend — update `orchestrator.py`**
- Register `fetch_market_trends`, `fetch_fhfa_hpi`, `fetch_ca_hazard_zones` tools
- System prompt Step 4: call all three in parallel before `assess_risk`

### Validation
1. `fetch_market_trends` returns 6 months of data for a Bay Area ZIP
2. `fetch_fhfa_hpi` returns YoY change for a Bay Area ZIP
3. Marina District SF (lat/lon in liquefaction zone) → `liquefaction_risk: High`
4. Oakland Hills address → `fire_hazard_zone: Very High`
5. Bayfront address → `flood_zone: AE`
6. Redfin TSV is cached; second call within 24h doesn't re-download

---

## Phase 7 — Risk Assessment

**Goal:** Combine all gathered data into a weighted risk score and render a `RiskAnalysisCard`.

### What changes

**Backend — new tool: `assess_risk`**
- `backend/agent/tools/risk.py` (new file)
- Pure Python, no I/O — called after all Phase 6 tools complete
- Inputs: `property`, `comps_stats`, `market_trends`, `hpi_data`, `ca_hazard_zones`, `prop13_data`
- Risk factors and weights:
  - **Price risk**: offer > 10% above comp fair value → High
  - **Market velocity**: `months_of_supply` > 4 → lower risk; < 2 → higher
  - **Stale listing**: DOM > 60 → Medium/High (investigate price drops)
  - **Price drops**: any drops on subject listing → negotiating signal
  - **Home age**: year_built < 1970 → Medium repair risk; pre-1940 → High
  - **HPI trend**: negative YoY → adds risk
  - **Alquist-Priolo**: `True` → High (may affect financing/insurance)
  - **Fire zone**: Very High or High → insurance availability risk (State Farm/Allstate CA exit)
  - **Flood zone**: A/AE/AO/VE → required flood insurance (~$1–3K/yr carrying cost)
  - **Liquefaction**: High → elevated earthquake damage risk
  - **Prop 13 tax shock**: buyer tax > seller tax × 3 → flag significant increase
- Returns: `risk_level: Low/Medium/High`, `risk_factors: [{factor, severity, detail}]`

**Backend — update `orchestrator.py`**
- Register `assess_risk` tool
- System prompt Step 5: call `assess_risk` after all Phase 6 tools; emit `tool_result` SSE event

**Frontend — add `RiskAnalysisCard.tsx`** (new component)
- Risk level badge: green (Low) / yellow (Medium) / red (High)
- Bullet list of risk factors with severity icons
- Bay Area hazard row: four badges — Earthquake Zone / Liquefaction / Fire Zone / Flood Zone — each with color and one-line implication
- Fire insurance note when `fire_hazard_zone == Very High` (mention CA FAIR Plan)
- "What this means for your offer" paragraph (from Claude's text output)

**Frontend — update `AnalysisStream.tsx`**
- Render `RiskAnalysisCard` when `assess_risk` result arrives

### Validation
1. Risk card renders with ≥ 3 factors for any Bay Area address
2. Marina District → Liquefaction badge shown
3. Oakland Hills → Fire Zone: Very High + insurance note shown
4. Pre-1940 home → "Age/Repair Risk: High" factor
5. FHFA YoY negative → HPI risk factor included

---

## Phase 8 — Investment Analysis

**Goal:** Add rental estimate, Bay Area value drivers (ADU, rent control, transit), and compute investment metrics. Render `InvestmentCard`.

### What changes

**Backend — new tool: `fetch_mortgage_rates`**
- `backend/agent/tools/mortgage_rates.py` (new file)
- Calls FRED API (St. Louis Fed): `GET https://api.stlouisfed.org/fred/series/observations?series_id=MORTGAGE30US&sort_order=desc&limit=1&file_type=json&api_key=FRED_API_KEY`
- Also fetches `MORTGAGE15US` (15-year fixed) in the same call batch
- Returns: `rate_30yr_fixed: float`, `rate_15yr_fixed: float`, `as_of_date: str`, `source: "Freddie Mac PMMS via FRED"`
- Cache result in memory for 24h (rates update weekly on Thursdays — no need to hit the API per request)

**Backend — new tool: `fetch_rental_estimate`**
- `backend/agent/tools/rentcast.py` (new file)
- Primary: `GET https://api.rentcast.io/v1/avm/rent/long-term?address=matched_address` (`RENTCAST_API_KEY`)
- Fallback (quota exhausted): Census ACS `B25064` median gross rent for ZCTA
- Returns: `rent_estimate`, `rent_low`, `rent_high`, `confidence`, `source`

**Backend — new tool: `fetch_ba_value_drivers`**
- `backend/agent/tools/ba_value_drivers.py` (new file)
- Three sub-checks (all use data already in memory from prior phases):
  1. **ADU potential**: `lot_size ≥ 3000 sqft AND property_type == SFR` → `adu_potential: True`; `adu_rent_estimate` = ZIP median rent × 0.65
  2. **Rent control**: hardcoded city/vintage lookup — SF (pre-1979), Oakland (most rentals), Berkeley (pre-1980), Mountain View, East Palo Alto, Hayward, San Jose (pre-9/7/79). Returns `rent_controlled: bool`, `rent_control_city: str`, `implications: str`
  3. **Transit proximity**: fetch BART stations once via `api.bart.gov/api/stn.aspx?cmd=stns&json=y` (`BART_API_KEY`); haversine to nearest station. Caltrain stops hardcoded in `backend/data/caltrain_stations.json`. Returns `nearest_bart_station`, `bart_distance_miles`, `transit_premium_likely` (≤ 0.5 miles = walkshed)

**Backend — new tool: `compute_investment_metrics`**
- `backend/agent/tools/investment.py` (new file)
- Pure Python, no I/O
- Inputs: `property`, `rental_estimate`, `mortgage_rates`, `hpi_trend`, `ba_value_drivers`, `prop13_annual_tax`
- Computes:
  - `gross_yield_pct` = (annual_rent / price) × 100
  - `price_to_rent_ratio` = price / (monthly_rent × 12)
  - `monthly_cashflow_estimate` = rent − (mortgage + `prop13_annual_tax`/12 + hoa + 10% vacancy + 10% maintenance). Mortgage: 20% down, 30yr fixed using `mortgage_rates.rate_30yr_fixed` from FRED (live rate, not hardcoded). Surface `rate_30yr_fixed` and `as_of_date` in the UI so the buyer knows what rate was assumed.
  - `adu_gross_yield_boost_pct`: recomputed yield including `adu_rent_estimate` if `adu_potential == True`
  - `projected_value_1yr/3yr/5yr`: FHFA HPI YoY compounded
  - `investment_rating`: Buy (≥ 3.5%) / Hold (2.5–3.5%) / Overpriced (< 2.5%) — Bay Area-calibrated thresholds

**Backend — update `orchestrator.py`**
- Register `fetch_mortgage_rates`, `fetch_rental_estimate`, `fetch_ba_value_drivers`, `compute_investment_metrics`
- System prompt Step 6: fetch mortgage rates + rental estimate + BA drivers (all parallel), then compute metrics

**Frontend — add `InvestmentCard.tsx`** (new component)
- Investment rating badge
- Metrics grid: Gross Yield, Price-to-Rent Ratio, Monthly Cashflow
- Mortgage rate assumption line: "Assumes X.XX% 30yr fixed (Freddie Mac PMMS, week of [date])"
- Appreciation table: 1yr / 3yr / 5yr projected values with FHFA assumption noted
- ADU panel (if `adu_potential`): estimated ADU rent + boosted gross yield
- Rent control badge (if `rent_controlled`): ordinance name + implications
- Transit badge: nearest BART/Caltrain station + distance; "transit premium likely" if in walkshed
- Disclaimer: "Based on FHFA HPI trend and RentCast estimate — not financial advice"

**Frontend — update `AnalysisStream.tsx`**
- Render `InvestmentCard` when `compute_investment_metrics` result arrives

### Validation
1. SF SFR with lot ≥ 3000 sqft → ADU potential shown; boosted yield displayed
2. Pre-1979 SF flat → Rent Control: SF Rent Ordinance badge shown
3. Address within 0.5 miles of 16th St Mission BART → transit premium badge
4. `prop13_annual_tax` (not estimated rate) used in cashflow calc
5. Live FRED rate used in mortgage payment — not hardcoded; `as_of_date` shown in UI
6. Gross yield thresholds use Bay Area norms (3.5% / 2.5% breakpoints)

---

## Phase 9 — Analysis History + Full Persistence

**Goal:** Complete DB persistence on agent completion. Add `/history` route so past analyses can be retrieved without re-scraping.

### What changes

**Backend — update `orchestrator.py`**
- On `stop_reason == "end_turn"`: write full analysis to DB
  - `Listing` upsert by `address_matched`
  - `Analysis` insert with all fields populated from prior phases
  - `Comp` bulk insert
- Emit `{"type": "analysis_id", "id": ...}` as final SSE event

**Backend — update `api/routes.py`**
- `GET /api/analyses` — list last 20 analyses, newest first (address, date, offer_recommended, risk_level, investment_rating)
- `GET /api/analyses/{id}` — full record with comps array

**Frontend — add `AnalysisHistory.tsx`** (new component/route)
- New route `/history`
- Table: address, date, offer recommended, risk level, investment rating
- Click row → re-render all four cards from saved DB record (no live scraping)

**Frontend — update `AnalysisStream.tsx`**
- On `analysis_id` SSE event: show "Saved — view history" link

### Validation
1. Completing a full analysis → `analysis_id` SSE event received; "Saved" link shown
2. `GET /api/analyses` lists the saved record
3. `GET /api/analyses/{id}` returns full analysis with comps
4. `/history` route renders; clicking a row re-renders all four cards from DB
5. Re-submitting same address → cache hit; existing `Listing` upserted, new `Analysis` created

---

## Files Modified Per Phase (Summary)

| File | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 |
|---|---|---|---|---|---|---|---|---|---|
| `backend/agent/tools/property_lookup.py` | | NEW | | | | | | | |
| `backend/agent/tools/neighborhood.py` | | | NEW | | | | | | |
| `backend/agent/tools/market_trends.py` | | | | | | NEW | | | |
| `backend/agent/tools/fhfa.py` | | | | | | NEW | | | |
| `backend/agent/tools/ca_hazards.py` | | | | | | NEW | | | |
| `backend/agent/tools/risk.py` | | | | | | | NEW | | |
| `backend/agent/tools/mortgage_rates.py` | | | | | | | | NEW | |
| `backend/agent/tools/rentcast.py` | | | | | | | | NEW | |
| `backend/agent/tools/ba_value_drivers.py` | | | | | | | | NEW | |
| `backend/agent/tools/investment.py` | | | | | | | | NEW | |
| `backend/agent/tools/comps.py` | | | | UPDATE | | | | | |
| `backend/agent/tools/pricing.py` | | | | | UPDATE | | | | |
| `backend/agent/orchestrator.py` | | UPDATE | UPDATE | UPDATE | UPDATE | UPDATE | UPDATE | UPDATE | UPDATE |
| `backend/api/routes.py` | UPDATE | | | | | | | | UPDATE |
| `backend/db/models.py` | UPDATE | UPDATE | UPDATE | | | | | | |
| `backend/data/caltrain_stations.json` | | | | | | | | NEW | |
| `frontend/app/components/AnalysisForm.tsx` | UPDATE | | | | | | | | |
| `frontend/app/components/AnalysisStream.tsx` | | UPDATE | | UPDATE | | | UPDATE | UPDATE | UPDATE |
| `frontend/app/components/PropertySummaryCard.tsx` | | NEW | UPDATE | | | | | | |
| `frontend/app/components/OfferRecommendationCard.tsx` | | | | NEW | UPDATE | | | | |
| `frontend/app/components/RiskAnalysisCard.tsx` | | | | | | | NEW | | |
| `frontend/app/components/InvestmentCard.tsx` | | | | | | | | NEW | |
| `frontend/app/routes/history.tsx` | | | | | | | | | NEW |

---

## External APIs Used

| API | Phase | Auth | Limit | Notes |
|---|---|---|---|---|
| Census Geocoder | P2 | None | No hard limit | Address normalization |
| homeharvest (Realtor.com/Redfin) | P2 | None | ToS risk | Primary listing + comp source |
| RentCast (property lookup) | P2 | Free API key | 50 calls/month free | AVM for unlisted homes |
| DataSF Assessor-Recorder API | P3 | None | No hard limit | SF Prop 13 assessed value |
| Alameda County Open Data | P3 | None | No hard limit | East Bay assessor parcel data |
| Santa Clara County Assessor | P3 | None | No hard limit | South Bay assessor parcel data |
| Census ACS | P3 fallback | Free API key | No hard limit | Neighborhood demographics |
| Redfin Data Center TSV | P6 | None | Download; cache 24h | Market trends + % sold above list |
| FHFA HPI ZIP CSV | P6 | None | Download; cache 7d | YoY price index |
| CGS shapefiles (fault + liquefaction) | P6 | None | Static download | Earthquake hazard zones |
| CalFire FHSZ shapefile | P6 | None | Static download | Fire hazard zones |
| FEMA Flood Map Service API | P6 | None | No hard limit | NFIP flood zone per point |
| FRED API (Freddie Mac PMMS) | P8 | Free API key | No hard limit | 30yr/15yr fixed rates; cache 24h |
| RentCast (rent estimate) | P8 | Free API key | 50 calls/month free | Rental AVM |
| BART Open API | P8 | Free API key | No hard limit | Station proximity scoring |

`.env` needs: `RENTCAST_API_KEY`, `CENSUS_API_KEY`, `BART_API_KEY`, `FRED_API_KEY`

Static shapefiles (CGS fault zones, CGS liquefaction, CalFire FHSZ) are downloaded once and committed to `backend/data/`. They are loaded into memory at app startup — not downloaded per request.
