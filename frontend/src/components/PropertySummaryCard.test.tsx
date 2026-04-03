import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PropertySummaryCard } from "./PropertySummaryCard";

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
  it("renders address and key fields", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);

    expect(screen.getByText(/450 Sanchez St, San Francisco, CA 94114/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,250,000/)).toBeInTheDocument();
    expect(screen.getByText(/\$1,300,000/)).toBeInTheDocument();
    expect(screen.getByText(/\+4\.0%|\+\$50,000/i)).toBeInTheDocument();
    expect(screen.getByText(/single.?family/i)).toBeInTheDocument();
    expect(screen.getByText(/2,500/)).toBeInTheDocument();

    const bedsDt = screen.getByText(/^beds$/i);
    const bathsDt = screen.getByText(/^baths$/i);
    const domDt = screen.getByText(/days on market/i);
    expect(bedsDt.nextElementSibling?.textContent).toBe("3");
    expect(bathsDt.nextElementSibling?.textContent).toBe("2");
    expect(domDt.nextElementSibling?.textContent).toBe("5 days");
  });

  it("shows the normalized matched address with inferred unit when needed", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          address_input: "821 Folsom St #515, San Francisco, CA 94107",
          address_matched: "821 FOLSOM ST, SAN FRANCISCO, CA, 94107",
        }}
      />
    );

    expect(screen.getByText(/821 Folsom St #515, San Francisco, CA 94107/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Matched as:\s*821 FOLSOM ST UNIT 515, SAN FRANCISCO, CA, 94107/i)
    ).toBeInTheDocument();
  });

  it.each([
    {
      name: "null list price",
      patch: { price: null },
      label: /^list price$/i,
      value: "—",
    },
    {
      name: "null AVM",
      patch: { avm_estimate: null },
      text: /N\/A/i,
    },
  ])("renders fallback values for $name", ({ patch, label, value, text }) => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, ...patch }} />);

    if (text) {
      expect(screen.getByText(text)).toBeInTheDocument();
      return;
    }

    const dt = screen.getByText(label!);
    expect(dt.nextElementSibling?.textContent).toBe(value);
  });

  it.each([
    {
      name: "under 24 hours",
      patch: {
        list_date: new Date(Date.now() - 5 * 60 * 60 * 1000)
          .toISOString()
          .replace("T", " ")
          .slice(0, 19),
        days_on_market: 0,
      },
      expected: /5\s*h(r|our)/i,
    },
    {
      name: "multiple days",
      patch: {
        list_date: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000)
          .toISOString()
          .replace("T", " ")
          .slice(0, 19),
        days_on_market: 3,
      },
      expected: /3 days/i,
    },
    {
      name: "stale provider date",
      patch: { list_date: "2017-10-22 07:00:00", days_on_market: 0 },
      expected: /0 days/i,
    },
    {
      name: "missing list date",
      patch: { list_date: null, days_on_market: 7 },
      expected: /7 days/i,
    },
  ])("formats days-on-market using $name", ({ patch, expected }) => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, ...patch }} />);
    const dt = screen.getByText(/days on market/i);
    expect(dt.nextElementSibling?.textContent).toMatch(expected);
  });

  it.each([
    {
      name: "unit is set",
      patch: { unit: "1206" },
      unitVisible: true,
    },
    {
      name: "unit is null",
      patch: { unit: null },
      unitVisible: false,
    },
  ])("shows unit field only when present: $name", ({ patch, unitVisible }) => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, ...patch }} />);

    if (unitVisible) {
      const dt = screen.getByText(/^unit$/i);
      expect(dt.nextElementSibling?.textContent).toBe("1206");
    } else {
      expect(screen.queryByText(/^unit$/i)).not.toBeInTheDocument();
    }
  });

  it.each([
    { property_type: "SINGLE_FAMILY", unit: null, hasLotSize: true },
    { property_type: "CONDO", unit: "5B", hasLotSize: false },
    { property_type: "TOWNHOUSE", unit: "3", hasLotSize: false },
  ])("shows lot size only for detached properties (%s)", ({ property_type, unit, hasLotSize }) => {
    render(
      <PropertySummaryCard property={{ ...BASE_PROPERTY, property_type, unit }} />
    );

    if (hasLotSize) {
      expect(screen.getByText(/lot size/i)).toBeInTheDocument();
    } else {
      expect(screen.queryByText(/lot size/i)).not.toBeInTheDocument();
    }
  });

  it("uses the requested property summary layout order", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);

    const labels = screen
      .getAllByRole("term")
      .map((node) => node.textContent?.trim().toLowerCase() ?? "");

    expect(labels).toEqual([
      "list price",
      "avm estimate",
      "hoa / mo",
      "beds",
      "baths",
      "type",
      "sqft",
      "lot size (sqft)",
      "year built",
      "city",
      "county",
      "days on market",
    ]);

    const grid = document.querySelector("dl");
    expect(grid).toHaveClass("sm:grid-cols-3");
  });
});
