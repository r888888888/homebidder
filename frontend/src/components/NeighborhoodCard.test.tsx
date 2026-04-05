import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NeighborhoodCard } from "./NeighborhoodCard";

const BASE_NEIGHBORHOOD = {
  median_home_value: 950_000,
  housing_units: 12_000,
  vacancy_rate: 2.5,
  median_year_built: 1965,
};

describe("NeighborhoodCard — neighborhood name", () => {
  it("renders the neighborhood name in the header when provided", () => {
    render(
      <NeighborhoodCard
        neighborhood={BASE_NEIGHBORHOOD}
        neighborhoodName="Noe Valley, Castro"
      />
    );
    expect(screen.getByText(/Noe Valley/)).toBeInTheDocument();
  });

  it("omits neighborhood name when not provided", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} />
    );
    expect(screen.queryByText(/Noe Valley/)).not.toBeInTheDocument();
  });
});

describe("NeighborhoodCard — neighborhood stats", () => {
  it("renders key neighborhood stats", () => {
    render(
      <NeighborhoodCard neighborhood={BASE_NEIGHBORHOOD} />
    );
    expect(screen.getByText(/\$950,000/)).toBeInTheDocument();
    expect(screen.getByText(/12,000/)).toBeInTheDocument();
    expect(screen.getByText(/2\.5%/)).toBeInTheDocument();
    expect(screen.getByText(/1965/)).toBeInTheDocument();
  });
});
