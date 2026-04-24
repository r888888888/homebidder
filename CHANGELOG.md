# Changelog

All notable changes to HomeBidder are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]

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
