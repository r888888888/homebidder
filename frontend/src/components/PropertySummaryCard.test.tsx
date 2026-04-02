import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PropertySummaryCard } from "./PropertySummaryCard";
import { AnalysisStream } from "./AnalysisStream";

const BASE_PROPERTY = {
  address_input: "450 Sanchez St, San Francisco, CA 94114",
  address_matched: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  latitude: 37.7612,
  longitude: -122.4313,
  county: "San Francisco",
  state: "CA",
  zip_code: "94114",
  city: "San Francisco",
  neighborhoods: "Noe Valley, Castro",
  unit: null,
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
    expect(screen.getByText(/450 Sanchez St, San Francisco, CA 94114/i)).toBeInTheDocument();
  });

  it("prefers original address input for unit display", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          address_input: "821 Folsom St #515, San Francisco, CA 94107",
          address_matched: "821 FOLSOM ST, SAN FRANCISCO, CA, 94107",
        }}
      />
    );
    expect(
      screen.getByText(/821 Folsom St #515, San Francisco, CA 94107/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Matched as:\s*821 FOLSOM ST UNIT 515, SAN FRANCISCO, CA, 94107/i)
    ).toBeInTheDocument();
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
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toBe("5 days");
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

  it("shows '—' when price is null", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, price: null }} />);
    const dt = screen.getByText(/^list price$/i);
    expect(dt.nextElementSibling?.textContent).toBe("—");
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

  it("renders city", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    const dt = screen.getByText(/^city$/i);
    expect(dt.nextElementSibling?.textContent).toBe("San Francisco");
  });

  it("renders county", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    const dt = screen.getByText(/^county$/i);
    expect(dt.nextElementSibling?.textContent).toBe("San Francisco");
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
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toMatch(/3 days/);
  });

  it("falls back to days_on_market when list_date is null", () => {
    render(
      <PropertySummaryCard
        property={{ ...BASE_PROPERTY, list_date: null, days_on_market: 7 }}
      />
    );
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toMatch(/7 days/);
  });

  it("uses days_on_market when list_date is clearly stale/inconsistent", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          // Known provider edge case: stale list_date but fresh DOM
          list_date: "2017-10-22 07:00:00",
          days_on_market: 0,
        }}
      />
    );
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toBe("0 days");
  });
});

describe("PropertySummaryCard — unit field", () => {
  it("renders Unit field when unit is set", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, unit: "1206" }} />);
    const dt = screen.getByText(/^unit$/i);
    expect(dt.nextElementSibling?.textContent).toBe("1206");
  });

  it("does not render Unit field when unit is null", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, unit: null }} />);
    expect(screen.queryByText(/^unit$/i)).not.toBeInTheDocument();
  });
});

describe("PropertySummaryCard — lot size visibility", () => {
  it("renders Lot Size for single family properties", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, property_type: "SINGLE_FAMILY" }} />);
    expect(screen.getByText(/lot size/i)).toBeInTheDocument();
  });

  it("does not render Lot Size for condo properties", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, property_type: "CONDO", unit: "5B" }} />);
    expect(screen.queryByText(/lot size/i)).not.toBeInTheDocument();
  });

  it("does not render Lot Size for townhome properties", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, property_type: "TOWNHOUSE", unit: "3" }} />);
    expect(screen.queryByText(/lot size/i)).not.toBeInTheDocument();
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
    expect(screen.getByText(/450 Sanchez St, San Francisco, CA 94114/i)).toBeInTheDocument();
  });

  it("renders the latest lookup_property_by_address result when multiple are present", () => {
    const events = [
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: {
          ...BASE_PROPERTY,
          address_input: "OLD ADDRESS",
          address_matched: "OLD ADDRESS",
          price: 1_000_000,
        } as unknown as Record<string, unknown>,
      },
      {
        type: "tool_result" as const,
        tool: "lookup_property_by_address",
        result: {
          ...BASE_PROPERTY,
          address_input: "NEW ADDRESS",
          address_matched: "NEW ADDRESS",
          price: 1_750_000,
        } as unknown as Record<string, unknown>,
      },
    ];

    render(<AnalysisStream events={events} isRunning={false} />);

    expect(screen.getByText(/NEW ADDRESS/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,750,000/)).toBeInTheDocument();
  });
});
