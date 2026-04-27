import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { InvestmentTeaserCard } from "./InvestmentTeaserCard";
import type { InvestmentData } from "./InvestmentCard";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

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
  rent_controlled: false,
  rent_control_city: null,
  rent_control_implications: null,
  nearest_bart_station: "16TH ST MISSION",
  bart_distance_miles: 0.31,
  transit_premium_likely: true,
  nearest_muni_stop: null,
  muni_distance_miles: null,
  nearby_schools: [],
};

describe("InvestmentTeaserCard", () => {
  it("shows monthly buy cost and rent equivalent", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    expect(screen.getByText("Buy (monthly)")).toBeInTheDocument();
    expect(screen.getByText("Rent equivalent")).toBeInTheDocument();
    expect(screen.getAllByText(/\$7,820/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/\$3,500/).length).toBeGreaterThan(0);
  });

  it("shows upgrade CTA linking to /pricing", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    const link = screen.getByRole("link", { name: /upgrade to investor/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/pricing");
  });

  it("mentions that projections are available on Investor and Agent plans", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    expect(screen.getByText(/investor and agent plans/i)).toBeInTheDocument();
    expect(screen.getByText(/10\/20\/30-year/i)).toBeInTheDocument();
  });

  it("does not show 10/20/30-year appreciation projection labels", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    expect(screen.queryByText(/10yr projected value/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/20yr projected value/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/30yr projected value/i)).not.toBeInTheDocument();
  });

  it("does not show opportunity cost rows", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    expect(screen.queryByText(/10yr opp\. cost/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/20yr opp\. cost/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/30yr opp\. cost/i)).not.toBeInTheDocument();
  });

  it("shows transit info when present", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    expect(screen.getByText(/16TH ST MISSION/)).toBeInTheDocument();
  });

  it("shows ADU potential when present", () => {
    render(<InvestmentTeaserCard investment={BASE} />);
    expect(screen.getByText(/adu potential/i)).toBeInTheDocument();
  });

  it("shows rent comparison unavailable when no rent data", () => {
    render(
      <InvestmentTeaserCard
        investment={{
          ...BASE,
          monthly_buy_cost: null,
          monthly_rent_equivalent: null,
          monthly_cost_diff: null,
        }}
      />
    );
    expect(screen.getByText(/rent comparison unavailable/i)).toBeInTheDocument();
  });
});
