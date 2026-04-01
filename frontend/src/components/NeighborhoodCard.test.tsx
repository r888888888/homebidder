import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NeighborhoodCard } from "./NeighborhoodCard";
import { AnalysisStream } from "./AnalysisStream";

const BASE_NEIGHBORHOOD = {
  median_home_value: 950_000,
  housing_units: 12_000,
  vacancy_rate: 2.5,
  median_year_built: 1965,
  prop13_assessed_value: 1_200_000,
  prop13_base_year: 2019,
  prop13_annual_tax: 15_000,
};

describe("NeighborhoodCard — neighborhood stats", () => {
  it("renders median home value", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getByText(/\$950,000/)).toBeInTheDocument();
  });

  it("renders housing units", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getByText(/12,000/)).toBeInTheDocument();
  });

  it("renders vacancy rate", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getByText(/2\.5%/)).toBeInTheDocument();
  });

  it("renders median year built", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getByText(/1965/)).toBeInTheDocument();
  });
});

describe("NeighborhoodCard — Prop 13 panel", () => {
  it("renders Prop 13 panel when prop13_assessed_value is set", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getAllByText(/prop\s*13/i).length).toBeGreaterThan(0);
  });

  it("shows seller annual tax from Prop 13 assessed value", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    // prop13_annual_tax = $15,000
    expect(screen.getByText(/\$15,000/)).toBeInTheDocument();
  });

  it("shows buyer estimated annual tax at purchase price × 1.25%", () => {
    // 1,500,000 × 1.25% = $18,750
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getByText(/\$18,750/)).toBeInTheDocument();
  });

  it("flags delta in amber when increase is between $5K and $10K/yr", () => {
    // seller tax $15,000, buyer tax $18,750 — delta $3,750 < $5K, no flag
    // Use a case where delta > $5K: purchase $2M, buyer tax $25,000, seller $15,000, delta $10K
    const { container } = render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={2_000_000} />
    );
    // buyer tax = 2,000,000 * 0.0125 = 25,000; delta = 10,000 > 5K → amber
    expect(container.querySelector("[data-tax-alert='amber']")).toBeInTheDocument();
  });

  it("flags delta in red when increase is above $10K/yr", () => {
    // seller $15,000, buyer at $5M = $62,500, delta $47,500 > $10K → red
    const { container } = render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={5_000_000} />
    );
    expect(container.querySelector("[data-tax-alert='red']")).toBeInTheDocument();
  });

  it("hides Prop 13 panel when prop13_assessed_value is null", () => {
    render(
      <NeighborhoodCard
        neighborhood={{ ...BASE_NEIGHBORHOOD, prop13_assessed_value: null, prop13_annual_tax: null, prop13_base_year: null }}
        purchasePrice={1_500_000}
      />
    );
    expect(screen.queryByText(/prop\s*13/i)).not.toBeInTheDocument();
  });
});

describe("NeighborhoodCard — AnalysisStream integration", () => {
  it("renders NeighborhoodCard when tool_result for fetch_neighborhood_context arrives", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "fetch_neighborhood_context",
        result: BASE_NEIGHBORHOOD as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: {
          price: 1_500_000,
          address_matched: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
        } as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);
    expect(screen.getAllByText(/prop\s*13/i).length).toBeGreaterThan(0);
  });
});
