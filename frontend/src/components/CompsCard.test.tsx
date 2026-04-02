import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CompsCard } from "./CompsCard";

const BASE_COMP: import("./CompsCard").CompData = {
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
};

const COMPS = [BASE_COMP];

describe("CompsCard", () => {
  it("renders heading and key comp fields", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/comparable sales/i)).toBeInTheDocument();
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,100,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,700/)).toBeInTheDocument();
    expect(screen.getByText(/\$647/)).toBeInTheDocument();
    expect(screen.getByText(/\+4\.8%|\+4\.76%/)).toBeInTheDocument();
    expect(screen.getByText(/0\.30?\s*mi/i)).toBeInTheDocument();
    expect(screen.getByText(/Feb\s+1,?\s+2026/i)).toBeInTheDocument();
    expect(screen.getByText(/3bd\s*\/\s*2ba/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Lot size: 2,500 sqft/i)).toBeInTheDocument();
    expect(screen.getByTitle(/List price: \$1,050,000/i)).toBeInTheDocument();
  });

  it("renders unit in address when provided", () => {
    render(<CompsCard comps={[{ ...BASE_COMP, unit: "515" }]} />);
    expect(screen.getByText(/100 Comp St #515/i)).toBeInTheDocument();
  });

  it.each([
    { name: "negative pct_over_asking", patch: { pct_over_asking: -9.52 }, expected: /-9\.5%|-9\.52%/ },
    { name: "null pct_over_asking", patch: { pct_over_asking: null }, expected: "—" },
    { name: "null distance_miles", patch: { distance_miles: null }, expected: "—" },
  ])("handles $name", ({ patch, expected }) => {
    render(<CompsCard comps={[{ ...BASE_COMP, ...patch }]} />);
    if (typeof expected === "string") {
      expect(screen.getAllByText(expected).length).toBeGreaterThan(0);
    } else {
      expect(screen.getByText(expected)).toBeInTheDocument();
    }
  });

  it("renders multiple comps sorted by distance", () => {
    const comp2 = { ...BASE_COMP, address: "200 Other Ave", sold_price: 900_000 };
    render(<CompsCard comps={[{ ...BASE_COMP, distance_miles: 0.3 }, { ...comp2, distance_miles: 0.1 }]} />);
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
    expect(screen.getByText(/200 Other Ave/i)).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent(/200 Other Ave/);
    expect(rows[2]).toHaveTextContent(/100 Comp St/);
  });

  it("marks the closest comps with data-nearest attribute", () => {
    const near = { ...BASE_COMP, address: "Near House", distance_miles: 0.1 };
    const far = { ...BASE_COMP, address: "Far House", distance_miles: 1.5 };
    render(<CompsCard comps={[far, near]} />);
    const nearestRows = document.querySelectorAll("[data-nearest='true']");
    expect(nearestRows.length).toBe(2); // both qualify when ≤ 3 total
  });

  it("renders an empty state when comps list is empty", () => {
    render(<CompsCard comps={[]} />);
    expect(screen.getByText(/no comparable sales/i)).toBeInTheDocument();
  });
});
