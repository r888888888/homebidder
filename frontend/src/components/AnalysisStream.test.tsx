import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AnalysisStream } from "./AnalysisStream";

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
  source: "homeharvest" as const,
};

const NEIGHBORHOOD_RESULT = {
  median_home_value: 950_000,
  housing_units: 12_000,
  vacancy_rate: 2.5,
  median_year_built: 1965,
  prop13_assessed_value: 1_200_000,
  prop13_base_year: 2019,
  prop13_annual_tax: 15_000,
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
  median_pct_over_asking: 8.0,
  pct_sold_over_asking: 100.0,
  offer_review_advisory: "Offer review likely — submit by 2026-04-08",
  contingency_recommendation: {
    waive_appraisal: false,
    waive_loan: false,
    keep_inspection: true,
  },
};

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
    expect(screen.getAllByText(/prop\s*13/i).length).toBeGreaterThan(0);
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
});
