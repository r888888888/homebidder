import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/faq")({ component: FAQPage });

interface FAQItem {
  question: string;
  answer: string;
}

interface FAQSection {
  title: string;
  items: FAQItem[];
}

const FAQ_SECTIONS: FAQSection[] = [
  {
    title: "Fair Value Estimation",
    items: [
      {
        question: "How is the fair value estimate calculated?",
        answer:
          "HomeBidder uses a comparable-sales (comp) approach as its primary method. It finds recently sold properties near the subject with similar characteristics, then adjusts each comp's sale price for differences in lot size and square footage using a log-linear hedonic model. The adjusted comp prices are averaged to produce a base fair value, which is then modified by any applicable discounts (e.g., TIC ownership, fixer condition). When fewer than three comps are available, the model falls back to a price-per-square-foot estimate derived from the same comp pool; when no comps exist at all, the list price is used as a proxy.",
      },
      {
        question: "How are comparable sales selected?",
        answer:
          "Comps are drawn from recent MLS sales within a 0.5-mile radius of the subject property. Properties must share the same broad type (single-family, condo/TIC, multi-family) and must have sold within the past six months. Outliers — sales more than two standard deviations from the median price-per-sqft — are removed before computing the average, so a single distressed or inflated sale does not skew the result.",
      },
      {
        question: "How do lot size and square footage adjustments work?",
        answer:
          "HomeBidder applies a log-linear hedonic model grounded in Bay Area empirical research. For lot size, an elasticity of 0.15 is used — meaning doubling the lot size relative to a comp adds roughly 10.4% to value (ln(2) × 0.15). For interior square footage, an elasticity of 0.25 is applied. Using logarithms rather than simple linear scaling prevents runaway adjustments on extreme size differences and better reflects the diminishing returns of extra space in dense urban markets. Lot adjustments are capped at −15% / +20% and sqft adjustments at −20% / +20%.",
      },
      {
        question: "What is the confidence interval, and what affects it?",
        answer:
          "The fair value is always accompanied by a low–high confidence interval. The interval widens when: there are few comps (< 3), the comp pool shows high price dispersion (coefficient of variation > 20%), the property is missing square footage or lot size data, or a fallback valuation method (price-per-sqft or list price) was used. The interval narrows as more matching comps are available and their adjusted prices converge. Missing size data also immediately triggers a 'low confidence' flag on the analysis.",
      },
    ],
  },
  {
    title: "Offer Recommendation",
    items: [
      {
        question: "How are the low, mid, and high offer prices set?",
        answer:
          "The mid offer is the fair value estimate itself. The low offer subtracts a margin that reflects local market conditions and the property's risk profile — conservative buyers or high-risk properties get a larger cushion. The high offer adds a premium calibrated to recent overbid rates in the same neighborhood; in hot SF submarkets this can be 5–15% above fair value. The spread between low and high is not fixed — it grows with uncertainty (wider confidence interval) and shrinks when comps are dense and consistent.",
      },
      {
        question: "What is a TIC discount, and why is it applied?",
        answer:
          "Tenancy-in-Common (TIC) properties in San Francisco typically sell at a 7% discount to equivalent condo or single-family values. This discount reflects two structural differences: (1) TIC financing is harder to obtain — most lenders require fractional loans at higher rates — and (2) TIC ownership carries liquidity risk because resale depends on co-owner cooperation or partition. HomeBidder detects TIC ownership signals in the listing description and property type, and applies the −7% discount to the comp-derived fair value before computing the offer range.",
      },
    ],
  },
  {
    title: "Risk Analysis",
    items: [
      {
        question: "What risk factors does HomeBidder assess?",
        answer:
          "HomeBidder evaluates the following risk categories: FEMA flood zone designation, CAL FIRE fire hazard severity zone, seismic liquefaction zone, earthquake fault proximity (Alquist-Priolo zones), CalEnviroScreen air quality (PM2.5) and environmental contamination percentiles, highway noise proximity, TIC ownership structure, multi-family structure type, and tenant-occupied status detected from the listing description. Each factor is rated high, moderate, or low and displayed in the Risk tab.",
      },
      {
        question: "How is flood risk determined?",
        answer:
          "HomeBidder queries the FEMA National Flood Hazard Layer for the property's coordinates. Properties in Zone AE, AO, or VE are flagged as high flood risk (Special Flood Hazard Areas where flood insurance is typically required for federally backed mortgages). Zones X-shaded (moderate) and X-unshaded (minimal) are rated accordingly.",
      },
      {
        question: "How is fire risk determined?",
        answer:
          "Fire risk is sourced from CAL FIRE's Fire Hazard Severity Zone (FHSZ) data. Zones are classified as Moderate, High, or Very High in State Responsibility Areas, and Local Responsibility Area classifications are also incorporated. Properties in Very High FHSZ zones receive a high risk rating; High zones receive moderate; Moderate zones receive low.",
      },
    ],
  },
  {
    title: "Investment Analysis",
    items: [
      {
        question: "How are the 10/20/30-year appreciation projections calculated?",
        answer:
          "Projections use FHFA House Price Index data specific to the property's metropolitan statistical area (MSA) and zip code where available. The historical compound annual growth rate (CAGR) over the most recent full decade is used as the base appreciation rate. The model compounds this rate forward from the estimated purchase price. These are illustrative projections — actual appreciation depends on market conditions, interest rates, and local policy changes.",
      },
      {
        question: "How is the rent estimate derived?",
        answer:
          "Registered users receive a property-specific rent estimate from RentCast's automated valuation model, which is neighborhood-aware and accounts for bedrooms, bathrooms, square footage, and property type. Anonymous users receive a Census ACS zip-code median rent for the property's zip. The source of the rent estimate is always labeled in the Investment tab.",
      },
      {
        question: "What does the buy-vs-rent comparison show?",
        answer:
          "The monthly cost comparison includes principal and interest (at a current 30-year fixed rate), estimated property taxes (using California's Prop 13 1% base rate on assessed value), homeowner's insurance, and HOA fees where disclosed. This all-in ownership cost is compared to the estimated market rent for a similar unit. The comparison is displayed at the 10, 20, and 30-year horizon to show how equity accumulation changes the long-run cost picture.",
      },
    ],
  },
  {
    title: "Schools, Transit & Crime",
    items: [
      {
        question: "How are school ratings calculated?",
        answer:
          "HomeBidder uses CAASPP (California Assessment of Student Performance and Progress) proficiency rates — the percentage of students meeting or exceeding state standards in Math and English Language Arts. The nearest elementary, middle, and high school within 2 miles are shown, color-coded green (≥ 60% proficient), yellow (40–59%), or red (< 40%). Data is from the 2022–23 CAASPP administration and covers 31 Bay Area schools in the built-in dataset.",
      },
      {
        question: "How is the transit score determined?",
        answer:
          "HomeBidder finds the nearest BART station, Caltrain station, and MUNI Metro stop to the property and reports the straight-line distance to each. A transit premium signal fires when the nearest rapid-transit stop (BART or Caltrain) is within 0.5 miles. Walking distance to transit is a well-documented value driver in the Bay Area; properties near BART in particular have historically commanded a measurable premium.",
      },
      {
        question: "How is crime risk assessed?",
        answer:
          "For San Francisco properties, HomeBidder queries the DataSF Socrata API (SFPD incident data) for incidents within a 0.5-mile radius over the past 90 days. For other Bay Area cities, the SpotCrime API is used when a key is configured. Incidents are split into violent crime (assault, robbery, homicide, rape) and property crime (theft, burglary, auto theft, arson). The counts are color-coded and displayed in the Risk tab alongside the top crime types reported.",
      },
    ],
  },
  {
    title: "Renovation Estimates",
    items: [
      {
        question: "How are fixer renovation costs estimated?",
        answer:
          "When a property is detected as a fixer (based on listing description keywords and MLS condition signals), HomeBidder uses an LLM to generate a line-item renovation estimate tailored to the property's age, size, and description. Line items are drawn from a curated list of renovation categories typical for Bay Area homes — roof replacement, electrical panel upgrade, plumbing, kitchen and bath remodels, foundation work, seismic retrofitting, HVAC, windows, and siding. Each line item can be toggled on or off to adjust the total estimate to your scope.",
      },
      {
        question: "How accurate are the renovation estimates?",
        answer:
          "Renovation estimates are ballpark figures intended to calibrate your offer, not contractor bids. Bay Area construction costs vary significantly by neighborhood, contractor availability, permit complexity, and material choices. The estimates are based on median contractor rates for the SF Bay Area and are most reliable for full-scope renovation of a typical 1900–1970s SFH. Always obtain at least two licensed contractor quotes before finalizing your offer on a fixer property.",
      },
    ],
  },
];

function FAQItem({ item, id }: { item: FAQItem; id: string }) {
  const [open, setOpen] = useState(false);
  const panelId = `faq-panel-${id}`;

  return (
    <div className="border-b border-[var(--line)] last:border-b-0">
      <button
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 py-4 text-left text-sm font-medium text-[var(--ink)] hover:text-[var(--coral)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--coral)] focus-visible:ring-offset-2"
      >
        <span>{item.question}</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
          className={`shrink-0 text-[var(--ink-muted)] transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M3 6l5 5 5-5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <div
        id={panelId}
        role="region"
        aria-labelledby={`faq-btn-${id}`}
        hidden={!open}
        className="pb-4 text-sm leading-relaxed text-[var(--ink-soft)]"
      >
        {item.answer}
      </div>
    </div>
  );
}

export function FAQPage() {
  return (
    <main className="page-wrap py-10">
      <div className="content-wrap">
        <h1 className="display-title mb-2 text-3xl font-bold text-[var(--ink)]">
          Frequently Asked Questions
        </h1>
        <p className="mb-10 text-sm text-[var(--ink-muted)]">
          How HomeBidder's calculations and data sources work.
        </p>

        <div className="space-y-10">
          {FAQ_SECTIONS.map((section, si) => (
            <section
              key={section.title}
              className={`fade-up stagger-${Math.min(si + 1, 5)}`}
            >
              <h2 className="display-title mb-1 border-b border-[var(--line)] pb-2 text-base font-semibold text-[var(--ink)]">
                {section.title}
              </h2>
              <div>
                {section.items.map((item, ii) => (
                  <FAQItem
                    key={ii}
                    item={item}
                    id={`${si}-${ii}`}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
