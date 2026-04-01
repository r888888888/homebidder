import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PropertySummaryCard } from "./PropertySummaryCard";
import { AnalysisStream } from "./AnalysisStream";

const BASE_PROPERTY = {
  address_matched: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  latitude: 37.7612,
  longitude: -122.4313,
  county: "San Francisco",
  state: "CA",
  zip_code: "94114",
  price: 1_250_000,
  bedrooms: 3,
  bathrooms: 2,
  sqft: 1800,
  year_built: 1928,
  lot_size: 2500,
  property_type: "SINGLE_FAMILY",
  hoa_fee: null,
  days_on_market: 5,
  list_date: null,
  price_history: [],
  avm_estimate: 1_300_000,
  source: "homeharvest" as const,
};

describe("PropertySummaryCard", () => {
  it("renders the matched address", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument();
  });

  it("renders the list price formatted as currency", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.getByText(/\$1,250,000/)).toBeInTheDocument();
  });

  it("renders beds, baths, sqft", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    const bedsDt = screen.getByText(/^beds$/i);
    expect(bedsDt.nextElementSibling?.textContent).toBe("3");
    const bathsDt = screen.getByText(/^baths$/i);
    expect(bathsDt.nextElementSibling?.textContent).toBe("2");
    expect(screen.getByText(/1,800/)).toBeInTheDocument();
  });

  it("renders year built", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.getByText(/1928/)).toBeInTheDocument();
  });

  it("renders days on market", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    // DOM label is "Days on Market" and value "5" — find the dd sibling
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toBe("5");
  });

  it("renders AVM estimate", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.getByText(/\$1,300,000/)).toBeInTheDocument();
  });

  it("renders AVM vs list price delta", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    // avm (1,300,000) - price (1,250,000) = +50,000 = +4.0%
    expect(screen.getByText(/\+4\.0%|\+\$50,000/i)).toBeInTheDocument();
  });

  it("shows 'not listed' when price is null", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, price: null }} />);
    expect(screen.getByText(/not listed/i)).toBeInTheDocument();
  });

  it("shows 'N/A' for AVM when avm_estimate is null", () => {
    render(
      <PropertySummaryCard property={{ ...BASE_PROPERTY, avm_estimate: null }} />
    );
    expect(screen.getByText(/N\/A/i)).toBeInTheDocument();
  });

  it("renders property type", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.getByText(/single.?family/i)).toBeInTheDocument();
  });

  it("renders lot size", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.getByText(/2,500/)).toBeInTheDocument();
  });
});

describe("PropertySummaryCard — hours on market", () => {
  it("shows hours when list_date is less than 24 hours ago", () => {
    const recentDate = new Date(Date.now() - 5 * 60 * 60 * 1000); // 5 hours ago
    const listDate = recentDate.toISOString().replace("T", " ").slice(0, 19);
    render(
      <PropertySummaryCard
        property={{ ...BASE_PROPERTY, list_date: listDate, days_on_market: 0 }}
      />
    );
    expect(screen.getByText(/5\s*h(r|our)/i)).toBeInTheDocument();
  });

  it("shows days when list_date is 2 or more days ago", () => {
    const oldDate = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000); // 3 days ago
    const listDate = oldDate.toISOString().replace("T", " ").slice(0, 19);
    render(
      <PropertySummaryCard
        property={{ ...BASE_PROPERTY, list_date: listDate, days_on_market: 3 }}
      />
    );
    // Should show days, not hours
    expect(screen.queryByText(/\d+\s*h(r|our)/i)).not.toBeInTheDocument();
  });

  it("falls back to days_on_market when list_date is null", () => {
    render(
      <PropertySummaryCard
        property={{ ...BASE_PROPERTY, list_date: null, days_on_market: 7 }}
      />
    );
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toMatch(/7/);
  });
});

describe("PropertySummaryCard — AnalysisStream integration", () => {
  it("renders PropertySummaryCard when a tool_result for lookup_property_by_address arrives", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: BASE_PROPERTY as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);
    expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument();
  });
});
