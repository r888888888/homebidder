import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CompsTeaserCard } from "./CompsTeaserCard";
import type { CompData } from "./CompsCard";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const BASE_COMP: CompData = {
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

describe("CompsTeaserCard", () => {
  it("renders the heading", () => {
    render(<CompsTeaserCard comps={[BASE_COMP]} />);
    expect(screen.getByRole("heading", { name: /recent sold comps/i })).toBeInTheDocument();
  });

  it("shows count of comps found", () => {
    const comps = [
      BASE_COMP,
      { ...BASE_COMP, address: "200 Other Ave", sold_price: 900_000 },
      { ...BASE_COMP, address: "300 Third St", sold_price: 1_300_000 },
    ];
    render(<CompsTeaserCard comps={comps} />);
    expect(screen.getByText(/3 comparable sales found/i)).toBeInTheDocument();
  });

  it("shows low, mid, high price labels", () => {
    render(<CompsTeaserCard comps={[BASE_COMP]} />);
    expect(screen.getByText(/\bLow\b/i)).toBeInTheDocument();
    expect(screen.getByText(/\bMid\b/i)).toBeInTheDocument();
    expect(screen.getByText(/\bHigh\b/i)).toBeInTheDocument();
  });

  it("computes correct low/mid/high from three comps", () => {
    const comps = [
      { ...BASE_COMP, sold_price: 900_000, price_per_sqft: 529 },
      { ...BASE_COMP, address: "200 Other Ave", sold_price: 1_100_000, price_per_sqft: 647 },
      { ...BASE_COMP, address: "300 Third St", sold_price: 1_300_000, price_per_sqft: 765 },
    ];
    render(<CompsTeaserCard comps={comps} />);
    expect(screen.getByText(/\$900,000/)).toBeInTheDocument(); // low
    expect(screen.getByText(/\$1,100,000/)).toBeInTheDocument(); // mid
    expect(screen.getByText(/\$1,300,000/)).toBeInTheDocument(); // high
  });

  it("shows median $/sqft", () => {
    const comps = [
      { ...BASE_COMP, price_per_sqft: 529 },
      { ...BASE_COMP, address: "200 Other Ave", price_per_sqft: 647 },
      { ...BASE_COMP, address: "300 Third St", price_per_sqft: 765 },
    ];
    render(<CompsTeaserCard comps={comps} />);
    expect(screen.getByText(/\$647/)).toBeInTheDocument();
  });

  it("does not show comp addresses (full table is gated)", () => {
    render(<CompsTeaserCard comps={[BASE_COMP]} />);
    expect(screen.queryByText(/100 Comp St/i)).not.toBeInTheDocument();
  });

  it("shows upsell section with upgrade link to /pricing", () => {
    render(<CompsTeaserCard comps={[BASE_COMP]} />);
    expect(screen.getByText(/unlock comparable sales/i)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /upgrade to investor/i });
    expect(link).toHaveAttribute("href", "/pricing");
  });

  it("renders gracefully with empty comps list", () => {
    render(<CompsTeaserCard comps={[]} />);
    expect(screen.getByRole("heading", { name: /recent sold comps/i })).toBeInTheDocument();
    expect(screen.getByText(/no comparable sales found/i)).toBeInTheDocument();
  });

  it("handles comps with null sold_price by ignoring them in summary", () => {
    const comps = [
      BASE_COMP,
      { ...BASE_COMP, address: "200 Other Ave", sold_price: null, price_per_sqft: null },
    ];
    render(<CompsTeaserCard comps={comps} />);
    // Should show count based on total comps
    expect(screen.getByText(/2 comparable sales found/i)).toBeInTheDocument();
    // When only 1 valid price exists, all three (low/mid/high) show the same value
    expect(screen.getAllByText(/\$1,100,000/).length).toBeGreaterThan(0);
  });
});
