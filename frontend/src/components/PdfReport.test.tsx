import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

vi.mock("@react-pdf/renderer", () => ({
  Document: ({ children }: any) => <div data-testid="pdf-document">{children}</div>,
  Page: ({ children }: any) => <div data-testid="pdf-page">{children}</div>,
  View: ({ children }: any) => <div>{children}</div>,
  Text: ({ children }: any) => <span>{children}</span>,
  StyleSheet: { create: (s: any) => s },
  Font: { register: () => {} },
}));

import { PdfReport } from "./PdfReport";

const FULL_ANALYSIS = {
  id: 1,
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  created_at: "2026-04-01T12:00:00",
  offer_low: 1_170_000,
  offer_recommended: 1_200_000,
  offer_high: 1_250_000,
  risk_level: "Moderate",
  investment_rating: "Buy",
  rationale: "Good investment opportunity",
  property_data: {
    address_input: "450 Sanchez St",
    address_matched: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
    latitude: 37.76,
    longitude: -122.43,
    bedrooms: 3,
    bathrooms: 2,
    sqft: 1800,
    year_built: 1920,
    price: 1_250_000,
    hoa_fee: null,
    primary_photo: null,
    alt_photos: [],
    listing_url: null,
    redfin_url: null,
    google_maps_url: null,
    avm_estimate: null,
    property_type: "SFR",
    description: null,
    fixer_score: 0,
    renovated_score: 0,
  },
  neighborhood_data: null,
  offer_data: {
    list_price: 1_250_000,
    fair_value_estimate: 1_200_000,
    offer_low: 1_170_000,
    offer_recommended: 1_200_000,
    offer_high: 1_250_000,
    posture: "competitive",
    spread_vs_list_pct: -4.0,
    median_pct_over_asking: 5.0,
    pct_sold_over_asking: 80.0,
    offer_review_advisory: null,
    contingency_recommendation: {
      waive_appraisal: false,
      waive_loan: false,
      keep_inspection: true,
    },
  },
  risk_data: {
    overall_risk: "Moderate",
    score: 45,
    factors: [
      { name: "Fire Risk", level: "High", description: "Very High Fire Hazard Severity Zone" },
      { name: "Flood Risk", level: "Low", description: "Not in a flood zone" },
    ],
    ces_census_tract: null,
  },
  investment_data: {
    purchase_price: 1_250_000,
    projected_value_10yr: 1_850_000,
    projected_value_20yr: 2_730_000,
    projected_value_30yr: 4_040_000,
    rate_30yr_fixed: 6.63,
    as_of_date: "2026-03-26",
    hpi_yoy_assumption_pct: 4.0,
    monthly_buy_cost: 7820,
    monthly_rent_equivalent: 3500,
    monthly_cost_diff: 4320,
    opportunity_cost_10yr: 1_050_000,
    opportunity_cost_20yr: 3_300_000,
    opportunity_cost_30yr: 8_200_000,
    adu_potential: false,
    adu_rent_estimate: null,
    rent_controlled: false,
    rent_control_city: null,
    rent_control_implications: null,
    nearest_bart_station: "16TH ST MISSION",
    bart_distance_miles: 0.31,
    transit_premium_likely: false,
    nearest_muni_stop: null,
    muni_distance_miles: null,
    nearby_schools: [],
  },
  renovation_data: null,
  permits_data: null,
  crime_data: null,
  comps: [
    {
      address: "448 Sanchez St",
      unit: null,
      city: "San Francisco",
      state: "CA",
      zip_code: "94114",
      sold_price: 1_180_000,
      list_price: 1_150_000,
      sold_date: "2026-02-15",
      bedrooms: 3,
      bathrooms: 2,
      sqft: 1750,
      lot_size: null,
      price_per_sqft: 674,
      pct_over_asking: 2.6,
      distance_miles: 0.1,
      url: "",
      source: "homeharvest",
    },
  ],
};

describe("PdfReport", () => {
  it("renders without throwing given full analysis data", () => {
    expect(() => render(<PdfReport analysis={FULL_ANALYSIS as any} />)).not.toThrow();
  });

  it("renders without throwing when optional fields are null", () => {
    const minimalAnalysis = {
      ...FULL_ANALYSIS,
      property_data: null,
      offer_data: null,
      risk_data: null,
      investment_data: null,
      comps: [],
    };
    expect(() => render(<PdfReport analysis={minimalAnalysis as any} />)).not.toThrow();
  });
});
