import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/changelog")({ component: ChangelogPage });

interface ChangelogEntry {
  category: "Added" | "Changed" | "Fixed";
  text: string;
}

interface Release {
  version: string;
  date: string;
  entries: ChangelogEntry[];
}

const RELEASES: Release[] = [
  {
    version: "1.8.0",
    date: "2026-04-25",
    entries: [
      { category: "Added", text: "Duplex / triplex / multi-family structure detection — new signal fires on duplex, triplex, half-duplex, multi-family, upper/lower unit/flat, two-unit, and related phrases; risk factor distinguishes one unit within a multi-unit building from a whole investment property" },
      { category: "Added", text: "Daly City school data — Serramonte Elementary, Benjamin Franklin Intermediate, Westmoor High, and Jefferson High added with CAASPP 2022–23 proficiency rates" },
      { category: "Changed", text: "Admin portal authentication upgraded from HTTP Basic Auth to JWT Bearer + superuser check; first registered user automatically promoted to superuser on startup" },
      { category: "Fixed", text: "Permalink page tests: added missing useNavigate to router mock" },
    ],
  },
  {
    version: "1.7.0",
    date: "2026-04-25",
    entries: [
      { category: "Added", text: "RentCast property-specific rent AVM for authenticated users in Bay Area value drivers — more accurate than Census zip-code median; falls back to Census for anonymous users" },
      { category: "Added", text: "Rent range (low/high) and estimate source surfaced in investment metrics" },
      { category: "Added", text: "Saved analysis page: Refresh analysis button re-runs the full analysis pipeline for the saved address" },
      { category: "Added", text: "Saved analysis page: final AI analysis text now displayed in a styled markdown card" },
      { category: "Fixed", text: "TIC risk factor and fair value discount applied correctly in offer recommendation" },
      { category: "Fixed", text: "Deduplicated photo URLs in property lookup" },
      { category: "Fixed", text: "Front page feature badges updated to reflect current app capabilities" },
      { category: "Fixed", text: "History page View link navigated to wrong URL" },
    ],
  },
  {
    version: "1.6.0",
    date: "2026-04-24",
    entries: [
      { category: "Added", text: "HTTP Basic Auth protected admin portal at /admin — tables of all users and analyses, credentials from ADMIN_USERNAME/ADMIN_PASSWORD env vars" },
      { category: "Added", text: "Paginated admin portal with page/page_size query params and Prev/Next controls" },
      { category: "Added", text: "Permalink for saved analyses — /analysis/:id loads a saved analysis without re-running; Copy permalink button; History View links updated" },
      { category: "Fixed", text: "Admin analyses table shows user email instead of truncated UUID" },
      { category: "Fixed", text: "Admin analyses table removes redundant Low/High/Rating columns; formats price as M/k" },
      { category: "Fixed", text: "Rate-limit status fetch now sends Authorization header for authenticated users" },
    ],
  },
  {
    version: "1.5.0",
    date: "2026-04-24",
    entries: [
      { category: "Added", text: "Sign In with Apple — authorize + callback endpoints, branded button on login/register pages" },
      { category: "Added", text: "Persist renovation toggle state in the database; PATCH /api/analyses/{id}/renovation-toggles stores disabled line-item indices" },
      { category: "Added", text: "RentCast AVM estimate restored behind ENABLE_RENTCAST_AVM feature flag; blends 15% AVM weight into comp-based fair value and surfaces it in property summary" },
      { category: "Added", text: "Exact Redfin listing URL via location-autocomplete API; graceful fallback to address search URL" },
      { category: "Added", text: "UI polish: avatar dropdown header, shimmer skeletons, tab/toast animations, card-hover lift, footer logomark, coral sign-up button, refined form inputs" },
      { category: "Added", text: ".env.example updated with all environment variables grouped by category with signup links" },
      { category: "Fixed", text: "Rate-limit status endpoint now returns account quota (20/day) for authenticated users instead of the IP-based anonymous quota" },
    ],
  },
  {
    version: "1.4.0",
    date: "2026-04-14",
    entries: [
      { category: "Added", text: "User accounts — email/password registration and login via fastapi-users with JWT Bearer tokens (30-day expiry)" },
      { category: "Added", text: "Per-account rate limiting: 20 analyses/day for authenticated users vs. 5/day for anonymous visitors" },
      { category: "Added", text: "Analyses tied to the logged-in user; list and delete endpoints scoped by ownership" },
      { category: "Added", text: "Frontend AuthContext, login/register routes, and auth headers on all API calls" },
      { category: "Added", text: "Profile page: change password (PATCH /api/users/me) and delete account (DELETE /api/users/me)" },
      { category: "Added", text: "Google OAuth2 — authorize + callback endpoints, \"Continue with Google\" button on login/register pages" },
    ],
  },
  {
    version: "1.3.0",
    date: "2026-04-10",
    entries: [
      { category: "Added", text: "Tabbed analysis layout (Offer, Risk, Investment, Fixer) with animated tab-fade transitions" },
      { category: "Added", text: "Clickable photo gallery with full-screen lightbox; Escape/arrow key navigation, click-outside to close" },
      { category: "Added", text: "Rate limiting for unauthenticated visitors: 5 analyses per 24-hour rolling window (IP-based, hashed for privacy)" },
      { category: "Added", text: "Rate-limit counter below the form; turns amber at ≤ 2 remaining; shows reset time when exhausted" },
      { category: "Added", text: "Favicon (SVG + ICO) and corrected PWA manifest with HomeBidder branding" },
      { category: "Fixed", text: "Photo extraction corrected to read primary_photo and alt_photos columns from homeharvest" },
    ],
  },
  {
    version: "1.2.0",
    date: "2026-04-03",
    entries: [
      { category: "Added", text: "BART, Caltrain, and MUNI Metro transit proximity displayed in investment analysis" },
      { category: "Added", text: "Nearby school quality using CAASPP proficiency rates — nearest elementary/middle/high within 2 miles, color-coded Math/ELA scores" },
      { category: "Added", text: "Crime rates near the property via DataSF (San Francisco) and SpotCrime (Bay Area); violent vs. property crime breakdown" },
      { category: "Added", text: "CalEnviroScreen 4.0 data: Air Quality (PM2.5 percentile) and Environmental Contamination (cleanup sites, groundwater threats, hazardous waste)" },
      { category: "Added", text: "MLS listing photo gallery embedded in property summary card" },
      { category: "Added", text: "LLM summary of DBI permit history; permit data cached with 24-hour expiry" },
      { category: "Added", text: "Direct Google Maps link and external listing links (Redfin, Zillow, Realtor, StreetView) in property summary" },
    ],
  },
  {
    version: "1.1.0",
    date: "2026-04-02",
    entries: [
      { category: "Added", text: "Market trend analysis using FHFA HPI and Zillow ZHVI with ZIP-level fallback" },
      { category: "Added", text: "California hazard zone overlays: fire, flood, liquefaction, and seismic risk" },
      { category: "Added", text: "Risk assessment card with color-coded factor breakdown" },
      { category: "Added", text: "10/20/30-year investment projections with opportunity-cost-vs-renting comparison" },
      { category: "Added", text: "Rent comparison normalized by bedroom count with rent growth factoring" },
      { category: "Added", text: "Comp outlier removal and adaptive search radius" },
      { category: "Fixed", text: "Off-market condo data handling and unit-number collision prevention" },
      { category: "Fixed", text: "Overbid/low-offer recommendation logic edge cases" },
    ],
  },
  {
    version: "1.0.0",
    date: "2026-04-01",
    entries: [
      { category: "Added", text: "Initial release: SF Bay Area offer analysis engine" },
      { category: "Added", text: "Property lookup via HomeHarvest with address normalization" },
      { category: "Added", text: "Comparable sales within 0.3-mile radius with sqft and property-type filters" },
      { category: "Added", text: "Fair value estimate with confidence interval" },
      { category: "Added", text: "Offer recommendation (low / recommended / high) with contingency guidance" },
      { category: "Added", text: "Fixer vs. turn-key analysis with line-item renovation estimates; toggleable line items" },
      { category: "Added", text: "Investment analysis with projected appreciation" },
      { category: "Added", text: "Analysis history page with expand-in-place detail and delete" },
      { category: "Added", text: "Streaming agent UI with step-by-step progress indicator" },
    ],
  },
];

export function ChangelogPage() {
  return (
    <main className="page-wrap py-10">
      <div className="content-wrap">
        <h1 className="display-title mb-2 text-3xl font-bold text-[var(--ink)]">
          Changelog
        </h1>
        <p className="mb-10 text-sm text-[var(--ink-muted)]">
          A record of every notable improvement to HomeBidder.
        </p>

        <div className="space-y-10">
          {RELEASES.map((release, i) => (
            <section
              key={release.version}
              className={`fade-up stagger-${Math.min(i + 1, 5)}`}
            >
              <div className="mb-4 flex items-baseline gap-3 border-b border-[var(--line)] pb-2">
                <h2 className="display-title text-xl font-bold text-[var(--ink)]">
                  v{release.version}
                </h2>
                <time
                  dateTime={release.date}
                  className="text-xs text-[var(--ink-muted)]"
                >
                  {new Date(release.date + "T12:00:00").toLocaleDateString(
                    "en-US",
                    { year: "numeric", month: "long", day: "numeric" }
                  )}
                </time>
              </div>

              {(["Added", "Changed", "Fixed"] as const).map((cat) => {
                const items = release.entries.filter(
                  (e) => e.category === cat
                );
                if (!items.length) return null;
                return (
                  <div key={cat} className="mb-4">
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
                      {cat}
                    </h3>
                    <ul className="space-y-1.5">
                      {items.map((entry, j) => (
                        <li
                          key={j}
                          className="flex gap-2 text-sm leading-relaxed text-[var(--ink-soft)]"
                        >
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--coral)]" />
                          {entry.text}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
