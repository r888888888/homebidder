import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InvestmentCard, type InvestmentData } from "./InvestmentCard";

const BASE: InvestmentData = {
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
  nearest_muni_stop: "Castro St",
  muni_distance_miles: 0.15,
};

describe("InvestmentCard", () => {
  it("renders appreciation projections and mortgage assumption", () => {
    render(<InvestmentCard investment={BASE} />);

    expect(screen.getByText(/investment analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/^today$/i)).toBeInTheDocument();
    expect(screen.getByText(/10yr projected value/i)).toBeInTheDocument();
    expect(screen.getByText(/20yr projected value/i)).toBeInTheDocument();
    expect(screen.getByText(/30yr projected value/i)).toBeInTheDocument();
    expect(screen.getByText(/assumes 6.63% 30yr fixed/i)).toBeInTheDocument();
  });

  it("renders opportunity cost section when rent data is available", () => {
    render(<InvestmentCard investment={BASE} />);

    expect(screen.getByText(/10yr opp\. cost/i)).toBeInTheDocument();
    expect(screen.getByText(/20yr opp\. cost/i)).toBeInTheDocument();
    expect(screen.getByText(/30yr opp\. cost/i)).toBeInTheDocument();
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
          opportunity_cost_10yr: null,
          opportunity_cost_20yr: null,
          opportunity_cost_30yr: null,
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

  it("renders both BART and MUNI in a single Nearest Transit card", () => {
    render(<InvestmentCard investment={BASE} />);

    expect(screen.getByText(/nearest transit/i)).toBeInTheDocument();
    expect(screen.getByText(/Castro St/)).toBeInTheDocument();
    expect(screen.getByText(/0\.15 mi/i)).toBeInTheDocument();
    expect(screen.getByText(/16TH ST MISSION/)).toBeInTheDocument();
    expect(screen.getByText(/0\.31 mi/i)).toBeInTheDocument();
    // Only one "Nearest Transit" heading — not two separate cards
    expect(screen.getAllByText(/nearest transit/i)).toHaveLength(1);
  });

  it("shows transit card with only MUNI when BART is null", () => {
    render(
      <InvestmentCard
        investment={{
          ...BASE,
          nearest_bart_station: null,
          bart_distance_miles: null,
          transit_premium_likely: false,
        }}
      />
    );

    expect(screen.getByText(/nearest transit/i)).toBeInTheDocument();
    expect(screen.getByText(/Castro St/)).toBeInTheDocument();
    expect(screen.queryByText(/BART/)).not.toBeInTheDocument();
  });

  it("shows transit card with only BART when MUNI is null", () => {
    render(
      <InvestmentCard
        investment={{ ...BASE, nearest_muni_stop: null, muni_distance_miles: null }}
      />
    );

    expect(screen.getByText(/nearest transit/i)).toBeInTheDocument();
    expect(screen.getByText(/16TH ST MISSION/)).toBeInTheDocument();
    expect(screen.queryByText(/MUNI/)).not.toBeInTheDocument();
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
          nearest_muni_stop: null,
          muni_distance_miles: null,
          monthly_buy_cost: null,
          monthly_rent_equivalent: null,
          monthly_cost_diff: null,
          opportunity_cost_10yr: null,
          opportunity_cost_20yr: null,
          opportunity_cost_30yr: null,
        }}
      />
    );

    expect(screen.queryByText(/adu potential/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/rent control/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/nearest transit/i)).not.toBeInTheDocument();
  });
});
