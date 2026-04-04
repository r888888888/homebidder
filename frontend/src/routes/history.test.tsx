import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { HistoryPage } from "./history";

// Mock TanStack Router
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const ANALYSES_LIST = [
  {
    id: 1,
    address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
    created_at: "2026-04-01T12:00:00",
    offer_recommended: 1_200_000,
    risk_level: "Moderate",
    investment_rating: "Buy",
  },
  {
    id: 2,
    address: "100 MAIN ST, OAKLAND, CA, 94607",
    created_at: "2026-03-28T08:00:00",
    offer_recommended: null,
    risk_level: "Low",
    investment_rating: "Hold",
  },
];

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
  comps: [],
};

describe("HistoryPage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the Analysis History heading", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 })
    );
    render(<HistoryPage />);
    expect(screen.getByRole("heading", { name: /analysis history/i })).toBeInTheDocument();
  });

  it("shows empty state when no analyses exist", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 })
    );
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.getByText(/no saved analyses/i)).toBeInTheDocument()
    );
  });

  it("renders analysis rows with address, date, offer, risk level, investment rating", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
    );
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/100 MAIN ST/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1,200,000/)).toBeInTheDocument();
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(screen.getAllByText("Buy").length).toBeGreaterThan(0);
    // Second row has null offer_recommended — shows dash
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("clicking a row fetches detail and renders offer card", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
      );

    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/450 SANCHEZ ST/i));

    await waitFor(() =>
      expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument()
    );
  });
});
