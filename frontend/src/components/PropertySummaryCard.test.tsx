import { render, screen, fireEvent } from "@testing-library/react";
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
  listing_url: "https://www.realtor.com/realestateandhomes-detail/450-Sanchez-St_San-Francisco_CA_94114_M89012-34567/",
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
  avm_estimate: null,
  listing_description: null,
  description_signals: {
    version: "v1",
    raw_description_present: false,
    detected_signals: [],
    net_adjustment_pct: 0,
  },
  source: "homeharvest" as const,
};

describe("PropertySummaryCard", () => {
  it("renders address and key fields", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);

    expect(screen.getByText(/450 Sanchez St, San Francisco, CA 94114/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,250,000/)).toBeInTheDocument();
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

  it("renders fallback value for null list price", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, price: null }} />);

    const dt = screen.getByText(/^list price$/i);
    expect(dt.nextElementSibling?.textContent).toBe("—");
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

  it("renders description signal chips only when detected", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          description_signals: {
            version: "v1",
            raw_description_present: true,
            net_adjustment_pct: -1.5,
            detected_signals: [
              { label: "Fixer / Contractor Special", direction: "negative" },
              { label: "Tenant Occupied", direction: "negative" },
            ],
          },
        }}
      />
    );

    expect(screen.getByText(/fixer/i)).toBeInTheDocument();
    expect(screen.getByText(/tenant occupied/i)).toBeInTheDocument();
  });

  it("hides description signal chips when there are none", () => {
    render(<PropertySummaryCard property={BASE_PROPERTY} />);
    expect(screen.queryByText(/description signals/i)).not.toBeInTheDocument();
  });

  it("renders listing description when present", () => {
    const desc = "Charming Victorian with original hardwood floors and modern kitchen.";
    render(
      <PropertySummaryCard
        property={{ ...BASE_PROPERTY, listing_description: desc }}
      />
    );
    expect(screen.getByText(desc)).toBeInTheDocument();
  });

  it("hides listing description section when null", () => {
    render(<PropertySummaryCard property={{ ...BASE_PROPERTY, listing_description: null }} />);
    expect(screen.queryByText(/listing description/i)).not.toBeInTheDocument();
  });

  it("does not show Show more button for short descriptions", () => {
    const short = "Charming Victorian with original hardwood floors.";
    render(
      <PropertySummaryCard property={{ ...BASE_PROPERTY, listing_description: short }} />
    );
    expect(screen.queryByRole("button", { name: /show more/i })).not.toBeInTheDocument();
  });

  it("shows Show more button for long descriptions", () => {
    const long = "A".repeat(181);
    render(
      <PropertySummaryCard property={{ ...BASE_PROPERTY, listing_description: long }} />
    );
    expect(screen.getByRole("button", { name: /show more/i })).toBeInTheDocument();
  });

  it("clicking Show more reveals Show less and collapses again", () => {
    const long = "A".repeat(181);
    render(
      <PropertySummaryCard property={{ ...BASE_PROPERTY, listing_description: long }} />
    );
    fireEvent.click(screen.getByRole("button", { name: /show more/i }));
    expect(screen.getByRole("button", { name: /show less/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /show more/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /show less/i }));
    expect(screen.getByRole("button", { name: /show more/i })).toBeInTheDocument();
  });

  it("renders AI fixer badge when llm is used with negative adjustment", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          description_signals: {
            ...BASE_PROPERTY.description_signals,
            llm: { used: true, confidence: 0.87, model: "claude-haiku", adjustment_pct: -0.8 },
          },
        }}
      />
    );
    expect(screen.getByText(/ai.*fixer/i)).toBeInTheDocument();
    expect(screen.getByText(/87%/)).toBeInTheDocument();
  });

  it("renders AI move-in ready badge when llm is used with positive adjustment", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          description_signals: {
            ...BASE_PROPERTY.description_signals,
            llm: { used: true, confidence: 0.92, model: "claude-haiku", adjustment_pct: 0.6 },
          },
        }}
      />
    );
    expect(screen.getByText(/ai.*move.?in ready/i)).toBeInTheDocument();
    expect(screen.getByText(/92%/)).toBeInTheDocument();
  });

  it("hides AI badge when llm is not used", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          description_signals: {
            ...BASE_PROPERTY.description_signals,
            llm: { used: false, confidence: null, model: null, adjustment_pct: 0 },
          },
        }}
      />
    );
    expect(screen.queryByText(/^ai:/i)).not.toBeInTheDocument();
  });

  it("hides AI badge when llm adjustment is zero", () => {
    render(
      <PropertySummaryCard
        property={{
          ...BASE_PROPERTY,
          description_signals: {
            ...BASE_PROPERTY.description_signals,
            llm: { used: true, confidence: 0.75, model: "claude-haiku", adjustment_pct: 0 },
          },
        }}
      />
    );
    expect(screen.queryByText(/^ai:/i)).not.toBeInTheDocument();
  });

  describe("photo gallery", () => {
    it("renders images when photos array is provided", () => {
      render(
        <PropertySummaryCard
          property={{
            ...BASE_PROPERTY,
            photos: [
              "https://ap.rdcpix.com/abc/img1.jpg",
              "https://ap.rdcpix.com/abc/img2.jpg",
            ],
          }}
        />
      );
      const images = screen.getAllByRole("img");
      expect(images.length).toBeGreaterThanOrEqual(2);
      expect(images[0]).toHaveAttribute("src", "https://ap.rdcpix.com/abc/img1.jpg");
      expect(images[1]).toHaveAttribute("src", "https://ap.rdcpix.com/abc/img2.jpg");
    });

    it("does not render gallery section when photos is null", () => {
      render(<PropertySummaryCard property={{ ...BASE_PROPERTY, photos: null }} />);
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    });

    it("does not render gallery section when photos is empty array", () => {
      render(<PropertySummaryCard property={{ ...BASE_PROPERTY, photos: [] }} />);
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    });

    it("does not render gallery section when photos is omitted", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    });
  });

  describe("sold listing fallback source display", () => {
    it("shows 'List Price' label for active for-sale listings", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      expect(screen.getByText("List Price")).toBeInTheDocument();
    });

    it("shows 'Last Sold Price' label when source is homeharvest_sold", () => {
      render(
        <PropertySummaryCard property={{ ...BASE_PROPERTY, source: "homeharvest_sold" }} />
      );
      expect(screen.getByText("Last Sold Price")).toBeInTheDocument();
      expect(screen.queryByText("List Price")).not.toBeInTheDocument();
    });

    it("shows 'Recent Sale' source indicator when source is homeharvest_sold", () => {
      render(
        <PropertySummaryCard property={{ ...BASE_PROPERTY, source: "homeharvest_sold" }} />
      );
      expect(screen.getByText(/Recent Sale/)).toBeInTheDocument();
    });
  });

  describe("external listing links", () => {
    it("renders Zillow link with address slug in href", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      const link = screen.getByRole("link", { name: /zillow/i });
      expect(link).toHaveAttribute("href", expect.stringContaining("zillow.com"));
      expect(link).toHaveAttribute("href", expect.stringContaining("450-sanchez-st"));
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    });

    it("renders Redfin link pointing to zip code search", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      const link = screen.getByRole("link", { name: /redfin/i });
      expect(link).toHaveAttribute("href", expect.stringContaining("redfin.com"));
      expect(link).toHaveAttribute("href", expect.stringContaining("94114"));
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("renders Realtor link using listing_url from backend", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      const link = screen.getByRole("link", { name: /realtor/i });
      expect(link).toHaveAttribute(
        "href",
        "https://www.realtor.com/realestateandhomes-detail/450-Sanchez-St_San-Francisco_CA_94114_M89012-34567/"
      );
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("renders Realtor link using constructed URL when listing_url is absent", () => {
      render(<PropertySummaryCard property={{ ...BASE_PROPERTY, listing_url: null }} />);
      const link = screen.getByRole("link", { name: /realtor/i });
      expect(link).toHaveAttribute("href", expect.stringContaining("realtor.com"));
      expect(link).toHaveAttribute("href", expect.stringContaining("450-Sanchez-St"));
      expect(link).toHaveAttribute("href", expect.stringContaining("94114"));
    });

    it("renders Street View link with lat/lng in href", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      const link = screen.getByRole("link", { name: /street view/i });
      expect(link).toHaveAttribute("href", expect.stringContaining("google.com/maps"));
      expect(link).toHaveAttribute("href", expect.stringContaining("37.7612"));
      expect(link).toHaveAttribute("href", expect.stringContaining("-122.4313"));
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("renders Google Maps link with lat/lng search query in href", () => {
      render(<PropertySummaryCard property={BASE_PROPERTY} />);
      const link = screen.getByRole("link", { name: /google maps/i });
      expect(link).toHaveAttribute("href", expect.stringContaining("google.com/maps/search"));
      expect(link).toHaveAttribute("href", expect.stringContaining("37.7612"));
      expect(link).toHaveAttribute("href", expect.stringContaining("-122.4313"));
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    });
  });
});
