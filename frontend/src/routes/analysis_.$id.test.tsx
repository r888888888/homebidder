import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ToastProvider } from "../components/Toast";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useParams: vi.fn(),
  useNavigate: vi.fn(() => vi.fn()),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

import { useParams } from "@tanstack/react-router";
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
});
