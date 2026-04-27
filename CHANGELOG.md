# Changelog

All notable changes to HomeBidder are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]

## [1.11.0] - 2026-04-27

### Added
- Favorite analyses — heart icon on history page rows and analysis detail/streaming page headers toggles favorite status; favorited history rows highlighted with rose background
- Comparable sales table gated to Investor+ tier — Buyer tier sees a teaser with comp count, price range, and median $/sqft; Investor and Agent tiers see full table with addresses, dates, and $/sqft
- History retention limits by tier — Buyer (30 days), Investor (6 months), Agent (unlimited); informational banner on history page links to /pricing for upgrades
- Lower confidence interval when square footage or lot size data is missing — CI half-width widens +2% for missing sqft, +1% for missing lot size on non-condos
- FAQ page at /faq explaining how HomeBidder's calculations work — 6 sections and 15 questions; FAQ link added to footer
- Admin link in footer visible only to superusers
- robots.txt allowing crawling of public pages (/pricing, /changelog) and disallowing private routes (/admin, /profile, /history, /analysis, /api/)

### Changed
- Superusers treated as Agent tier for all feature gates — unlimited history retention, full comparable sales table, and investment projections
- Analysis page title redesigned — address displayed as a full-width h1; action buttons (Refresh, New analysis, PDF Export) moved to a compact sub-row below the address
- Rate limit counter text updated from daily to monthly throughout the UI
- Plans nav link given persistent coral color to visually distinguish it from standard nav links
- Pricing page redesigned with tiered visual identity — colored header bands, per-tier feature checklists, featured Investor card with coral ring shadow, anonymous usage pill badge, and Stripe trust strip

## [1.10.0] - 2026-04-27

### Added
- Log-based hedonic adjustments for lot size and square footage — more accurate relative value comparisons using a diminishing-returns model; expanded comp fields surfaced in analysis
- Analysis history pagination — offset/limit query parameters to load history incrementally
- Fair value calculation breakdown on offer card — itemized view of how base comp value, hedonic adjustments, and risk discounts combine to produce the final fair value
- PDF export for Agent tier — download a full analysis report as a formatted PDF
- Investment tab projections gated to Investor+ tier — Buyer tier users see an upgrade prompt instead of financial projections
- Tab navigation on saved analysis permalink page — switch between Offer, Investment, and Risk views on the saved analysis page

### Fixed
- Stripe webhook handler updated for SDK v15 compatibility; added reset subscription script for development
- Refresh button on saved analysis page now triggers a force-refresh immediately without requiring a second click
- Valuation breakdown handles old analyses gracefully — loose null checks prevent errors when displaying older saved analyses
- Null/undefined guards in numeric formatting prevent toFixed errors on old analyses

## [1.9.0] - 2026-04-26

### Added
- Subscription tiers — Buyer (free, 5 analyses/month), Investor ($10/month, 30 analyses/month), Agent ($30/month, 100 analyses/month); anonymous users get 3 analyses/month; superusers are unlimited
- Stripe Checkout integration — hosted redirect flow for upgrading to Investor or Agent; no embedded Stripe.js required
- Stripe billing portal — authenticated users can manage or cancel their subscription from the profile page
- Stripe webhook handler — `checkout.session.completed` upgrades the user tier; `customer.subscription.updated` syncs status; `customer.subscription.deleted` downgrades to Buyer
- Pricing page at `/pricing` — three plan cards with limits, prices, Current Plan badge, and upgrade CTAs
- Subscription section on profile page — tier badge, monthly usage meter, upgrade buttons, and Manage billing link
- Pricing nav link in header — visible to all users
- Grandfathering migration — all pre-existing users automatically promoted to Investor tier on first startup after upgrade
- `stripe-listen.sh` helper script for forwarding Stripe webhooks to the local backend during development

### Changed
- Rate limiting switched from rolling 24-hour window to calendar-month window for all users
- Authenticated users counted against their tier's monthly limit via the analyses table (no longer via RateLimitEntry)
- Anonymous rate limit changed from daily to monthly (3/month) so free registration is clearly more valuable
- 429 responses on the analysis page now show a contextual prompt — register link for anonymous users, upgrade link for authenticated users

### Fixed
- Apple Sign In switched to `form_post` response mode for compatibility with stricter browser redirect policies

## [1.8.0] - 2026-04-25

### Added
- Duplex / triplex / multi-family structure detection — new `structure_multifamily` description signal fires on "duplex", "triplex", "half-duplex", "multi-family", "upper/lower unit/flat", "two-unit", and related phrases; new risk factor distinguishes one unit within a multi-unit building from a whole investment property
- Daly City school data — Serramonte Elementary, Benjamin Franklin Intermediate, Westmoor High, and Jefferson High added to the Bay Area school dataset with CAASPP 2022–23 proficiency rates

### Changed
- Admin portal authentication upgraded from HTTP Basic Auth to JWT Bearer + `is_superuser` check; first registered user is automatically promoted to superuser on startup

### Fixed
- Permalink page tests: added missing `useNavigate` to router mock

## [1.7.0] - 2026-04-25

### Added
- RentCast property-specific rent AVM for authenticated users in Bay Area value drivers — more accurate than Census zip-code median; falls back to Census for anonymous users
- Rent range (low/high) and estimate source surfaced in investment metrics
- Saved analysis page: "Refresh analysis" button re-runs the full analysis pipeline for the saved address
- Saved analysis page: final AI analysis text (rationale) now displayed in a styled markdown card

### Fixed
- TIC risk factor and fair value discount applied correctly in offer recommendation
- Deduplicated photo URLs in property lookup
- Front page feature badges updated to reflect current app capabilities
- History page "View" link navigated to wrong URL

## [1.6.0] - 2026-04-24

### Added
- HTTP Basic Auth protected admin portal at `/admin` — tables of all users and analyses, credentials from `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars
- Paginated admin portal with `page`/`page_size` query params and Prev/Next controls
- Permalink for saved analyses — `/analysis/$id` route loads a saved analysis without re-running; "Copy permalink" button in the analysis stream; History "View" links updated to permalink

### Fixed
- Admin analyses table shows user email instead of truncated UUID
- Admin analyses table removes redundant Low/High/Rating columns; formats price as M/k
- Rate-limit status fetch now sends Authorization header for authenticated users

## [1.5.0] - 2026-04-24

### Added
- Sign In with Apple — authorize + callback endpoints, branded button on login/register pages, `/auth/callback/apple` frontend route
- Persist renovation toggle state in the database; `PATCH /api/analyses/{id}/renovation-toggles` stores disabled indices
- RentCast AVM estimate restored behind `ENABLE_RENTCAST_AVM` feature flag; blends 15% AVM weight into comp-based fair value; shown in property summary when active
- Exact Redfin listing URL via location-autocomplete API; graceful fallback to address search URL
- UI polish: avatar dropdown header, shimmer skeletons, tab/toast animations, card-hover lift, footer logomark, coral sign-up button, refined form inputs
- `.env.example` updated with all environment variables grouped by category with signup links

### Fixed
- Rate-limit status endpoint now returns account quota (20/day) for authenticated users instead of the IP-based anonymous quota

## [1.4.0] - 2026-04-14

### Added
- User accounts — email/password registration and login via fastapi-users (JWT Bearer, 30-day tokens)
- Per-account rate limiting: 20 analyses/day for authenticated users vs. 5/day anonymous
- Analyses tied to logged-in user; list and delete scoped by ownership
- Frontend AuthContext, login/register routes, auth headers on all API calls
- Profile page: change password (`PATCH /api/users/me`), delete account (`DELETE /api/users/me` with ON DELETE SET NULL cascade)
- Google OAuth2 — authorize + callback endpoints, "Continue with Google" button on login/register pages, `/auth/callback/google` route

## [1.3.0] - 2026-04-10

### Added
- Tabbed analysis layout (Offer, Risk, Investment, Fixer tabs) with animated tab-fade transitions
- Clickable photo gallery with full-screen lightbox; Escape/arrow key navigation, click-outside to close
- Rate limiting for unauthenticated visitors: 5 analyses per 24-hour rolling window (IP-based, hashed for privacy)
- Rate-limit counter displayed below the form; turns amber at ≤ 2 remaining; shows reset time at 0
- Favicon (SVG + ICO) and corrected PWA manifest with HomeBidder branding

### Fixed
- Photo extraction corrected to read `primary_photo` and `alt_photos` columns from homeharvest (not a non-existent `photos` dict)

## [1.2.0] - 2026-04-03

### Added
- BART, Caltrain, and MUNI Metro transit proximity in investment analysis
- Nearby school quality using CAASPP proficiency rates — nearest elementary/middle/high within 2 miles, color-coded Math/ELA scores
- Crime rates near the property via DataSF Socrata API (San Francisco) and SpotCrime (Bay Area); violent vs. property crime breakdown
- CalEnviroScreen 4.0 data: Air Quality (PM2.5 percentile) and Environmental Contamination (cleanup sites, groundwater threats, hazardous waste)
- MLS listing photo gallery embedded in property summary card
- LLM summary of DBI permit history; permit data cached with 24-hour expiry
- Direct Google Maps link in property summary card
- External listing links: Redfin, Zillow, Realtor, and StreetView

## [1.1.0] - 2026-04-02

### Added
- Market trend analysis using FHFA HPI and Zillow ZHVI with ZIP-level fallback
- California hazard zone overlays: fire, flood, liquefaction, and seismic risk
- Risk assessment card with color-coded factor breakdown
- 10/20/30-year investment projections with opportunity-cost-vs-renting comparison
- Rent comparison normalized by bedroom count with rent growth factoring
- Comp outlier removal and adaptive search radius

### Fixed
- Off-market condo data handling; unit-number collision prevention
- Overbid/low-offer recommendation logic edge cases

## [1.0.0] - 2026-04-01

### Added
- Initial release: SF Bay Area offer analysis engine
- Property lookup via HomeHarvest with address normalization
- Comparable sales within 0.3-mile radius with sqft and property-type filters
- Fair value estimate with confidence interval
- Offer recommendation (low / recommended / high) with contingency guidance
- Fixer vs. turn-key analysis with line-item renovation estimates; toggleable line items
- Investment analysis with projected appreciation
- Analysis history page with expand-in-place detail and delete
- Streaming agent UI with step-by-step progress indicator
