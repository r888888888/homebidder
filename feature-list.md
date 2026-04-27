# TODO

- Tier differentiation — PDF export for Agent tier. Generate a printable, shareable single-page report (offer range, risk summary, comps, investment snapshot) that agents can email to clients. This is the clearest justification for the $30/mo price point.
- Tier differentiation — history retention limits. Buyer: show only last 30 days of analyses. Investor: last 6 months. Agent: unlimited. Adds perceived upgrade value without removing real-time features.
- Tier differentiation — full comparable sales table for Investor+. Buyer tier sees only the summary range (low/mid/high); Investor and Agent see the full comp table with address, sale date, price, and $/sqft.
- Favorite analyses: users can mark analyses as favorites. Favorited analyses appear visually distinct on the history page (e.g. star icon, highlighted row).
- Show more info in the frontend about how the fair value estimate was calculated.
- Support inspection reports
- Support pest inspection reports
- Support disclosures
- Factor in seasonality of sales
- Regularly prune the database for stale data
- Plan this new feature: a validation mode. The app should look at recently sold properties in SF and run analysis on each property. Then it should grade its performance. For poorly scoring analyses, use the LLM to hypothesize what caused the discrepancy.
- Tier differentiation — bulk/batch analysis for Agent tier. Agent can submit a CSV of addresses and receive analyses for all of them. High-effort but strongest competitive differentiator for active agents touring many properties.
- Tier differentiation — watchlist for Investor+. Save a set of addresses; one-click re-run to refresh an analysis as market conditions change.

# DONE

- Tier differentiation — gate Investment tab to Investor+ only. Buyer tier (and anonymous users) see an `InvestmentTeaserCard` with monthly cost summary (buy vs rent), ADU potential, rent control, transit, and schools, plus an "Unlock Investment Projections" upsell linking to /pricing. Investor and Agent tiers see the full `InvestmentCard` with 10/20/30yr appreciation projections and opportunity cost analysis. Applied in both `AnalysisStream` and `PermalinkPage`. 14 new frontend tests.

- Payments & subscription tiers (4 phases). Three tiers: Buyer (free, 5/month), Investor ($10/month, 30/month), Agent ($30/month, 100/month). Anonymous users get 3/month (IP-based, monthly window). Superusers unlimited. Pre-existing users grandfathered to Investor tier. Stripe Checkout (hosted redirect, no embedded JS) for upgrades; webhook handles checkout.session.completed / subscription.updated / subscription.deleted. Customer billing portal via Stripe. New pricing page with plan cards; subscription section on profile page with tier badge, monthly usage meter, upgrade/manage billing buttons; structured 429 handling in analysis page (register prompt for anonymous, upgrade prompt for authenticated). 32 new backend tests, 26 new frontend tests.

- Duplex / triplex / multi-family detection: new `structure_multifamily` description signal fires on "duplex", "triplex", "half-duplex", "multi-family", "upper/lower unit/flat", "two-unit", "three-unit", and related phrases (weight −0.5%). New `_assess_multifamily_structure()` risk factor checks property_type (DUPLEX, TRIPLEX, MULTI_FAMILY, etc.) and description signals; flags a "low" risk factor with tailored descriptions for: one unit in a multi-unit building (unit number present), whole multi-family building (investment type), or description-only signals. 18 new backend tests.

- Admin portal superuser auth: replaced HTTP Basic Auth on `/api/admin/users` and `/api/admin/analyses` with JWT Bearer + `is_superuser` check (returns 403 for non-superusers). At startup, `_promote_first_user_to_superuser()` in `init_db()` automatically promotes the first-registered user (by rowid) to superuser if none exists yet. Frontend `admin.tsx` uses `useAuth()` context — shows "Please log in" when unauthenticated, "Access denied" when not a superuser, and auto-loads data for superusers. `is_superuser` added to `UserRead` interface in `auth.ts`. 16 backend tests, 10 frontend tests.

- Alternative services for Daly City: Schools — added 4 Daly City schools to `_BAY_AREA_SCHOOLS` (Serramonte Elementary, Benjamin Franklin Intermediate, Westmoor High, Jefferson High) with CAASPP 2022-23 proficiency rates. Previously the nearest SF schools (Lowell, Aptos) were shown for Daly City properties despite Daly City students attending Jefferson Elementary SD / Jefferson Union HS District. Transit — Daly City BART station was already present; SamTrans bus doesn't drive a transit premium signal. Permits — Daly City uses Accela (no public REST API); the existing graceful empty-return for non-SF counties is the correct fallback.

- Rent comparison data: registered users now get property-specific rent estimates from RentCast's `/v1/avm/rent` endpoint (neighborhood-aware, tuned to beds/baths/sqft/property type) instead of Census ACS zip-code medians. Anonymous users continue using Census data. New fields: `rent_estimate_source`, `rent_range_low`, `rent_range_high` in ba_value_drivers and investment metrics output. `user_id` threaded through `_run_phase8_investment` to `fetch_ba_value_drivers`. 19 new backend tests.

- Add a risk factor for properties that are Tenancy-in-Common or TICs. Detect TIC signals (`tenancy-in-common`, `tenants in common`, `TIC`) in the listing description via a new `ownership_tic` signal rule. Apply a −7% fair value discount in `recommend_offer()` (surfaced as `tic_adjustment_pct` in `fair_value_breakdown`). Surface a `tic_ownership` moderate risk factor in `assess_risk()` with financing and liquidity warnings. 17 new backend tests.

- Update front page feature badges to reflect the current app. Replaced "0.3-mile comp radius" → "Comparable sales analysis", "CA hazard zones" → "Fire, flood & seismic risk", "BART proximity" → "BART, MUNI & Caltrain proximity", "ADU potential" → "Fixer renovation estimate". Added "School & crime ratings" for the two major features added since the original badges were written.

- Dedupe photos based on the URL. `_extract_photo_urls` now tracks seen URLs in a set; the primary photo is deduplicated against alt_photos, and duplicate URLs within alt_photos are dropped (first occurrence preserved). Two new backend tests cover both cases.

- Fix history page "View" link: `to="/analysis_/$id"` used the TanStack Router route ID instead of the route path `/analysis/$id`, causing navigation to a non-existent URL in real browsers.

- Provide a permalink that users can copy for an analysis. New route `/analysis/$id` (`analysis_.$id.tsx`) loads a saved analysis by ID — no re-run. `AnalysisStream` shows a "Copy permalink" button once the `analysis_id` event fires. History page "View" link updated to go to the permalink instead of re-running the analysis. 6 new frontend tests.

- Add a HTTP basic auth protected admin portal at `/admin` that shows all users and all analyses. `GET /api/admin/users` and `GET /api/admin/analyses` return JSON protected by HTTP Basic Auth (FastAPI `HTTPBasic` scheme). Credentials read from `ADMIN_USERNAME` (default: `admin`) and `ADMIN_PASSWORD` env vars; 503 returned when `ADMIN_PASSWORD` is not configured. Frontend React page at `/admin` shows a login form, then renders paginated tables of users (email, status flags, ID) and analyses (address, offer range, risk, date, user). Both endpoints tested with 9 backend tests; frontend tested with 7 component tests.

- Add release versions and a changelog. `CHANGELOG.md` at project root (Keep-a-Changelog format, 6 retroactive releases v1.0.0–v1.5.0). `/changelog` page (`frontend/src/routes/changelog.tsx`) with inline TypeScript `RELEASES` data, grouped by Added/Changed/Fixed with coral dot bullets. "Changelog" link added to Footer. `/deploy` slash command at `.claude/commands/deploy.md` guides version bump → CHANGELOG.md → frontend data → commit/tag → `fly deploy` for both services. `CLAUDE.md` updated with a Releases section pointing to `/deploy`.

- Support Sign Up with Apple account. `GET /api/auth/apple/authorize` returns an authorization URL; `GET /api/auth/apple/callback` exchanges the code via Apple's token endpoint, decodes the `id_token` to extract email, and finds-or-creates a user. `client_secret` is a per-request ES256 JWT generated from the Apple private key. "Continue with Apple" button on login + register pages; `/auth/callback/apple` frontend route mirrors the Google pattern.

- Persist which renovation options were toggled in the database. New `PATCH /api/analyses/{id}/renovation-toggles` endpoint stores `disabled_indices: list[int]` inside `renovation_data_json`. `FixerAnalysisCard` accepts `analysisId` and `initialDisabledIndices` props; debounces a PATCH on every toggle. `AnalysisStream` passes the `analysis_id` SSE event down; history page passes `id` + `disabled_indices` from saved data.

- Restore RentCast AVM estimate behind a feature flag. RentCast (free tier: 50 calls/month) is the only viable free, legally-safe property-specific AVM. Restored behind `ENABLE_RENTCAST_AVM=1` + `RENTCAST_API_KEY`. When active, blends 15% AVM weight into comp-based fair value. Frontend shows "AVM Estimate" row in PropertySummaryCard when non-null. Degrades gracefully when flag is off.

- Investigate ways of getting a more accurate link to Redfin for the property. If listing_url from homeharvest is a Redfin URL, use it directly. Otherwise call Redfin's location-autocomplete API (stingray/do/location-autocomplete) to obtain the exact listing URL with home ID. Frontend falls back to a Redfin address search URL when no direct URL is available.

- Update .env.example with all missing environment variables: JWT_SECRET, SPOTCRIME_API_KEY, rate-limit flags (RATE_LIMIT_ENABLED/ANALYSES_PER_DAY/AUTHENTICATED_PER_DAY), LLM feature flags and model overrides (ENABLE_DESCRIPTION_LLM, DESCRIPTION_LLM_MODEL, PERMIT_LLM_MODEL, RENOVATION_LLM_MODEL), and Google OAuth (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URL). Grouped by category with signup links.

- User accounts (4 phases). Phase 1: email/password registration and login via fastapi-users (JWT Bearer, 30-day tokens), per-account rate limiting (20/day vs 5/day anonymous). Phase 2: analyses tied to the logged-in user, list/delete scoped by ownership, frontend AuthContext + login/register routes + auth headers on all API calls. Phase 3: profile page with change-password (PATCH /api/users/me) and delete-account (DELETE /api/users/me with ON DELETE SET NULL cascade on analyses). Phase 4: Google OAuth2 via httpx-oauth — authorize + callback endpoints, "Continue with Google" on login/register pages, /auth/callback/google route. Account not required; all existing anonymous flows unchanged.

- Make the gallery photos clickable to open a larger version. Each thumbnail is wrapped in a button; clicking opens a full-screen lightbox overlay. Hover effect scales the image and shows a magnifier icon. Lightbox supports Escape to close, click-outside to close, close button, and previous/next navigation with arrow buttons and arrow keys.
- Rate-limit unauthenticated visitors to 5 analyses per 24-hour rolling window. IP-based identification using Fly-Client-IP header (hashed for privacy). New rate_limit_entries DB table; RATE_LIMIT_ENABLED / RATE_LIMIT_ANALYSES_PER_DAY env vars. GET /api/rate-limit/status endpoint returns used/remaining/reset_at. Frontend shows a counter below the form card ("N of 5 free analyses remaining today"), turns amber at ≤ 2, shows reset time at 0. Submit button shows "Daily limit reached" and is disabled when quota exhausted. analysis.tsx shows a specific toast on 429.
- Add favicon to deployed app. Updated manifest.json with HomeBidder branding (was placeholder TanStack App values); added ICO fallback link and manifest link to HTML head alongside the existing SVG icon reference.
- Surface additional CalEnviroScreen 4.0 data points in risk analysis. Investigated all CES fields; added two new risk factors: Air Quality (PM2.5 percentile, already fetched but previously unused) and Environmental Contamination (cleanup/Superfund sites, groundwater threats, hazardous waste — each scored high/moderate/low at ≥80th/≥60th pct thresholds). Both factors are displayed in the Risk tab with CalEnviroScreen labels. Backend expanded to return 8 CES fields (was 4). Skipped: pesticides (rural/agricultural, not relevant for Bay Area urban properties), ozone (not property-specific), socioeconomic indicators (already covered by school ratings).
- Show crime rates near the property. Hybrid approach: DataSF Socrata API (SFPD data, free) for San Francisco properties; SpotCrime API (requires SPOTCRIME_API_KEY) for other Bay Area cities. Incidents within 0.5-mile radius over 90 days; distinguishes violent (assault, robbery, homicide, rape) from property (theft, burglary, auto theft, arson). Displayed in Risk tab as CrimeCard with color-coded counts (green/amber/red) and top crime types. Persisted in crime_data_json column and replayed from cache.
- Show quality of nearby schools using CAASPP proficiency rates. Nearest elementary/middle/high within 2 miles displayed in InvestmentCard with Math/ELA % meeting/exceeding CA standards, color-coded green/yellow/red. Built-in Bay Area school dataset (31 schools); `prefetch_schools` writes to `data/schools.json`.
- Support showing nearby MUNI stops. Saved 30 MUNI Metro stops to backend/data/muni_stops.json; added to transit search pool alongside BART/Caltrain; displays in InvestmentCard as a separate "Nearest MUNI" panel.
- Add a direct google maps link to the property.
- I want to include images from the MLS listing. If possible embed directly, but if that isn't possible then just link to a gallery.
- Fix photo gallery: \_extract_photo_urls was reading a non-existent `photos` dict column; homeharvest actually exports `primary_photo` (single URL string) and `alt_photos` (comma-separated URL string). Updated to read both columns and combine into a list.
- Update CLAUDE.md to instruct that a list of feature can be found in @feature-list.md. When instructed to implement the next feature, work off this list. Assume it is prioritized. When complete, move the item to the DONE section and commit your changes.
- Verify that fire hazard zone and liquefaction zone actually work. Test with real locations.
- Review the existing test coverage and remove tests that test scenarios that will likely never happen, or are based on assumptions that are no longer relevant. Look for opportunities to consolidate and refactor test coverage.
- Code review of frontend
- Code review of backend
- Review major renovation items typical for a century old SFH in the SF Bay Area. Update the fixer analysis to incorporate these items.
- Show LLM summary of permits in the card
- Hide the agent steps card once analysis is completed
- Review what LLM model is used for the final analysis. Evaluate whether Opus is a better match for what the model is doing.
- Compact final analysis prompt
- Property mismatch on "84 Caroline Way, Daly City, CA 94014". examine why the property summary card is wrong.
- Property mismatch on "1250 Ellis St #2, San Francisco, CA 94109". examine why the property summary card is wrong.
- Improve the fixer analysis card. Remove the post-renovation value, remove the implied equity value.
- The redfin and realtor links do not work
- Add links to real estate sites (redfin, zillow, realtor, etc)
- Add StreetView link
- Examine description of https://www.redfin.com/CA/San-Francisco/286-Crescent-Ave-94110/home/1687833 for more fixer keywords. Then reassess the logic for identifying fixer/renovated properties and remove keywords that are not strong signals.
- The fixer analysis card should always be displayed.
- The investment analysis for "24 Victoria St, San Francisco, CA 94132" seems to have a distorted projection.
- The highway proximity metric is not working correctly.
- Remove outliers from comp analysis
- Update investment analysis to move rent opportunity costs to 10/20/30 year scale
- Debug whether FHFA data includes data for 94112.
- Move BART API data into fetch script
- Move FHFA API data into fetch script
- Fix failing tests
- Tweak fixer analysis card to show an offer price that subtracts the cost of renovations.
- Add opportunity cost versus renting
- Disable 1password for the property address search field
- Why does "88 Hoff St Apt 104, San Francisco, CA 94110" produce a low offer recc that's higher than the high offer recc?
- Why does "88 Hoff St #104, San Francisco, CA 94110" not find the correct unit?
- Assuming the DBI permit search works, let's cache it in the database. Use a 24 hour expiry.
- Organize page into tabs
- Incorporate React Query for API calls
- Clicking on description should expand to full text
- Can we persist the fixer analysis card in the database
- Analyzing a property seems to insert it into the database twice
- Add renovation estimate for siding replacement
- Remove rentcast integration entirely
- fix sensitivity of fixer/renovated badges
- Brainstorm better methods for estimating renovation costs
  - Make each line item in renovation toggleable to adjust total renovation estimate
- Add an option to delete analysis from database
- Create a page with a list of previously persisted analyses
- For fixer properties, add a Fixer vs Turn-key comparison card. What would it cost in renovations to modernize this fixer versus buying a turn-key equivalent. Use the LLM to figure out market rates for construction costs. Use teh base recommended offer price.
- Remove Prop 13 tax impact information
- Eliminate presentation specific frontend tests
- Alert on tenant occupied
- Evaluate how LLM analysis of description might affect fair value
- Factor in noise pollution and smog risk
- Resolve the "sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) table analyses has no column named risk_level" error in the backend
- Handle backend error: "Anthropic bad request (400): Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}, 'request_id': 'req_011CZoKt4KB8yaQZQg6uRaJw'}"
