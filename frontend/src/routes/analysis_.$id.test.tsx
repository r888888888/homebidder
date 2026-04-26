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
});
