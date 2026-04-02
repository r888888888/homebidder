import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OfferRecommendationCard, type OfferData } from "./OfferRecommendationCard";

const BASE: OfferData = {
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
  median_pct_over_asking: 8.0,
  pct_sold_over_asking: 100.0,
  offer_review_advisory: "Offer review likely — submit by 2026-04-08",
  contingency_recommendation: {
    waive_appraisal: false,
    waive_loan: false,
    keep_inspection: true,
  },
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
});
