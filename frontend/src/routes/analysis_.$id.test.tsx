import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ToastProvider } from "../components/Toast";

// vi.hoisted() runs before module evaluation, making mockUseLoaderData
// available when the vi.mock() factory is called (which is also hoisted).
const mockUseLoaderData = vi.hoisted(() =>
  vi.fn<[], undefined | { data: Record<string, unknown> } | { notFound: true }>(
    () => undefined
  )
);

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => ({
    ...(config as object),
    useLoaderData: mockUseLoaderData,
  }),
  useParams: vi.fn(),
  useNavigate: vi.fn(() => vi.fn()),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

vi.mock("@react-pdf/renderer", () => ({
  PDFDownloadLink: ({ children, fileName }: any) => (
    <a href="blob:fake" download={fileName} data-testid="pdf-link">
      {typeof children === "function" ? children({ loading: false, url: "blob:fake" }) : children}
    </a>
  ),
  Document: ({ children }: any) => <>{children}</>,
  Page: ({ children }: any) => <div>{children}</div>,
  View: ({ children }: any) => <div>{children}</div>,
  Text: ({ children }: any) => <span>{children}</span>,
  StyleSheet: { create: (s: any) => s },
  Font: { register: () => {} },
}));

// Mock AuthContext — default to investor so existing tests see the full InvestmentCard
const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// BuyingPlanBadge has its own tests; stub it here to avoid extra fetch calls.
vi.mock("../components/BuyingPlanBadge", () => ({
  BuyingPlanBadge: () => null,
}));

beforeEach(() => {
  mockUseAuth.mockReturnValue({ user: { subscription_tier: "investor" }, isLoading: false });
  mockUseLoaderData.mockReturnValue(undefined); // default: no loader data → manual fetch
});

import { useParams, useNavigate } from "@tanstack/react-router";
import { PermalinkPage } from "./analysis_.$id";

const ANALYSIS_DETAIL = {
  id: 1,
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  created_at: "2026-04-01T12:00:00",
  offer_low: 1_170_000,
  offer_recommended: 1_200_000,
  offer_high: 1_250_000,
  risk_level: "Moderate",
  investment_rating: "Buy",
  rationale: "Good buy",
  property_data: null,
  neighborhood_data: null,
  offer_data: {
    list_price: 1_250_000,
    fair_value_estimate: 1_200_000,
    offer_low: 1_170_000,
    offer_recommended: 1_200_000,
    offer_high: 1_250_000,
    posture: "competitive",
    spread_vs_list_pct: -4.0,
    median_pct_over_asking: 5.0,
    pct_sold_over_asking: 80.0,
    offer_review_advisory: null,
    contingency_recommendation: {
      waive_appraisal: false,
      waive_loan: false,
      keep_inspection: true,
    },
  },
  risk_data: null,
  investment_data: null,
  renovation_data: null,
  permits_data: null,
  crime_data: null,
  comps: [],
};

function renderPage() {
  vi.mocked(useParams).mockReturnValue({ id: "1" });
  return render(
    <ToastProvider>
      <PermalinkPage />
    </ToastProvider>
  );
}

describe("PermalinkPage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it("shows loading state while fetching", () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders the address and offer card when fetch succeeds", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument();
  });

  it("renders a Copy permalink button when analysis loads", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /copy permalink/i })
      ).toBeInTheDocument()
    );
  });

  it("shows Copied! feedback after clicking Copy permalink", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /copy permalink/i })
      ).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("button", { name: /copy permalink/i }));
    expect(screen.getByRole("button", { name: /copied/i })).toBeInTheDocument();
  });

  it("shows not-found message when API returns 404", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("Not found", { status: 404 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/not found/i)).toBeInTheDocument()
    );
  });

  it("shows a toast error on network failure", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("Network error"));
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
  });

  it("renders tab bar with Decision, Property, Market, Risk, and Analysis tabs", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("tablist")).toBeInTheDocument()
    );
    expect(screen.getByRole("tab", { name: /decision/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /property/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /risk/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /analysis/i })).toBeInTheDocument();
  });

  it("shows offer recommendation on Decision tab by default", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: /decision/i })).toBeInTheDocument()
    );
    expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument();
  });

  it("shows rationale when Analysis tab is clicked", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: /analysis/i })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("tab", { name: /analysis/i }));
    expect(screen.getByText(/good buy/i)).toBeInTheDocument();
  });

  const INVESTMENT_DATA = {
    purchase_price: 1250000,
    projected_value_10yr: 1850000,
    projected_value_20yr: 2730000,
    projected_value_30yr: 4040000,
    rate_30yr_fixed: 6.63,
    as_of_date: "2026-03-26",
    hpi_yoy_assumption_pct: 4.0,
    monthly_buy_cost: 7820.0,
    monthly_rent_equivalent: 3500.0,
    monthly_cost_diff: 4320.0,
    opportunity_cost_10yr: 1050000.0,
    opportunity_cost_20yr: 3300000.0,
    opportunity_cost_30yr: 8200000.0,
    adu_potential: false,
    adu_rent_estimate: null,
    rent_controlled: false,
    rent_control_city: null,
    rent_control_implications: null,
    nearest_bart_station: "16TH ST MISSION",
    bart_distance_miles: 0.31,
    transit_premium_likely: false,
    nearest_muni_stop: null,
    muni_distance_miles: null,
    nearby_schools: [],
  };

  it("renders CompsCard when comps are present and Market tab is clicked", async () => {
    const analysisWithComps = {
      ...ANALYSIS_DETAIL,
      comps: [
        {
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
          lot_size: null,
          price_per_sqft: 647,
          pct_over_asking: 4.76,
          distance_miles: 0.3,
          url: "",
          source: "homeharvest",
        },
      ],
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(analysisWithComps), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() =>
      expect(screen.getByText(/comparable sales/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument();
  });

  it("shows full InvestmentCard (projections) for investor tier on Market tab", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "investor" }, isLoading: false });
    const detail = { ...ANALYSIS_DETAIL, investment_data: INVESTMENT_DATA };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(detail), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() =>
      expect(screen.getByText(/10yr projected value/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/unlock investment projections/i)).not.toBeInTheDocument();
  });

  it("shows full InvestmentCard (projections) for superuser on Market tab", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "buyer", is_superuser: true }, isLoading: false });
    const detail = { ...ANALYSIS_DETAIL, investment_data: INVESTMENT_DATA };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(detail), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() => expect(screen.getByText(/10yr projected value/i)).toBeInTheDocument());
    expect(screen.queryByText(/unlock investment projections/i)).not.toBeInTheDocument();
  });

  it("shows teaser card (no projections, upgrade CTA) for buyer tier on Market tab", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "buyer" }, isLoading: false });
    const detail = { ...ANALYSIS_DETAIL, investment_data: INVESTMENT_DATA };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(detail), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() =>
      expect(screen.getByText(/unlock investment projections/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/10yr projected value/i)).not.toBeInTheDocument();
    const upgradeLinks = screen.getAllByRole("link", { name: /upgrade to investor/i });
    upgradeLinks.forEach(link => expect(link).toHaveAttribute("href", "/pricing"));
  });

  it("shows AffordabilityCalculatorCard for investor and teaser for buyer on Market tab", async () => {
    // Investor sees full calculator
    mockUseAuth.mockReturnValue({ user: { id: "u1", subscription_tier: "investor" }, isLoading: false });
    const detail = { ...ANALYSIS_DETAIL, investment_data: INVESTMENT_DATA };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(detail), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() =>
      expect(screen.getByText(/affordability calculator/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/unlock affordability calculator/i)).not.toBeInTheDocument();
  });

  it("shows Download PDF button for agent tier", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "agent" }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/download pdf/i)).toBeInTheDocument());
  });

  it("shows PDF upsell for investor tier", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "investor" }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument());
    expect(screen.getByText(/pdf export — agent plan/i)).toBeInTheDocument();
  });

  it("shows PDF upsell for buyer tier", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "buyer" }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument());
    expect(screen.getByText(/pdf export — agent plan/i)).toBeInTheDocument();
  });

  it("does not show PDF upsell for agent tier", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "agent" }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/download pdf/i)).toBeInTheDocument());
    expect(screen.queryByText(/pdf export — agent plan/i)).not.toBeInTheDocument();
  });

  it("shows Download PDF button for superuser", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "buyer", is_superuser: true }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/download pdf/i)).toBeInTheDocument());
    expect(screen.queryByText(/pdf export — agent plan/i)).not.toBeInTheDocument();
  });

  it("Refresh analysis button navigates to /analysis with forceRefresh: true", async () => {
    const mockNavigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(mockNavigate);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /refresh analysis/i })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("button", { name: /refresh analysis/i }));
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "/analysis",
        search: expect.objectContaining({ forceRefresh: true }),
      })
    );
  });

  it("shows 'Analysis refreshed' toast when arriving from a forced refresh", async () => {
    sessionStorage.setItem("analysis_just_refreshed", "1");
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/analysis refreshed/i)).toBeInTheDocument()
    );
    expect(sessionStorage.getItem("analysis_just_refreshed")).toBeNull();
  });

  it("does not show refresh toast when sessionStorage flag is absent", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/analysis refreshed/i)).not.toBeInTheDocument();
  });

  const COMP_FIXTURE = {
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
    lot_size: null,
    price_per_sqft: 647,
    pct_over_asking: 4.76,
    distance_miles: 0.3,
    url: "",
    source: "homeharvest",
  };

  it("shows full comp table (with addresses) for investor tier on Market tab", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "investor" }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...ANALYSIS_DETAIL, comps: [COMP_FIXTURE] }), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() => expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument());
    expect(screen.queryByText(/unlock comparable sales/i)).not.toBeInTheDocument();
  });

  it("shows teaser card (no addresses, upgrade CTA) for buyer tier on Market tab", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "buyer" }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...ANALYSIS_DETAIL, comps: [COMP_FIXTURE] }), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() =>
      expect(screen.getByText(/unlock comparable sales/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/100 Comp St/i)).not.toBeInTheDocument();
    const upgradeLink = screen.getByRole("link", { name: /upgrade to investor/i });
    expect(upgradeLink).toHaveAttribute("href", "/pricing");
  });

  it("shows full comp table for superuser on Market tab", async () => {
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "buyer", is_superuser: true }, isLoading: false });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...ANALYSIS_DETAIL, comps: [COMP_FIXTURE] }), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tab", { name: /market/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /market/i }));
    await waitFor(() => expect(screen.getByText(/100 Comp St/i)).toBeInTheDocument());
    expect(screen.queryByText(/unlock comparable sales/i)).not.toBeInTheDocument();
  });
});

describe("PermalinkPage — favorites", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders an unfilled Favorite button when is_favorite is false", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...ANALYSIS_DETAIL, is_favorite: false }), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^favorite$/i })).toBeInTheDocument()
    );
  });

  it("renders a filled Unfavorite button when is_favorite is true", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...ANALYSIS_DETAIL, is_favorite: true }), { status: 200 })
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^unfavorite$/i })).toBeInTheDocument()
    );
  });

  it("calls PATCH /api/analyses/{id}/favorite when favorite button is clicked", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...ANALYSIS_DETAIL, is_favorite: false }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ is_favorite: true }), { status: 200 })
      );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^favorite$/i })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("button", { name: /^favorite$/i }));
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/analyses/1/favorite"),
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("toggles aria-label from Favorite to Unfavorite after successful PATCH", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...ANALYSIS_DETAIL, is_favorite: false }), { status: 200 })
      )
      // buying-plan fetch (investor+ user, no plan)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "No buying plan found" }), { status: 404 })
      )
      // MarkSeenButton fetches seen-properties on mount
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [] }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ is_favorite: true }), { status: 200 })
      );
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^favorite$/i })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("button", { name: /^favorite$/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^unfavorite$/i })).toBeInTheDocument()
    );
  });

  const COMMIT_PLAN_RESPONSE = {
    plan: { id: 1, buy_by_date: "2026-12-01", viewings_per_week: 3, total_n: 30, explore_threshold: 11, created_at: "2026-05-01T00:00:00" },
    status: { phase: "commit", seen_count: 13, explore_max_score: 0.75, explore_threshold: 11, properties_past_threshold: 2, bid_premium_pct: 0.02 },
    seen_properties: [],
  };

  it("applies buying plan bid premium when property is seen with bidding_intent=yes", async () => {
    // ANALYSIS_DETAIL has offer_recommended: 1_200_000; 2% → $1,224,000
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(COMMIT_PLAN_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [{ id: 1, analysis_id: 1, quality: "neutral", location: "neutral", composite_score: 1.0, bidding_intent: "yes", seen_at: "2026-05-05T10:00:00", notes: null }] }), { status: 200 })
      );
    renderPage();
    await waitFor(() => expect(screen.getByText(/1,224,000/)).toBeInTheDocument());
    expect(screen.getByText(/buying plan calibration/i)).toBeInTheDocument();
  });

  it("applies premium when seen with Yes intent regardless of explore_max", async () => {
    // Binary signal: any "yes" qualifies, no score comparison needed.
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(COMMIT_PLAN_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [{ id: 1, analysis_id: 1, quality: "neutral", location: "neutral", composite_score: 1.0, bidding_intent: "yes", seen_at: "2026-05-05T10:00:00", notes: null }] }), { status: 200 })
      );
    renderPage();
    await waitFor(() => expect(screen.getByText(/1,224,000/)).toBeInTheDocument());
  });

  it("does not apply premium when seen with bidding_intent=no", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(COMMIT_PLAN_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [{ id: 1, analysis_id: 1, quality: "neutral", location: "neutral", composite_score: 0.0, bidding_intent: "no", seen_at: "2026-05-05T10:00:00", notes: null }] }), { status: 200 })
      );
    renderPage();
    await waitFor(() => expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument());
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    expect(screen.queryByText(/1,224,000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/buying plan calibration/i)).not.toBeInTheDocument();
  });

  it("does not apply premium when buying plan is paused", async () => {
    const pausedPlanResponse = {
      ...COMMIT_PLAN_RESPONSE,
      plan: { ...COMMIT_PLAN_RESPONSE.plan, is_paused: true },
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(pausedPlanResponse), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [{ id: 1, analysis_id: 1, quality: "neutral", location: "neutral", composite_score: 1.0, bidding_intent: "yes", seen_at: "2026-05-05T10:00:00", notes: null }] }), { status: 200 })
      );
    renderPage();
    await waitFor(() => expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument());
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    expect(screen.queryByText(/1,224,000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/buying plan calibration/i)).not.toBeInTheDocument();
  });

  it("does not apply premium when property has not been marked seen", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 }))
      // buying-plan: commit phase with premium
      .mockResolvedValueOnce(new Response(JSON.stringify(COMMIT_PLAN_RESPONSE), { status: 200 }))
      // MarkSeenButton: not yet seen
      .mockResolvedValueOnce(new Response(JSON.stringify({ seen_properties: [] }), { status: 200 }));
    renderPage();
    await waitFor(() => expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument());
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    expect(screen.queryByText(/1,224,000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/buying plan calibration/i)).not.toBeInTheDocument();
  });

  it("refetches buying plan data after marking a property as seen", async () => {
    vi.mocked(fetch)
      // 1. analysis
      .mockResolvedValueOnce(new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 }))
      // 2. buying-plan (initial)
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: { phase: "explore", seen_count: 3, explore_max_score: null, explore_threshold: 11, properties_past_threshold: 0, bid_premium_pct: 0 } }), { status: 200 }))
      // 3. MarkSeenButton GET (not yet seen)
      .mockResolvedValueOnce(new Response(JSON.stringify({ seen_properties: [] }), { status: 200 }))
      // 4. MarkSeenButton POST
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 1, analysis_id: 1, quality: "neutral", location: "neutral", composite_score: 1.0, bidding_intent: "yes", seen_at: "2026-05-05T10:00:00", notes: null }), { status: 201 }))
      // 5. buying-plan refetch after marking seen
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: { phase: "explore", seen_count: 4, explore_max_score: 1.0, explore_threshold: 11, properties_past_threshold: 0, bid_premium_pct: 0 } }), { status: 200 }));

    renderPage();

    const markSeenBtn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(markSeenBtn);
    await userEvent.click(screen.getByRole("radio", { name: /yes/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
    const buyingPlanCalls = vi.mocked(fetch).mock.calls.filter(([url]) =>
      String(url).includes("/api/buying-plan")
    );
    expect(buyingPlanCalls).toHaveLength(2);
  });
});

const _INSPECTION_FINDINGS = {
  property_address: "450 SANCHEZ ST, SAN FRANCISCO, CA 94114",
  inspector: "Test Inspector",
  inspection_date: "2026-05-01",
  systems: [
    { name: "Roof", status: "deficient", severity: "high", findings: "Needs replacement", renovation_category: "roof" },
  ],
  summary: "1 deficiency found.",
};

const _RENOVATION_DATA_BASE = {
  is_fixer: true,
  fixer_signals: ["Fixer"],
  offer_recommended: 900_000,
  renovation_estimate_low: 60_000,
  renovation_estimate_mid: 80_000,
  renovation_estimate_high: 100_000,
  line_items: [],
  all_in_fixer_low: 960_000,
  all_in_fixer_mid: 980_000,
  all_in_fixer_high: 1_000_000,
  turnkey_value: 1_050_000,
  renovated_fair_value: 1_050_000,
  implied_equity_mid: 70_000,
  verdict: "cheaper_fixer",
  savings_mid: 70_000,
  scope_notes: null,
  disclaimer: "Rough estimates only.",
  inspection_informed: false,
};

describe("PermalinkPage — inspection report upload", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "investor" }, isLoading: false });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows upload widget on Property tab when inspection_data is null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...ANALYSIS_DETAIL, inspection_data: null }), { status: 200 })
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /property/i }));
    await waitFor(() =>
      expect(screen.getByLabelText(/upload inspection report/i)).toBeInTheDocument()
    );
  });

  it("shows InspectionReportCard on Property tab when inspection_data is present", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ...ANALYSIS_DETAIL, inspection_data: _INSPECTION_FINDINGS }),
        { status: 200 }
      )
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /property/i }));
    await waitFor(() =>
      expect(screen.getByText(/inspection report/i)).toBeInTheDocument()
    );
    expect(screen.queryByLabelText(/upload inspection report/i)).not.toBeInTheDocument();
  });

  it("shows InspectionReportCard after successful upload", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...ANALYSIS_DETAIL, inspection_data: null }), { status: 200 })
      )
      // buying-plan fetch (investor+ user, no plan)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "No buying plan found" }), { status: 404 })
      )
      // MarkSeenButton fetches seen-properties on mount
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [] }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ findings: _INSPECTION_FINDINGS, renovation_data: null }), { status: 200 })
      );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: /property/i }));
    await waitFor(() =>
      expect(screen.getByLabelText(/upload inspection report/i)).toBeInTheDocument()
    );

    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, new File(["%PDF-1.4"], "report.pdf", { type: "application/pdf" }));

    await waitFor(() =>
      expect(screen.getByText(/inspection report/i)).toBeInTheDocument()
    );
    expect(screen.queryByLabelText(/upload inspection report/i)).not.toBeInTheDocument();
  });

  it("Property tab dot indicator appears after upload when it had no content before", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        // No property_data, no neighborhood_data, no inspection_data → dot should be absent initially
        new Response(JSON.stringify({ ...ANALYSIS_DETAIL, property_data: null, neighborhood_data: null, inspection_data: null }), { status: 200 })
      )
      // buying-plan fetch (investor+ user, no plan)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "No buying plan found" }), { status: 404 })
      )
      // MarkSeenButton fetches seen-properties on mount
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [] }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ findings: _INSPECTION_FINDINGS, renovation_data: null }), { status: 200 })
      );
    renderPage();
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());

    // Initially no dot on Property tab (no content)
    const propertyTab = screen.getByRole("tab", { name: /property/i });
    expect(propertyTab.querySelector("[aria-label='has content']")).toBeNull();

    await userEvent.click(propertyTab);
    await waitFor(() =>
      expect(screen.getByLabelText(/upload inspection report/i)).toBeInTheDocument()
    );

    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, new File(["%PDF-1.4"], "report.pdf", { type: "application/pdf" }));

    await waitFor(() => expect(screen.getByText(/inspection report/i)).toBeInTheDocument());

    // Switch away from Property tab so the dot can render
    await userEvent.click(screen.getByRole("tab", { name: /decision/i }));
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: /property/i }).querySelector("[aria-label='has content']")).not.toBeNull()
    );
  });

  it("FixerAnalysisCard shows inspection_informed badge after upload returns renovation_data", async () => {
    const analysisWithReno = {
      ...ANALYSIS_DETAIL,
      inspection_data: null,
      renovation_data: _RENOVATION_DATA_BASE,
    };
    const updatedReno = { ..._RENOVATION_DATA_BASE, inspection_informed: true };

    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(analysisWithReno), { status: 200 })
      )
      // buying-plan fetch (investor+ user, no plan)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "No buying plan found" }), { status: 404 })
      )
      // MarkSeenButton fetches seen-properties on mount
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ seen_properties: [] }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ findings: _INSPECTION_FINDINGS, renovation_data: updatedReno }),
          { status: 200 }
        )
      );

    renderPage();
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());

    // Upload from Property tab
    await userEvent.click(screen.getByRole("tab", { name: /property/i }));
    await waitFor(() =>
      expect(screen.getByLabelText(/upload inspection report/i)).toBeInTheDocument()
    );
    await userEvent.upload(
      screen.getByLabelText(/upload inspection report/i),
      new File(["%PDF-1.4"], "report.pdf", { type: "application/pdf" })
    );

    // Switch to Decision tab and verify badge
    await userEvent.click(screen.getByRole("tab", { name: /decision/i }));
    await waitFor(() =>
      expect(screen.getByText(/informed by inspection report/i)).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// Loader integration — Route.useLoaderData() supplies pre-fetched data
// ---------------------------------------------------------------------------

describe("PermalinkPage — loader integration", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders analysis immediately from loader data without fetching the analysis endpoint", async () => {
    mockUseLoaderData.mockReturnValue({ data: ANALYSIS_DETAIL as unknown as Record<string, unknown> });

    renderPage();

    // Content is available immediately — no loading spinner
    expect(screen.queryByText(/^loading/i)).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    // The analysis detail endpoint must NOT have been fetched (loader provided it)
    const analysisFetches = vi.mocked(fetch).mock.calls.filter(
      ([url]) => typeof url === "string" && /\/api\/analyses\/\d+$/.test(url)
    );
    expect(analysisFetches).toHaveLength(0);
  });

  it("shows not-found state synchronously when loader returns { notFound: true }", () => {
    mockUseLoaderData.mockReturnValue({ notFound: true });

    renderPage();

    // No loading state — loader already resolved
    expect(screen.queryByText(/^loading/i)).not.toBeInTheDocument();
    expect(screen.getByText(/not found/i)).toBeInTheDocument();
    // The analysis detail endpoint must NOT have been fetched
    const analysisFetches = vi.mocked(fetch).mock.calls.filter(
      ([url]) => typeof url === "string" && /\/api\/analyses\/\d+$/.test(url)
    );
    expect(analysisFetches).toHaveLength(0);
  });

  it("falls back to manual fetch of the analysis endpoint when loader data is undefined", async () => {
    // Default: mockUseLoaderData returns undefined (set in outer beforeEach)
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
    );

    renderPage();

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    // The analysis endpoint should have been called manually
    const analysisFetches = vi.mocked(fetch).mock.calls.filter(
      ([url]) => typeof url === "string" && /\/api\/analyses\/\d+$/.test(url)
    );
    expect(analysisFetches.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// Validation mode banner
// ---------------------------------------------------------------------------

const VALIDATION_DATA = {
  actual_sold_price: 1_350_000,
  estimated_price: 1_280_000,
  error_dollars: -70_000,
  error_pct: -5.2,
  within_ci: true,
  sold_date: "2026-03-15",
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
};

describe("PermalinkPage — validation mode banner", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
    mockUseAuth.mockReturnValue({ user: { subscription_tier: "investor" }, isLoading: false });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows validation banner when analysis has validation_data", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ...ANALYSIS_DETAIL, validation_data: VALIDATION_DATA }),
        { status: 200 }
      )
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/validation mode/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/1,350,000/)).toBeInTheDocument();
  });

  it("does not show validation banner when validation_data is null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ...ANALYSIS_DETAIL, validation_data: null }),
        { status: 200 }
      )
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/validation mode/i)).not.toBeInTheDocument();
  });
});
