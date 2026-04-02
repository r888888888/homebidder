import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NeighborhoodCard } from "./NeighborhoodCard";

const BASE_NEIGHBORHOOD = {
  median_home_value: 950_000,
  housing_units: 12_000,
  vacancy_rate: 2.5,
  median_year_built: 1965,
  prop13_assessed_value: 1_200_000,
  prop13_base_year: 2019,
  prop13_annual_tax: 15_000,
};

describe("NeighborhoodCard — neighborhood name", () => {
  it("renders the neighborhood name in the header when provided", () => {
    render(
      <NeighborhoodCard
        neighborhood={BASE_NEIGHBORHOOD}
        purchasePrice={1_500_000}
        neighborhoodName="Noe Valley, Castro"
      />
    );
    expect(screen.getByText(/Noe Valley/)).toBeInTheDocument();
  });

  it("omits neighborhood name when not provided", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.queryByText(/Noe Valley/)).not.toBeInTheDocument();
  });
});

describe("NeighborhoodCard — neighborhood stats", () => {
  it("renders key neighborhood stats", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={1_500_000} />
    );
    expect(screen.getByText(/\$950,000/)).toBeInTheDocument();
    expect(screen.getByText(/12,000/)).toBeInTheDocument();
    expect(screen.getByText(/2\.5%/)).toBeInTheDocument();
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

  it.each([
    { purchasePrice: 2_000_000, alert: "amber" },
    { purchasePrice: 5_000_000, alert: "red" },
  ])("applies %s alert when tax delta is high", ({ purchasePrice, alert }) => {
    const { container } = render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} purchasePrice={purchasePrice} />
    );
    expect(container.querySelector(`[data-tax-alert='${alert}']`)).toBeInTheDocument();
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
