import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ToastProvider } from "../components/Toast";
import { ComparePage } from "./compare";

vi.mock("../lib/AuthContext", () => ({
  useAuth: () => ({ user: { subscription_tier: "investor" }, isLoading: false }),
}));

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  Link: ({
    children,
    to,
    params,
  }: {
    children: React.ReactNode;
    to: string;
    params?: Record<string, string>;
  }) => {
    let href = to.replace(/_\//g, "/");
    if (params) {
      href = href.replace(/\$(\w+)/g, (_, key) => params[key] ?? `$${key}`);
    }
    return <a href={href}>{children}</a>;
  },
}));

const FAVORITES_PAGE = {
  items: [
    {
      id: 1,
      address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
      created_at: "2026-04-01T12:00:00",
      offer_recommended: 1_200_000,
      risk_level: "Moderate",
      investment_rating: "Buy",
      is_favorite: true,
    },
    {
      id: 2,
      address: "100 MAIN ST, OAKLAND, CA, 94607",
      created_at: "2026-03-28T08:00:00",
      offer_recommended: 850_000,
      risk_level: "Low",
      investment_rating: "Hold",
      is_favorite: true,
    },
    {
      id: 3,
      address: "88 HOFF ST APT 104, SAN FRANCISCO, CA, 94110",
      created_at: "2026-03-20T08:00:00",
      offer_recommended: 950_000,
      risk_level: "High",
      investment_rating: "Hold",
      is_favorite: true,
    },
  ],
  total: 3,
  limit: 100,
  offset: 0,
};

const EMPTY_FAVORITES = { items: [], total: 0, limit: 100, offset: 0 };

const ANALYSIS_1 = {
  id: 1,
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  created_at: "2026-04-01T12:00:00",
  offer_low: 1_170_000,
  offer_recommended: 1_200_000,
  offer_high: 1_250_000,
  risk_level: "Moderate",
  investment_rating: "Buy",
  is_favorite: true,
  property_data: {
    sqft: 1500,
    bedrooms: 3,
    bathrooms: 2,
    lot_size: 2800,
    city: "San Francisco",
    neighborhoods: "Castro, Eureka Valley",
  },
  offer_data: { list_price: 1_250_000, fair_value_estimate: 1_200_000 },
  risk_data: { overall_risk: "Moderate" },
  renovation_data: { renovation_estimate_mid: 50000 },
  comps: [],
};

const ANALYSIS_2 = {
  id: 2,
  address: "100 MAIN ST, OAKLAND, CA, 94607",
  created_at: "2026-03-28T08:00:00",
  offer_low: 820_000,
  offer_recommended: 850_000,
  offer_high: 880_000,
  risk_level: "Low",
  investment_rating: "Hold",
  is_favorite: true,
  property_data: {
    sqft: 1000,
    bedrooms: 2,
    bathrooms: 1.5,
    lot_size: null,
    city: "Oakland",
    neighborhoods: "Jack London Square",
  },
  offer_data: { list_price: 875_000, fair_value_estimate: 850_000 },
  risk_data: { overall_risk: "Low" },
  renovation_data: null,
  comps: [],
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderCompare() {
  return render(
    <ToastProvider>
      <ComparePage />
    </ToastProvider>
  );
}

describe("ComparePage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the Compare heading", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(EMPTY_FAVORITES));
    renderCompare();
    expect(
      screen.getByRole("heading", { name: /compare/i })
    ).toBeInTheDocument();
  });

  it("requests only favorited analyses on mount", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(EMPTY_FAVORITES));
    renderCompare();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/analyses");
    expect(calledUrl).toContain("favorites=true");
  });

  it("shows an empty state with a link to history when there are no favorites", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(EMPTY_FAVORITES));
    renderCompare();
    await waitFor(() =>
      expect(screen.getByText(/no favorited analyses yet/i)).toBeInTheDocument()
    );
    const links = screen.getAllByRole("link", { name: /history/i });
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]).toHaveAttribute("href", "/history");
  });

  it("renders one selectable row per favorited analysis", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(FAVORITES_PAGE));
    renderCompare();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/100 MAIN ST/i)).toBeInTheDocument();
    expect(screen.getByText(/88 HOFF ST/i)).toBeInTheDocument();
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);
  });

  it("disables the Compare button until at least 2 favorites are selected", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(FAVORITES_PAGE));
    renderCompare();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const button = screen.getByRole("button", { name: /^compare/i });
    expect(button).toBeDisabled();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    expect(button).toBeDisabled();

    fireEvent.click(checkboxes[1]);
    expect(button).toBeEnabled();
  });

  it("prevents selecting more than 4 favorites", async () => {
    const fiveFavorites = {
      items: [
        ...FAVORITES_PAGE.items,
        {
          id: 4,
          address: "1 ELM ST, SF, CA 94110",
          created_at: "2026-03-10T08:00:00",
          offer_recommended: 700_000,
          risk_level: "Low",
          investment_rating: "Buy",
          is_favorite: true,
        },
        {
          id: 5,
          address: "2 OAK ST, SF, CA 94110",
          created_at: "2026-03-09T08:00:00",
          offer_recommended: 720_000,
          risk_level: "Low",
          investment_rating: "Buy",
          is_favorite: true,
        },
      ],
      total: 5,
      limit: 100,
      offset: 0,
    };
    vi.mocked(fetch).mockResolvedValue(jsonResponse(fiveFavorites));
    renderCompare();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(checkboxes[2]);
    fireEvent.click(checkboxes[3]);

    expect(checkboxes[4]).toBeDisabled();
    expect(checkboxes[0]).not.toBeDisabled();
  });

  it("fetches details for selected analyses and renders a comparison row for each", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(FAVORITES_PAGE))
      .mockResolvedValueOnce(jsonResponse(ANALYSIS_1))
      .mockResolvedValueOnce(jsonResponse(ANALYSIS_2));

    renderCompare();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);

    fireEvent.click(screen.getByRole("button", { name: /^compare/i }));

    await waitFor(() =>
      expect(screen.getAllByText(/450 SANCHEZ ST/i).length).toBeGreaterThan(0)
    );

    // Comparison column headers show both addresses
    expect(screen.getAllByText(/100 MAIN ST/i).length).toBeGreaterThan(0);

    // Property attributes appear as comparison rows
    expect(screen.getByText(/^city$/i)).toBeInTheDocument();
    expect(screen.getByText(/^neighborhood$/i)).toBeInTheDocument();
    expect(screen.getByText(/beds \/ baths/i)).toBeInTheDocument();
    expect(screen.getByText(/^sqft$/i)).toBeInTheDocument();
    expect(screen.getByText(/^lot size$/i)).toBeInTheDocument();

    // Pricing + risk rows are kept
    expect(screen.getByText(/list price/i)).toBeInTheDocument();
    expect(screen.getByText(/recommended offer/i)).toBeInTheDocument();
    expect(screen.getByText(/\$\/sqft/i)).toBeInTheDocument();
    expect(screen.getByText(/risk level/i)).toBeInTheDocument();

    // Investment-projection rows are removed
    expect(screen.queryByText(/investment rating/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^renovation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/monthly buy cost/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/monthly rent equiv/i)).not.toBeInTheDocument();

    // Cell values render correctly
    expect(screen.getByText("San Francisco")).toBeInTheDocument();
    expect(screen.getByText("Oakland")).toBeInTheDocument();
    expect(screen.getByText(/castro, eureka valley/i)).toBeInTheDocument();
    expect(screen.getByText(/3 bd \/ 2 ba/i)).toBeInTheDocument();
    expect(screen.getByText(/2 bd \/ 1\.5 ba/i)).toBeInTheDocument();

    // Each detail endpoint was fetched
    const detailCalls = vi.mocked(fetch).mock.calls.filter(([url]) =>
      /\/api\/analyses\/\d+($|\?)/.test(url as string)
    );
    expect(detailCalls).toHaveLength(2);
  });

  it("shows a back-to-selection control after rendering the comparison", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(FAVORITES_PAGE))
      .mockResolvedValueOnce(jsonResponse(ANALYSIS_1))
      .mockResolvedValueOnce(jsonResponse(ANALYSIS_2));

    renderCompare();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: /^compare/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /change selection/i })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /change selection/i }));
    await waitFor(() =>
      expect(screen.getAllByRole("checkbox").length).toBeGreaterThan(0)
    );
  });
});
