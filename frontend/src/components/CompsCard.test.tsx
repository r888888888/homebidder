import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CompsCard } from "./CompsCard";
import { AnalysisStream } from "./AnalysisStream";

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
  it("renders the section heading", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/comparable sales/i)).toBeInTheDocument();
  });

  it("renders a row for each comp", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
  });

  it("renders unit in address when provided", () => {
    render(<CompsCard comps={[{ ...BASE_COMP, unit: "515" }]} />);
    expect(screen.getByText(/100 Comp St #515/i)).toBeInTheDocument();
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

  it("renders sold date in human-readable form", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/Feb\s+1,?\s+2026/i)).toBeInTheDocument();
  });

  it("renders beds and baths", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByText(/3bd\s*\/\s*2ba/i)).toBeInTheDocument();
  });

  it("shows negative pct_over_asking in a visually distinct way", () => {
    const underComp = { ...BASE_COMP, sold_price: 950_000, pct_over_asking: -9.52 };
    render(<CompsCard comps={[underComp]} />);
    expect(screen.getByText(/-9\.5%|-9\.52%/)).toBeInTheDocument();
  });

  it("shows lot size as tooltip on sqft cell", () => {
    render(<CompsCard comps={COMPS} />);
    expect(screen.getByTitle(/Lot size: 2,500 sqft/i)).toBeInTheDocument();
  });

  it("shows list price as tooltip on % over ask cell", () => {
    render(<CompsCard comps={COMPS} />);
    const cell = screen.getByTitle(/List price: \$1,050,000/i);
    expect(cell).toBeInTheDocument();
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

  it("sorts comps by distance ascending", () => {
    const far = { ...BASE_COMP, address: "Far House", distance_miles: 1.5 };
    const near = { ...BASE_COMP, address: "Near House", distance_miles: 0.1 };
    render(<CompsCard comps={[far, near]} />);
    const rows = screen.getAllByRole("row");
    // Header + 2 data rows; nearest should appear first
    expect(rows[1]).toHaveTextContent(/Near House/);
    expect(rows[2]).toHaveTextContent(/Far House/);
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
