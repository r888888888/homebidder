import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CompsCard } from "./CompsCard";
import { AnalysisStream } from "./AnalysisStream";

const BASE_COMP = {
  address: "100 Comp St",
  city: "San Francisco",
  state: "CA",
  zip_code: "94110",
  sold_price: 1_100_000,
  list_price: 1_050_000,
  sold_date: "2026-02-01",
  bedrooms: 3,
  bathrooms: 2,
  sqft: 1700,
  price_per_sqft: 647,
  pct_over_asking: 4.76,
  distance_miles: 0.3,
  url: "https://redfin.com/comp",
  source: "homeharvest",
};

const COMPS = [BASE_COMP];

describe("CompsCard", () => {
  it("renders the section heading", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/comparable sales/i)).toBeInTheDocument();
  });

  it("renders a row for each comp", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
  });

  it("renders the sold price formatted as currency", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/\$1,100,000/)).toBeInTheDocument();
  });

  it("renders sqft", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/1,700/)).toBeInTheDocument();
  });

  it("renders price per sqft", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/\$647/)).toBeInTheDocument();
  });

  it("renders pct_over_asking as a percentage", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/\+4\.8%|\+4\.76%/)).toBeInTheDocument();
  });

  it("renders distance in miles", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/0\.30?\s*mi/i)).toBeInTheDocument();
  });

  it("renders sold date", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/2026-02-01/)).toBeInTheDocument();
  });

  it("shows negative pct_over_asking in a visually distinct way", () => {
    const underComp = { ...BASE_COMP, sold_price: 950_000, pct_over_asking: -9.52 };
    render(<CompsCard comps={[underComp]} />);
    expect(screen.getByText(/-9\.5%|-9\.52%/)).toBeInTheDocument();
  });

  it("shows — when pct_over_asking is null", () => {
    const comp = { ...BASE_COMP, pct_over_asking: null };
    render(<CompsCard comps={[comp]} />);
    // Should render a dash/em-dash for missing value in that column
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("shows — when distance_miles is null", () => {
    const comp = { ...BASE_COMP, distance_miles: null };
    render(<CompsCard comps={[comp]} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("renders multiple comps", () => {
    const comp2 = { ...BASE_COMP, address: "200 Other Ave", sold_price: 900_000 };
    render(<CompsCard comps={[BASE_COMP, comp2]} />);
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
    expect(screen.getByText(/200 Other Ave/i)).toBeInTheDocument();
  });

  it("renders an empty state when comps list is empty", () => {
    render(<CompsCard comps={[]} />);
    expect(screen.getByText(/no comparable sales/i)).toBeInTheDocument();
  });
});

describe("CompsCard — AnalysisStream integration", () => {
  it("renders CompsCard when a tool_result for fetch_comps arrives", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "fetch_comps",
        result: COMPS as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);
    expect(screen.getByText(/comparable sales/i)).toBeInTheDocument();
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
  });
});
