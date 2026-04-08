import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InvestmentCard, type InvestmentData } from "./InvestmentCard";

const BASE: InvestmentData = {
  projected_value_1yr: 1300000,
  projected_value_3yr: 1406080,
  projected_value_5yr: 1520824,
  rate_30yr_fixed: 6.63,
  as_of_date: "2026-03-26",
  hpi_yoy_assumption_pct: 4.0,
  monthly_buy_cost: 7820.0,
  monthly_rent_equivalent: 3500.0,
  monthly_cost_diff: 4320.0,
  opportunity_cost_1yr: 54200.0,
  opportunity_cost_3yr: 180000.0,
  opportunity_cost_5yr: 337000.0,
  adu_potential: true,
  adu_rent_estimate: 2600,
  rent_controlled: true,
  rent_control_city: "San Francisco",
  rent_control_implications: "Likely subject to SF Rent Ordinance for older rentals.",
  nearest_bart_station: "16TH ST MISSION",
  bart_distance_miles: 0.31,
  transit_premium_likely: true,
};

describe("InvestmentCard", () => {
  it("renders appreciation projections and mortgage assumption", () => {
    render(<InvestmentCard investment={BASE} />);

    expect(screen.getByText(/investment analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/1yr projected value/i)).toBeInTheDocument();
    expect(screen.getByText(/3yr projected value/i)).toBeInTheDocument();
    expect(screen.getByText(/5yr projected value/i)).toBeInTheDocument();
    expect(screen.getByText(/assumes 6.63% 30yr fixed/i)).toBeInTheDocument();
  });

  it("renders opportunity cost section when rent data is available", () => {
    render(<InvestmentCard investment={BASE} />);

    expect(screen.getByText(/1yr opp\. cost/i)).toBeInTheDocument();
    expect(screen.getByText(/3yr opp\. cost/i)).toBeInTheDocument();
    expect(screen.getByText(/5yr opp\. cost/i)).toBeInTheDocument();
    expect(screen.getByText(/\$7,820.*mo.*\$3,500.*mo/i)).toBeInTheDocument();
  });

  it("shows unavailable message when rent data is absent", () => {
    render(
      <InvestmentCard
        investment={{
          ...BASE,
          monthly_buy_cost: null,
          monthly_rent_equivalent: null,
          monthly_cost_diff: null,
          opportunity_cost_1yr: null,
          opportunity_cost_3yr: null,
          opportunity_cost_5yr: null,
        }}
      />
    );

    expect(screen.getByText(/rent comparison unavailable/i)).toBeInTheDocument();
  });

  it("renders ADU, rent control, and transit details when present", () => {
    render(<InvestmentCard investment={BASE} />);

    expect(screen.getByText(/adu potential/i)).toBeInTheDocument();
    expect(screen.getByText(/san francisco/i)).toBeInTheDocument();
    expect(screen.getByText(/16TH ST MISSION/i)).toBeInTheDocument();
    expect(screen.getByText(/transit premium likely/i)).toBeInTheDocument();
  });

  it("hides optional panels when data is absent", () => {
    render(
      <InvestmentCard
        investment={{
          ...BASE,
          adu_potential: false,
          adu_rent_estimate: null,
          rent_controlled: false,
          rent_control_city: null,
          rent_control_implications: null,
          nearest_bart_station: null,
          bart_distance_miles: null,
          transit_premium_likely: false,
          monthly_buy_cost: null,
          monthly_rent_equivalent: null,
          monthly_cost_diff: null,
          opportunity_cost_1yr: null,
          opportunity_cost_3yr: null,
          opportunity_cost_5yr: null,
        }}
      />
    );

    expect(screen.queryByText(/adu potential/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/rent control/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/nearest transit/i)).not.toBeInTheDocument();
  });
});
