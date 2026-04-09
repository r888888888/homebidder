import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  avm_estimate: null,
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
  purchase_price: 1250000,
  projected_value_10yr: 1850000,
  projected_value_20yr: 2730000,
  projected_value_30yr: 4040000,
  rate_30yr_fixed: 6.63,
  as_of_date: "2026-03-26",
  hpi_yoy_assumption_pct: 4.0,
  monthly_buy_cost: 7820.0,
  monthly_rent_equivalent: 3500.0,
  monthly_cost_diff: 4320.0,
  opportunity_cost_10yr: 1050000.0,
  opportunity_cost_20yr: 3300000.0,
  opportunity_cost_30yr: 8200000.0,
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
  it("renders cards from tool_result events", async () => {
    const user = userEvent.setup();
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

    // Decision tab (default) — offer card
    expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument();

    // Property tab — address and neighborhood
    await user.click(screen.getByRole("tab", { name: /property/i }));
    expect(screen.getByRole("heading", { name: /450 Sanchez St/i })).toBeInTheDocument();
    expect(screen.getByText(/median home value/i)).toBeInTheDocument();

    // Market tab — comps
    await user.click(screen.getByRole("tab", { name: /market/i }));
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
  });

  it("uses the latest property tool result when multiple are present", async () => {
    const user = userEvent.setup();
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

    await user.click(screen.getByRole("tab", { name: /property/i }));
    expect(screen.getByRole("heading", { name: /NEW ADDRESS/i })).toBeInTheDocument();
    expect(screen.getByText(/\$1,750,000/)).toBeInTheDocument();
  });

  it("renders investment card from compute_investment_metrics tool result", async () => {
    const user = userEvent.setup();
    const events = [
      {
        type: "tool_result" as const,
        tool: "compute_investment_metrics",
        result: INVESTMENT_RESULT as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    await user.click(screen.getByRole("tab", { name: /market/i }));
    expect(screen.getByText(/investment analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/assumes 6.63% 30yr fixed/i)).toBeInTheDocument();
    expect(screen.getByText(/transit premium likely/i)).toBeInTheDocument();
  });

  it("renders permits card from fetch_sf_permits tool result", async () => {
    const user = userEvent.setup();
    const events = [
      {
        type: "tool_result" as const,
        tool: "fetch_sf_permits",
        result: PERMITS_RESULT as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    await user.click(screen.getByRole("tab", { name: /risk/i }));
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

  it("renders fixer skeleton when isRunning and renovation data not yet available", () => {
    render(<AnalysisStream events={[]} isRunning={true} />);
    expect(screen.getByText(/analyzing renovation potential/i)).toBeInTheDocument();
  });

  it("renders final analysis with markdown formatting", async () => {
    const user = userEvent.setup();
    const events = [
      {
        type: "text" as const,
        text: "# Summary\n\nThis is **important**.\n\n- Fast close\n- Strong deposit",
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    await user.click(screen.getByRole("tab", { name: /analysis/i }));
    expect(screen.getByRole("heading", { level: 1, name: /summary/i })).toBeInTheDocument();
    expect(screen.getByText("important")).toContainHTML("<strong>important</strong>");
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByText(/fast close/i)).toBeInTheDocument();
    expect(screen.getByText(/strong deposit/i)).toBeInTheDocument();
  });
});

describe("AnalysisStream — tab layout", () => {
  // ── Tab bar rendering ──────────────────────────────────────────────

  it("renders all five tab buttons", () => {
    render(<AnalysisStream events={[]} isRunning={false} />);
    expect(screen.getByRole("tab", { name: /decision/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /property/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /risk/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /analysis/i })).toBeInTheDocument();
  });

  it("Decision tab is selected by default", () => {
    render(<AnalysisStream events={[]} isRunning={false} />);
    expect(screen.getByRole("tab", { name: /decision/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /property/i })).toHaveAttribute("aria-selected", "false");
  });

  // ── Tab switching ──────────────────────────────────────────────────

  it("clicking Property tab makes it selected and deselects Decision", async () => {
    const user = userEvent.setup();
    render(<AnalysisStream events={[]} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /property/i }));
    expect(screen.getByRole("tab", { name: /property/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /decision/i })).toHaveAttribute("aria-selected", "false");
  });

  it("cards for inactive tabs are not in the document after switching", async () => {
    const user = userEvent.setup();
    const events = [
      {
        type: "tool_result" as const,
        tool: "recommend_offer",
        result: OFFER_RESULT as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: PROPERTY_RESULT as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);

    // Decision tab is default — offer card visible
    expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument();

    // Switch to Property tab — offer card unmounts, property card appears
    await user.click(screen.getByRole("tab", { name: /property/i }));
    expect(screen.queryByText(/offer recommendation/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /450 Sanchez St/i })).toBeInTheDocument();
  });

  // ── Content-availability dots ──────────────────────────────────────

  it("shows availability dot on Property tab when property data is present and Decision is active", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: PROPERTY_RESULT as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    const propertyTab = screen.getByRole("tab", { name: /property/i });
    expect(propertyTab.querySelector("[aria-label='has content']")).toBeInTheDocument();
  });

  it("does not show availability dot on the active tab", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "recommend_offer",
        result: OFFER_RESULT as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    const decisionTab = screen.getByRole("tab", { name: /decision/i });
    expect(decisionTab.querySelector("[aria-label='has content']")).not.toBeInTheDocument();
  });

  it("does not show dot on a tab with no content", () => {
    render(<AnalysisStream events={[]} isRunning={false} />);
    const marketTab = screen.getByRole("tab", { name: /market/i });
    expect(marketTab.querySelector("[aria-label='has content']")).not.toBeInTheDocument();
  });

  // ── Decision tab content ───────────────────────────────────────────

  it("renders OfferRecommendationCard on Decision tab", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "recommend_offer",
        result: OFFER_RESULT as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument();
  });

  it("renders FixerAnalysisCard on Decision tab", () => {
    const renovationResult = {
      is_fixer: true,
      fixer_signals: [],
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
      verdict: "cheaper_fixer" as const,
      savings_mid: 112_000,
      scope_notes: null,
      disclaimer: "Rough estimate.",
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
  });

  // ── Property tab content ───────────────────────────────────────────

  it("renders PropertySummaryCard and NeighborhoodCard on Property tab", async () => {
    const user = userEvent.setup();
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
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /property/i }));
    expect(screen.getByRole("heading", { name: /450 Sanchez St/i })).toBeInTheDocument();
    expect(screen.getByText(/median home value/i)).toBeInTheDocument();
  });

  // ── Market tab content ─────────────────────────────────────────────

  it("renders CompsCard and InvestmentCard on Market tab", async () => {
    const user = userEvent.setup();
    const events = [
      {
        type: "tool_result" as const,
        tool: "fetch_comps",
        result: COMPS_RESULT as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "compute_investment_metrics",
        result: INVESTMENT_RESULT as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /market/i }));
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
    expect(screen.getByText(/investment analysis/i)).toBeInTheDocument();
  });

  // ── Risk tab content ───────────────────────────────────────────────

  it("renders RiskAnalysisCard on Risk tab", async () => {
    const user = userEvent.setup();
    const riskResult = {
      overall_risk: "Moderate" as const,
      score: 45,
      factors: [{ name: "flood_zone", level: "low" as const, description: "No flood risk." }],
    };
    const events = [
      {
        type: "tool_result" as const,
        tool: "assess_risk",
        result: riskResult as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /risk/i }));
    expect(screen.getByText(/risk assessment/i)).toBeInTheDocument();
  });

  it("renders PermitsCard on Risk tab when present", async () => {
    const user = userEvent.setup();
    const events = [
      {
        type: "tool_result" as const,
        tool: "fetch_sf_permits",
        result: PERMITS_RESULT as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /risk/i }));
    expect(screen.getByText(/permit history/i)).toBeInTheDocument();
  });

  it("Risk tab shows no PermitsCard when fetch_sf_permits event is absent", async () => {
    const user = userEvent.setup();
    const riskResult = {
      overall_risk: "Low" as const,
      score: 20,
      factors: [{ name: "flood_zone", level: "low" as const, description: "None." }],
    };
    const events = [
      {
        type: "tool_result" as const,
        tool: "assess_risk",
        result: riskResult as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /risk/i }));
    expect(screen.queryByText(/permit history/i)).not.toBeInTheDocument();
  });

  // ── Analysis tab content ───────────────────────────────────────────

  it("renders agent steps and final markdown on Analysis tab", async () => {
    const user = userEvent.setup();
    const events = [
      { type: "tool_call" as const, tool: "fetch_comps" },
      { type: "text" as const, text: "# Summary\n\nReady to bid." },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    await user.click(screen.getByRole("tab", { name: /analysis/i }));
    expect(screen.getByText(/agent steps/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /summary/i })).toBeInTheDocument();
  });

  // ── Global chrome outside tabs ─────────────────────────────────────

  it("ValidationBanner renders above the tab bar in DOM order", () => {
    const validationResult = {
      actual_sold_price: 1_300_000,
      estimated_price: 1_187_000,
      error_dollars: 113_000,
      error_pct: 8.7,
      within_ci: false,
      sold_date: "2026-01-15",
      address: "450 Sanchez St",
    };
    const events = [
      {
        type: "validation_result" as const,
        result: validationResult as unknown as Record<string, unknown>,
      },
    ];
    render(<AnalysisStream events={events} isRunning={false} />);
    const tabList = screen.getByRole("tablist");
    const banner = screen.getByText(/validation mode/i).closest("[class]");
    // banner should appear before the tablist in the DOM
    expect(
      banner!.compareDocumentPosition(tabList) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });

  it("saved link renders regardless of active tab", () => {
    const events = [{ type: "analysis_id" as const, id: 99 }];
    render(<AnalysisStream events={events} isRunning={false} />);
    expect(screen.getByRole("link", { name: /view history/i })).toBeInTheDocument();
  });

  // ── Streaming + tab interaction ────────────────────────────────────

  it("shows loading skeleton on Decision tab when running and no offer data yet", () => {
    render(<AnalysisStream events={[]} isRunning={true} />);
    expect(screen.getByText(/computing offer range/i)).toBeInTheDocument();
  });

  it("does not show skeleton when not running and no data", () => {
    render(<AnalysisStream events={[]} isRunning={false} />);
    expect(screen.queryByText(/computing offer range/i)).not.toBeInTheDocument();
  });
});
