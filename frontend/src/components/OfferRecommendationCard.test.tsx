import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OfferRecommendationCard, type OfferData } from "./OfferRecommendationCard";

const BASE: OfferData = {
  fair_value_breakdown: {
    method: "median_comp_anchor",
    base_comp_median: 1_090_000,
    lot_adjustment_pct: 3.2,
    sqft_adjustment_pct: -1.5,
    tic_adjustment_pct: null,
  },
  list_price: 1_250_000,
  fair_value_estimate: 1_099_500,
  fair_value_confidence_interval: {
    low: 1_045_000,
    high: 1_155_000,
    ci_pct: 5.0,
    confidence: "moderate",
    factors: ["few_comps"],
  },
  offer_low: 1_225_000,
  offer_recommended: 1_187_000,
  offer_high: 1_300_000,
  posture: "competitive",
  spread_vs_list_pct: -12.0,
  condition_signals: [
    {
      label: "Tenant Occupied",
      category: "occupancy_negative",
      direction: "negative",
      weight_pct: -1.5,
      matched_phrases: ["tenant occupied"],
    },
  ],
  median_pct_over_asking: 8.0,
  pct_sold_over_asking: 100.0,
  offer_review_advisory: "Offer review likely — submit by 2026-04-08",
  contingency_recommendation: {
    waive_appraisal: false,
    waive_loan: false,
    keep_inspection: true,
  },
  hoa_equivalent_sfh_value: null,
};

describe("OfferRecommendationCard", () => {
  it("renders key offer numbers and stats", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    expect(screen.getByText(/competitive/i)).toBeInTheDocument();
    expect(screen.getByText(/1,187,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,225,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,300,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,099,500/)).toBeInTheDocument();
    expect(screen.getByText(/8\.0%/)).toBeInTheDocument();
    expect(screen.getByText(/100(\.0)?%/)).toBeInTheDocument();
  });

  it.each([
    { posture: "competitive", label: /competitive/i },
    { posture: "at-market", label: /at.market/i },
    { posture: "negotiating", label: /negotiating/i },
  ] as const)("renders posture badge: $posture", ({ posture, label }) => {
    render(<OfferRecommendationCard offer={{ ...BASE, posture }} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("omits overbid stats section when both are null", () => {
    render(
      <OfferRecommendationCard
        offer={{ ...BASE, median_pct_over_asking: null, pct_sold_over_asking: null }}
      />
    );
    expect(screen.queryByText(/median overbid/i)).not.toBeInTheDocument();
  });

  it("renders offer review advisory when present", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    expect(screen.getByText(/offer review likely/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-04-08/)).toBeInTheDocument();
  });

  it("does not render advisory section when null", () => {
    render(
      <OfferRecommendationCard offer={{ ...BASE, offer_review_advisory: null }} />
    );
    expect(screen.queryByText(/offer review likely/i)).not.toBeInTheDocument();
  });

  it("renders contingency rows", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    expect(screen.getByText(/keep inspection/i)).toBeInTheDocument();
    expect(screen.getByText(/waive appraisal/i)).toBeInTheDocument();
    expect(screen.getByText(/waive loan/i)).toBeInTheDocument();
  });

  it("marks waive appraisal as recommended when true", () => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          contingency_recommendation: {
            waive_appraisal: true,
            waive_loan: false,
            keep_inspection: true,
          },
        }}
      />
    );
    expect(screen.getByText(/waive appraisal/i)).toBeInTheDocument();
  });

  it("renders confidence interval range and label", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    expect(screen.getByText(/1,045,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,155,000/)).toBeInTheDocument();
    expect(screen.getByText(/moderate confidence/i)).toBeInTheDocument();
  });

  it.each([
    { confidence: "high" as const, label: /high confidence/i },
    { confidence: "moderate" as const, label: /moderate confidence/i },
    { confidence: "low" as const, label: /low confidence/i },
  ])("renders correct confidence label: $confidence", ({ confidence, label }) => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          fair_value_confidence_interval: {
            ...BASE.fair_value_confidence_interval!,
            confidence,
          },
        }}
      />
    );
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("omits confidence interval section when field is absent", () => {
    render(
      <OfferRecommendationCard
        offer={{ ...BASE, fair_value_confidence_interval: undefined }}
      />
    );
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });

  it("renders no-HOA SFH equivalent value when present", () => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          hoa_equivalent_sfh_value: {
            monthly_hoa_fee: 1_443,
            extra_purchase_power: 285_000,
            equivalent_sfh_price_no_hoa: 1_472_000,
            assumptions: {
              mortgage_rate_pct: 6.5,
              mortgage_term_years: 30,
              down_payment_pct: 20,
            },
          },
        }}
      />
    );

    expect(screen.getByText(/no-hoa sfh equivalent/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,472,000/)).toBeInTheDocument();
    expect(screen.getByText(/\+\$285,000/)).toBeInTheDocument();
    expect(screen.getByText(/assumes 6\.5% 30-year fixed/i)).toBeInTheDocument();
  });

  it("does not render no-HOA SFH equivalent section when absent", () => {
    render(<OfferRecommendationCard offer={{ ...BASE, hoa_equivalent_sfh_value: null }} />);
    expect(screen.queryByText(/no-hoa sfh equivalent/i)).not.toBeInTheDocument();
  });

  // --- Valuation breakdown section ---

  it("renders valuation breakdown section when fair_value_breakdown is present", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    expect(screen.getByText(/how was this calculated/i)).toBeInTheDocument();
  });

  it("renders 'Comparable sales' label for median_comp_anchor method", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    expect(screen.getByText("Comparable sales")).toBeInTheDocument();
  });

  it("renders 'Price per sq ft' label for ppsf_fallback method", () => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          fair_value_breakdown: {
            method: "ppsf_fallback",
            base_comp_median: null,
            lot_adjustment_pct: null,
            sqft_adjustment_pct: null,
            tic_adjustment_pct: null,
          },
        }}
      />
    );
    expect(screen.getByText(/price per sq ft/i)).toBeInTheDocument();
  });

  it("renders 'List price' label for list_price_fallback method", () => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          fair_value_breakdown: {
            method: "list_price_fallback",
            base_comp_median: null,
            lot_adjustment_pct: null,
            sqft_adjustment_pct: null,
            tic_adjustment_pct: null,
          },
        }}
      />
    );
    expect(screen.getByText(/list price \(fallback\)/i)).toBeInTheDocument();
  });

  it("renders base comp median value when present", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    // BASE has base_comp_median: 1_090_000
    expect(screen.getByText(/1,090,000/)).toBeInTheDocument();
  });

  it("renders lot adjustment percentage when non-null", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    // BASE has lot_adjustment_pct: 3.2
    expect(screen.getByText(/\+3\.2%/)).toBeInTheDocument();
  });

  it("renders sqft adjustment percentage when non-null", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    // BASE has sqft_adjustment_pct: -1.5
    expect(screen.getByText(/-1\.5%/)).toBeInTheDocument();
  });

  it("renders TIC discount when tic_adjustment_pct is non-null", () => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          fair_value_breakdown: {
            ...BASE.fair_value_breakdown!,
            tic_adjustment_pct: -7.0,
          },
        }}
      />
    );
    expect(screen.getByText(/tic/i)).toBeInTheDocument();
    expect(screen.getByText(/-7\.0%/)).toBeInTheDocument();
  });

  it("omits breakdown section when fair_value_breakdown is null", () => {
    render(
      <OfferRecommendationCard offer={{ ...BASE, fair_value_breakdown: null }} />
    );
    expect(screen.queryByText(/how was this calculated/i)).not.toBeInTheDocument();
  });

  it("renders confidence factors as human-readable text", () => {
    render(<OfferRecommendationCard offer={BASE} />);
    // BASE has factors: ["few_comps"]
    expect(screen.getByText(/few comparable sales/i)).toBeInTheDocument();
  });

  it("omits confidence factors section when factors array is empty", () => {
    render(
      <OfferRecommendationCard
        offer={{
          ...BASE,
          fair_value_confidence_interval: {
            ...BASE.fair_value_confidence_interval!,
            factors: [],
          },
        }}
      />
    );
    expect(screen.queryByText(/few comparable sales/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/why the range/i)).not.toBeInTheDocument();
  });

});
