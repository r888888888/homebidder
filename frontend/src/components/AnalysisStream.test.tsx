import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AnalysisStream } from "./AnalysisStream";

// Mock TanStack Router Link so component tests don't need a router context
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const PROPERTY_RESULT = {
  address_input: "450 Sanchez St, San Francisco, CA 94114",
  address_matched: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  latitude: 37.7612,
  longitude: -122.4313,
  county: "San Francisco",
  state: "CA",
  zip_code: "94114",
  city: "San Francisco",
  neighborhoods: "Noe Valley, Castro",
  unit: null,
  price: 1_250_000,
  bedrooms: 3,
  bathrooms: 2,
  sqft: 1800,
  year_built: 1928,
  lot_size: 2500,
  property_type: "SINGLE_FAMILY",
  hoa_fee: null,
  days_on_market: 5,
  list_date: null,
  price_history: [],
  avm_estimate: 1_300_000,
  listing_description: "Contractor special, tenant occupied",
  description_signals: {
    version: "v1",
    raw_description_present: true,
    net_adjustment_pct: -1.5,
    detected_signals: [{ label: "Tenant Occupied" }],
  },
  source: "homeharvest" as const,
};

const NEIGHBORHOOD_RESULT = {
  median_home_value: 950_000,
  housing_units: 12_000,
  vacancy_rate: 2.5,
  median_year_built: 1965,
};

const COMPS_RESULT = [
  {
    address: "100 Comp St",
    unit: null,
    city: "San Francisco",
    state: "CA",
    zip_code: "94110",
    sold_price: 1_100_000,
    list_price: 1_050_000,
    sold_date: "2026-02-01",
    bedrooms: 3,
    bathrooms: 2,
    sqft: 1700,
    lot_size: 2500,
    price_per_sqft: 647,
    pct_over_asking: 4.76,
    distance_miles: 0.3,
    url: "https://redfin.com/comp",
    source: "homeharvest",
  },
];

const OFFER_RESULT = {
  list_price: 1_250_000,
  fair_value_estimate: 1_099_500,
  offer_low: 1_225_000,
  offer_recommended: 1_187_000,
  offer_high: 1_300_000,
  posture: "competitive" as const,
  spread_vs_list_pct: -12.0,
  condition_signals: [{ label: "Tenant Occupied" }],
  median_pct_over_asking: 8.0,
  pct_sold_over_asking: 100.0,
  offer_review_advisory: "Offer review likely — submit by 2026-04-08",
  contingency_recommendation: {
    waive_appraisal: false,
    waive_loan: false,
    keep_inspection: true,
  },
};

const INVESTMENT_RESULT = {
  gross_yield_pct: 3.8,
  price_to_rent_ratio: 21.0,
  monthly_cashflow_estimate: -1150,
  adu_gross_yield_boost_pct: 5.6,
  projected_value_1yr: 1300000,
  projected_value_3yr: 1406080,
  projected_value_5yr: 1520824,
  investment_rating: "Buy",
  rate_30yr_fixed: 6.63,
  as_of_date: "2026-03-26",
  hpi_yoy_assumption_pct: 4.0,
  adu_potential: true,
  adu_rent_estimate: 2600,
  rent_controlled: true,
  rent_control_city: "San Francisco",
  rent_control_implications: "Likely subject to SF Rent Ordinance for older rentals.",
  nearest_bart_station: "16TH ST MISSION",
  bart_distance_miles: 0.31,
  transit_premium_likely: true,
};

const PERMITS_RESULT = {
  source: "dbi",
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  open_permits_count: 1,
  recent_permits_5y: 3,
  major_permits_10y: 1,
  oldest_open_permit_age_days: 480,
  permit_counts_by_type: {
    electrical: 1,
    plumbing: 0,
    building: 0,
  },
  complaints_open_count: 0,
  complaints_recent_3y: 2,
  flags: ["open_over_365_days", "recent_structural_work"],
  permits: [
    {
      permit_number: "202401011234",
      filed_date: "2024-01-10",
      issued_date: "2024-03-05",
      completed_date: null,
      status: "issued",
      permit_type: "ALTERATION",
      work_description: "Kitchen and bath remodel",
      estimated_cost: 120000,
      address: "450 SANCHEZ ST",
      unit: "2",
      source_url:
        "https://dbiweb02.sfgov.org/dbipts/default.aspx?page=EID_PermitDetails&PermitNo=202401011234",
    },
  ],
  complaints: [
    {
      complaint_number: "202295394",
      date_filed: "2022-09-09",
      status: "CLOSED",
      division: "HIS",
      expired: null,
      address: "319 PLYMOUTH AV",
      source_url: "https://dbiweb02.sfgov.org/dbipts/default.aspx?page=AddressComplaint&ComplaintNo=202295394",
    },
  ],
};

describe("AnalysisStream — analysis_id saved link", () => {
  it("shows a 'view history' link when analysis_id event is received", () => {
    const events = [
      {
        type: "analysis_id" as const,
        id: 42,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/saved/i)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /view history/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/history");
  });

  it("does not show saved link when no analysis_id event", () => {
    const events = [
      {
        type: "text" as const,
        text: "Some analysis text",
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.queryByRole("link", { name: /view history/i })).not.toBeInTheDocument();
  });
});

describe("AnalysisStream", () => {
  it("renders cards from tool_result events", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: PROPERTY_RESULT as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "fetch_neighborhood_context",
        result: NEIGHBORHOOD_RESULT as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "fetch_comps",
        result: COMPS_RESULT as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "recommend_offer",
        result: OFFER_RESULT as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/450 Sanchez St, San Francisco, CA 94114/i)).toBeInTheDocument();
    expect(screen.getByText(/median home value/i)).toBeInTheDocument();
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
    expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument();
  });

  it("uses the latest property tool result when multiple are present", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: {
          ...PROPERTY_RESULT,
          address_input: "OLD ADDRESS",
          address_matched: "OLD ADDRESS",
          price: 1_000_000,
        } as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: {
          ...PROPERTY_RESULT,
          address_input: "NEW ADDRESS",
          address_matched: "NEW ADDRESS",
          price: 1_750_000,
        } as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/NEW ADDRESS/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,750,000/)).toBeInTheDocument();
  });

  it("renders investment card from compute_investment_metrics tool result", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "compute_investment_metrics",
        result: INVESTMENT_RESULT as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/investment analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/assumes 6.63% 30yr fixed/i)).toBeInTheDocument();
    expect(screen.getByText(/transit premium likely/i)).toBeInTheDocument();
  });

  it("renders permits card from fetch_sf_permits tool result", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "fetch_sf_permits",
        result: PERMITS_RESULT as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/permit history/i)).toBeInTheDocument();
    expect(screen.getByText(/department of building inspection/i)).toBeInTheDocument();
    expect(screen.getByText(/complaint 202295394 is closed/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view permit/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view complaint/i })).toBeInTheDocument();
    expect(screen.getByText(/open permit older than 1 year/i)).toBeInTheDocument();
  });

  it("renders FixerAnalysisCard when estimate_renovation_cost tool result is present", () => {
    const renovationResult = {
      is_fixer: true,
      fixer_signals: ["Fixer / Contractor Special"],
      offer_recommended: 900_000,
      renovation_estimate_low: 65_000,
      renovation_estimate_mid: 88_000,
      renovation_estimate_high: 111_000,
      line_items: [{ category: "Kitchen remodel", low: 35_000, high: 60_000 }],
      all_in_fixer_low: 965_000,
      all_in_fixer_mid: 988_000,
      all_in_fixer_high: 1_011_000,
      turnkey_value: 1_100_000,
      renovated_fair_value: 1_100_000,
      implied_equity_mid: 112_000,
      verdict: "cheaper_fixer",
      savings_mid: 112_000,
      scope_notes: null,
      disclaimer: "Renovation costs are rough Bay Area estimates. Get contractor bids before committing.",
    };

    const events = [
      {
        type: "tool_result" as const,
        tool: "estimate_renovation_cost",
        result: renovationResult as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/fixer analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/fixer may win/i)).toBeInTheDocument();
    expect(screen.getByText(/kitchen remodel/i)).toBeInTheDocument();
  });

  it("does not render fixer card when estimate_renovation_cost event is absent", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "compute_investment_metrics",
        result: INVESTMENT_RESULT as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.queryByText(/fixer analysis/i)).not.toBeInTheDocument();
  });

  it("renders final analysis with markdown formatting", () => {
    const events = [
      {
        type: "text" as const,
        text: "# Summary\n\nThis is **important**.\n\n- Fast close\n- Strong deposit",
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByRole("heading", { level: 1, name: /summary/i })).toBeInTheDocument();
    expect(screen.getByText("important")).toContainHTML("<strong>important</strong>");
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByText(/fast close/i)).toBeInTheDocument();
    expect(screen.getByText(/strong deposit/i)).toBeInTheDocument();
  });
});
