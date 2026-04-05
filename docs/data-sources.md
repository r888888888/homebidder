# HomeBidder — Real Estate Data Sources

Reference document for all candidate data sources: scrapeable sites, free APIs, open datasets, and MLS access options. Includes legal risk assessment and recommended use per source.

---

## Summary Table

| Source | Data type | Cost | Legal risk | Recommended use |
|---|---|---|---|---|
| Redfin Data Center | Aggregate market stats | Free, no auth | None | Market trend context |
| County Assessor portals | Sold comps, property records | Free, no auth | None | Historical comp backbone |
| FHFA HPI | Price index | Free, no auth | None | Trend overlays |
| Census ACS API | Neighborhood demographics | Free, API key | None | Context enrichment |
| RentCast API | AVM, comps, active listings | 50 calls/mo free | None | Low-volume AVM lookups |
| Redfin Stingray API | Listings, sold comps | Free (undocumented) | Low–moderate | Comps scraping |
| Realtor.com `__NEXT_DATA__` | MLS listings | Free (scraping) | Moderate | Active listing detail |
| Zillow `__NEXT_DATA__` | Listings, Zestimate | Free (scraping) | High | Fallback only |
| homeharvest (Python) | Realtor.com + Redfin + Zillow | Free (library) | Moderate | Rapid prototyping |
| ATTOM Data | Full property data | 30-day trial, then paid | None | Future paid tier |
| **DataSF Assessor-Recorder API** | SF permits | Free, no auth | None | Permit history |
| **Alameda County Open Data** | Assessor parcel data | Free, no auth | None | Oakland/Berkeley comps |
| **Santa Clara County Assessor** | Assessor parcel data | Free, no auth | None | South Bay comps |
| **CGS Fault/Liquefaction shapefiles** | Earthquake hazard zones | Free, static download | None | CA seismic risk |
| **CalFire FHSZ shapefile** | Fire Hazard Severity Zones | Free, static download | None | CA fire risk |
| **FEMA Flood Map Service API** | NFIP flood zones | Free, no auth | None | Flood zone lookup |
| **BART Open API** | Station locations | Free, API key | None | Transit proximity scoring |

---

## 1. Redfin Data Center ✅ Start here for market trends

**URL:** https://www.redfin.com/news/data-center/

**What it is:** Redfin's official, freely downloadable bulk TSV files — no login, no API key, no scraping. Updated weekly (Wednesdays) and monthly (3rd Friday).

**Data available:**
- Median sale price, homes sold, new listings, inventory, days on market
- Price drop %, off-market-in-two-weeks %, months of supply
- Redfin Home Price Index (RHPI) — repeat-sales index

**Geographic granularity:** National → Metro → State → County → City → Zip Code → Neighborhood

**Format:** `.tsv.gz` direct download files

**Limitations:** Aggregate statistics only — no individual listing or comp records.

**Legal risk:** None. Explicitly offered by Redfin as a public resource.

**How to use in HomeBidder:** Pull zip-code-level median sale price and DOM to provide market context alongside individual comp analysis.

---

## 2. County Assessor Open Data ✅ Best free comp backbone

**What it is:** Many large counties publish their full assessor parcel rolls for free via open data portals. These contain individual property records including last sale price and date.

**Data available:**
- Parcel number, situs address
- Last sale date and price
- Assessed land value + improvement value
- Property type, square footage, year built, beds/baths, lot size
- Owner name and mailing address (redact for privacy)

**Coverage (confirmed open data portals):**

| County | Metro | Portal |
|---|---|---|
| Los Angeles County, CA | Los Angeles | portal.assessor.lacounty.gov |
| Maricopa County, AZ | Phoenix | mcassessor.maricopa.gov |
| King County, WA | Seattle | kingcounty.gov/en/dept/assessor |
| Cook County, IL | Chicago | cookcountyassessor.com/open-data |
| Harris County, TX | Houston | hcad.org |
| Travis County, TX | Austin | traviscad.org |
| Miami-Dade County, FL | Miami | miamidade.gov/pa |
| Fulton County, GA | Atlanta | fultonassessor.org |

**How to find for any county:** Search `[County] assessor open data` or `[County] parcel data download`. Most use Esri ArcGIS Open Data portals.

**Update frequency:** Typically nightly–monthly depending on county. Sale price data may lag 30–90 days due to recording delays.

**Legal risk:** None. Public records.

**How to use in HomeBidder:** Download parcel data for target metros and load into SQLite as a comp lookup table. Supplement scraped comps with assessor sale history for verification.

---

## 3. FHFA House Price Index ✅ Free price trend data

**URL:** https://www.fhfa.gov/data/hpi

**What it is:** The federal repeat-sales house price index covering properties with Fannie Mae or Freddie Mac mortgages since 1975. Free CSV/Excel downloads.

**Data available:**
- HPI value, YoY % change, QoQ % change
- National, state, metro (CBSA), ZIP code levels
- Updated monthly (national/state) and quarterly (metro/ZIP)

**Limitations:** Index values, not raw prices. Properties with non-conforming loans (jumbo, FHA, VA) not included.

**Legal risk:** None. U.S. government public data.

**How to use in HomeBidder:** Provide "market direction" context in offer rationale (e.g., "prices in this ZIP have risen 4.2% YoY per FHFA data").

---

## 4. Census Bureau ACS API ✅ Neighborhood context

**URL:** https://www.census.gov/developers/ | Free API key required (no credit card)

**What it is:** American Community Survey data via REST API. 5-year estimates available for all geographies including block groups and ZCTAs (ZIP approximations).

**Key housing tables:**
- `B25001` — Housing units
- `B25077` — Median home value (owner-occupied)
- `B25064` — Median gross rent
- `B25004` — Vacancy status
- `B25035` — Median year structure built

**Geographic granularity:** Nation → State → County → Census Tract → Block Group → ZCTA

**Python library:** `census` (PyPI) or direct `httpx` calls

**Legal risk:** None. Public government data.

**How to use in HomeBidder:** Enrich offer rationale with neighborhood context: vacancy rate, median home value, owner vs. renter ratio.

---

## 5. RentCast API ✅ Best free structured API

**URL:** https://www.rentcast.io/api

**Free tier:** 50 API calls/month, no credit card required

**Data available:**
- Property details for 140M+ U.S. properties
- AVM (sale estimate) + rent estimate
- Comparable properties (sales and rentals)
- Active for-sale and for-rent listings
- Market trend data by city/zip

**Endpoints relevant to HomeBidder:**
- `GET /properties?address=...` — property lookup
- `GET /avm/value?address=...` — sale price estimate + confidence
- `GET /avm/rent/long-term?address=...` — rental estimate
- `POST /listings/sale` — active listings search
- `GET /markets` — market trend stats

**Limitations:** 50 calls/month free is only useful for prototyping. Paid plans start at $49/month for 1,000 calls.

**Legal risk:** None. Licensed API.

**How to use in HomeBidder:** Use as the AVM source during prototyping. Call `GET /avm/value` to get an independent estimate alongside comp-derived value. Upgrade to paid when volume warrants.

---

## 6. Redfin Stingray API ⚠️ Undocumented but usable

**What it is:** Redfin's internal JSON/CSV API, well-documented by the open-source community. Does not require a browser session for basic calls.

**Key endpoints:**

| Endpoint | Method | Returns |
|---|---|---|
| `/stingray/api/gis` | GET | Up to 350 listings as JSON for a geographic area |
| `/stingray/api/gis-csv` | GET | Same as above as TSV — **no JS rendering needed** |
| `/stingray/api/home/details/initialInfo?path=...` | GET | Single property metadata |
| `/stingray/api/home/details/avmHistoricalData` | GET | Redfin Estimate history |
| `/stingray/api/home/details/neighborhoodStats/statsInfo` | GET | Neighborhood market stats |

**Key query params for `/gis` and `/gis-csv`:**
- `status_type`: `1` (for sale), `2` (sold), `3` (for rent)
- `num_homes`: max `350`
- `poly`: URL-encoded WKT polygon to define search area
- `sf`: property type bitmask (`1`=house, `2`=condo, `3`=townhouse, `6`=multi-family, `13`=mobile)
- `sold_within_days`: e.g. `180` for 6-month comp window

**Example (sold comps as CSV):**
```
GET https://www.redfin.com/stingray/api/gis-csv?status_type=2&num_homes=350&sold_within_days=180&poly=...
```

**Anti-bot protection:** Cloudflare (rated 8/10 difficulty by ScrapeOps). Requires:
- Residential proxy rotation
- Playwright with stealth fingerprinting
- Human-like delays (3–8s + jitter)

**Legal risk:** Low–moderate. ToS prohibits scraping. Redfin filed suit against a scraper in May 2023. For non-commercial/low-volume personal use the risk is practical rather than theoretical; for commercial scale, treat as high risk.

**Python libraries:**
- `homeharvest` — supports Redfin natively, most actively maintained
- `RedfinScraper` (GitHub: ryansherby) — targets Stingray API directly, last commit March 2023

**How to use in HomeBidder:** Primary comps source for scraped data. Use `/gis-csv` endpoint for bulk sold comps in a polygon around the subject property. Cache results in SQLite to minimize request volume.

---

## 7. Realtor.com (`__NEXT_DATA__`) ⚠️ Best scraping accuracy

**What it is:** Realtor.com syndicates directly from MLS feeds, making it the most accurate source for active listing data among the consumer portals. It is a Next.js app.

**Scraping approach:**
- Every property detail page embeds the full listing record in `<script id="__NEXT_DATA__">` JSON
- Navigate to `data["props"]["pageProps"]["initialReduxState"]` for complete details
- Includes MLS number, listing date, price history, HOA fees, days on market — fields other aggregators often omit

**Data available:**
- Price, beds/baths/sqft, lot size, year built, DOM
- MLS number, listing office, open house schedule
- Price history, tax history
- Walk/bike/transit scores, school ratings

**Anti-bot protection:** Akamai Bot Manager (high difficulty). Requires residential proxies and Playwright.

**Legal risk:** Moderate. ToS violation. Akamai protection is difficult to reliably bypass at scale.

**Python library:** `homeharvest` (PyPI) is the recommended wrapper — handles session management and parsing.

**How to use in HomeBidder:** Use as the primary source for active listing detail scraping when the buyer provides a Realtor.com URL.

---

## 8. Zillow (`__NEXT_DATA__` + search API) ⚠️ Highest legal risk

**What it is:** The most visited real estate portal, with the richest data including Zestimate, price history, and tax data. Has the most aggressive anti-scraping protections.

**Scraping approaches:**

**Method 1 — Property page `__NEXT_DATA__`:**
- `<script id="__NEXT_DATA__">` contains full property JSON
- Also check `<script id="hdpApolloPreloadedData">` for Apollo GraphQL cache
- Navigate to `props.pageProps.componentProps.gdpClientCache` → parse inner JSON → first value `.property`

**Method 2 — Search API (`async-create-search-page-state`):**
```
PUT https://www.zillow.com/async-create-search-page-state
Content-Type: application/json

{
  "searchQueryState": {
    "pagination": {"currentPage": 1},
    "usersSearchTerm": "Austin TX",
    "mapBounds": {"west": -98.0, "east": -97.5, "south": 30.1, "north": 30.5},
    "filterState": {"rs": {"value": true}}
  },
  "wants": {"cat1": ["listResults"], "cat2": ["total"]},
  "requestId": 2
}
```
Returns up to 500 listings per page in `listResults`.

**Data uniquely available on Zillow:**
- Zestimate (AVM) and Zestimate history
- Rental Zestimate
- "Make Me Move" price (owner-set price)
- Detailed tax assessment history

**Anti-bot protection:** HUMAN Security (PerimeterX) + Akamai Bot Manager. Enterprise-grade. Residential proxies required. Datacenter IPs are burned within hours. Behavioral analysis (mouse/scroll/keystroke patterns) active on key flows.

**Legal risk:** Highest among all sources. Zillow's ToS explicitly prohibits scraping and data mining. They have issued cease-and-desist letters and pursued litigation. The hiQ v. LinkedIn ruling (scraping public data ≠ CFAA violation) provides some protection, but Zillow also pursues contract-based claims.

**How to use in HomeBidder:** Fallback source only when the buyer provides a Zillow URL directly. Do not proactively scrape Zillow for comps.

---

## 9. `homeharvest` Python Library 🛠️ Best for prototyping

**GitHub:** https://github.com/ZacharyHampton/HomeHarvest
**PyPI:** `pip install homeharvest`

**What it does:** Single library wrapping Realtor.com (primary), Zillow, and Redfin. Returns Pandas DataFrames or lists of Pydantic models.

**Usage:**
```python
from homeharvest import scrape_property

# Sold comps in Austin in last 6 months
properties = scrape_property(
    site_name=["realtor.com", "redfin"],
    listing_type="sold",
    location="Austin, TX",
    past_days=180,
    results_wanted=50,
)
```

**Fields returned:** MLS ID, address, price, beds/baths/sqft, year built, DOM, sold date, list date, price per sqft, HOA fee, latitude/longitude, stories, parking, agent info, photos URL.

**Limitations:** 10,000 result ceiling per query. Relies on underlying site availability; breaks when sites update their structure.

**Legal risk:** Moderate — inherits the ToS risks of the sites it wraps.

**How to use in HomeBidder:** Use `homeharvest` for the initial integration and prototype. Replace with direct Stingray/`__NEXT_DATA__` calls once the scraping layer stabilizes.

---

## 10. ATTOM Data Solutions 💰 Future paid upgrade path

**URL:** https://api.developer.attomdata.com

**What it is:** One of the most comprehensive property data providers in the U.S. — 158M+ properties, sourced from county assessors, recorders, GIS offices, and federal sources.

**Data available:**
- Full assessor data (AVM, assessed value, property characteristics)
- Recorder/deed data (all historical sales, mortgage data)
- Distressed property data (foreclosures, pre-foreclosures, auctions)
- Rental rates, school data, hazard risk (flood, fire, earthquake)
- Active listings (limited markets)

**Free access:** 30-day free trial with sandbox API. No permanent free tier.

**Pricing:** Enterprise pricing (typically thousands/year). Contact sales for quotes.

**How to use in HomeBidder:** Swap in as the primary data source when scale warrants the cost. The API is well-documented and the data quality is significantly higher than scraped sources.

---

## 11. SF Bay Area-Specific Data Sources ✅ Primary target market

### 11a. DataSF Assessor-Recorder API (San Francisco)

**URL:** `https://data.sfgov.org/resource/wv5m-vpq2.json`

**What it is:** SF's open data portal exposes the full Assessor-Recorder database via Socrata API. No auth required for basic queries.

**Key fields:** `blklot` (block-lot), `from_st`/`to_st`/`street` (address), `assessedland`, `assessedimpr`, `totvalue`, `exemptcode`, `taxclass`, `zoning_code`, `yrbuilt`, `baths`, `rooms`, `resunits`

**How to use in HomeBidder:** Query using the normalized `street` + `blklot` (block-lot) derived from the Census geocoder output (which returns the Census TIGER matched address). Filter by street name and number from the matched address string.

---

### 11b. Alameda County Assessor Open Data

**URL:** `https://data.acgov.org/datasets/assessor-parcel-data`

**What it is:** Alameda County publishes parcel data via their ArcGIS Open Data portal. Covers Oakland, Berkeley, Piedmont, Fremont, Hayward, Alameda, and 10+ other cities.

**Format:** GeoJSON or CSV download; also queryable via ArcGIS REST API with address/APN filter.

**Key fields:** APN, situs address, assessed land, assessed improvement, last sale price, last sale date, year built, sqft, beds/baths, property type.

**How to use in HomeBidder:** Sold comp backbone for East Bay. Query by bounding box around subject property to pull recent sales.

---

### 11c. Santa Clara County Assessor

**URL:** `https://sccassessor.org` (open data section)

**What it is:** SCC provides parcel query via their portal; bulk download available via their open data page for properties in San Jose, Palo Alto, Sunnyvale, Cupertino, Mountain View, Los Altos, etc.

**How to use in HomeBidder:** Comp backbone for South Bay / Silicon Valley markets.

---

### 11d. CGS Earthquake Hazard Shapefiles (California Geological Survey)

**URL:** `https://maps.conservation.ca.gov/cgs/EQZApp/app/`

**What it is:** The California Geological Survey publishes official Alquist-Priolo Earthquake Fault Zone and Seismic Hazard Zone (liquefaction and landslide) boundaries as downloadable shapefiles. These are the same zones used in CA Natural Hazard Disclosure (NHD) reports.

**Datasets:**
- **Alquist-Priolo Fault Zones**: Statewide polygon shapefile of fault zones (special studies areas). Homes within these zones require geologic investigation before permits are issued.
- **Seismic Hazard Zones**: Two sub-layers — liquefaction zones (bay fill, alluvium) and earthquake-induced landslide zones. Covers Bay Area counties in detail.

**Format:** Shapefile download (zip). Load with `shapely` + `fiona` or `geopandas` at startup.

**Legal risk:** None. State government data.

**How to use in HomeBidder:** At startup, load both shapefiles into memory as `shapely` geometry objects. At query time, check `point.within(zone_polygon)` for the property lat/lon.

---

### 11e. CalFire Fire Hazard Severity Zones

**URL:** `https://gis.data.cnra.ca.gov/datasets/CAL-FIRE::california-fire-hazard-severity-zones`

**What it is:** CAL FIRE's official FHSZ map, the dataset used in NHD reports. Three tiers: Moderate, High, Very High. Also includes "SRA" (State Responsibility Area) vs "LRA" (Local Responsibility Area) classification.

**Format:** GeoJSON or shapefile download via CNRA open data portal.

**Key Bay Area high-risk areas:** Oakland Hills, Berkeley Hills, Marin County (most of it), Los Altos Hills, Portola Valley, parts of Fremont/Sunol, South Bay foothills.

**Insurance implication:** State Farm and Allstate have stopped writing new homeowners policies in CA. Properties in Very High FHSZ may only be insurable through the CA FAIR Plan (last-resort insurer) or specialty markets — add $5–15K/yr to carrying costs and flag for buyers.

**How to use in HomeBidder:** Same pattern as CGS shapefiles — load at startup, `point.within()` at query time.

---

### 11f. FEMA Flood Map Service Center API

**URL:** `https://msc.fema.gov/arcgis/rest/services/`

**What it is:** FEMA's NFIP flood zone data as an ArcGIS REST endpoint. Free, no auth.

**Query pattern:**
```
GET https://msc.fema.gov/arcgis/rest/services/NFHL/NFHL_National/FeatureServer/28/query
  ?geometry=-122.4,37.75&geometryType=esriGeometryPoint
  &spatialRel=esriSpatialRelIntersects
  &outFields=FLD_ZONE,ZONE_SUBTY,SFHA_TF
  &f=json
```

**Key flood zones:**
- `A`, `AE`, `AO`, `AH` — Special Flood Hazard Areas (SFHAs) — mandatory flood insurance if federally-backed mortgage
- `VE` — Coastal high-velocity zone
- `X` (shaded) — Moderate risk (0.2% annual chance)
- `X` (unshaded) — Minimal risk

**Bay Area relevance:** Bay waterfront properties (parts of Alameda Island, portions of Fremont, Marin shoreline, South Bay marshes), creek corridors (Coyote Creek San Jose, Guadalupe River), SoMa/Mission Bay SF (historical bay fill).

**How to use in HomeBidder:** Point-in-polygon query per property lookup. Cache result in DB with the `Listing` record.

---

### 11g. BART Open API

**URL:** `https://api.bart.gov/docs/overview/index.aspx`

**What it is:** BART's official REST API. Free with a key (register at api.bart.gov). The `stn.aspx?cmd=stns` endpoint returns all 50 stations with lat/lon.

**How to use in HomeBidder:** Fetch all stations once at startup (or cache for 30 days). Compute haversine distance from property lat/lon to each station; return nearest station and distance in miles. Properties within 0.5 miles (walkshed) command a documented transit premium.

**Caltrain:** No API needed — 29 stops are hardcoded with lat/lon and can be committed to `backend/data/caltrain_stations.json`.

---

## Recommended Implementation Order

1. **Now — prototype:**
   - `homeharvest` for listing + comp scraping
   - RentCast free tier for AVM validation (50 calls/month)
   - Redfin Data Center TSV for market trend context
   - DataSF Assessor API for SF permit data (free, no rate limits)

2. **Short-term — stabilize:**
   - Download CGS, CalFire, FEMA shapefiles once; load at startup for hazard checks
   - Replace `homeharvest` with direct Redfin Stingray `/gis-csv` calls for comps
   - Alameda + Santa Clara county assessor data in SQLite as comp backbone
   - FHFA HPI + Census ACS for enrichment
   - BART API key for transit proximity scoring

3. **Scale — when commercial:**
   - ATTOM Data API or RealEstateAPI.com as primary structured source
   - Eliminate scraped sources to reduce legal and reliability risk

---

## Legal Risk Summary

| Action | Risk level | Notes |
|---|---|---|
| Download Redfin Data Center TSVs | None | Explicitly offered |
| Download county assessor open data | None | Public records |
| Call Census/FHFA APIs | None | Government data |
| Call RentCast free API | None | Licensed service |
| Redfin Stingray API (low volume, personal) | Low | ToS violation; Redfin sued scrapers in 2023 |
| Realtor.com scraping (low volume) | Moderate | ToS violation; Akamai protection |
| Zillow scraping | High | Explicit ToS prohibition, PerimeterX, active enforcement |

> **Recommendation:** For a commercial product, plan to migrate off scraped sources to licensed APIs (ATTOM, RentCast paid, RealEstateAPI.com) before any significant user growth. Use scraping only during prototyping.
