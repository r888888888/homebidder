import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { HistoryPage } from "./history";
import { ToastProvider } from "../components/Toast";

// Mock TanStack Router
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  Link: ({
    children,
    to,
    search,
    params,
  }: {
    children: React.ReactNode;
    to: string;
    search?: Record<string, string>;
    params?: Record<string, string>;
  }) => {
    // Strip trailing underscores from path segments (TanStack Router non-nesting convention)
    let href = to.replace(/_\//g, "/");
    // Interpolate dynamic params (e.g. $id → 1)
    if (params) {
      href = href.replace(/\$(\w+)/g, (_, key) => params[key] ?? `$${key}`);
    }
    const qs = search ? "?" + new URLSearchParams(search).toString() : "";
    return <a href={`${href}${qs}`}>{children}</a>;
  },
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
  renovation_data: null,
  comps: [],
};

function renderHistoryPage() {
  return render(
    <ToastProvider>
      <HistoryPage />
    </ToastProvider>
  );
}

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
    renderHistoryPage();
    expect(screen.getByRole("heading", { name: /analysis history/i })).toBeInTheDocument();
  });

  it("shows empty state when no analyses exist", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/no saved analyses/i)).toBeInTheDocument()
    );
  });

  it("renders analysis rows with address, date, offer, risk level, investment rating", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
    );
    renderHistoryPage();
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

  it("each row has a permalink link to the saved analysis", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    const links = screen.getAllByRole("link", { name: /view/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links[0]).toHaveAttribute("href", "/analysis/1");
  });

  it("clicking a row fetches detail and renders offer card", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/450 SANCHEZ ST/i));

    await waitFor(() =>
      expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument()
    );
  });

  it("each row has an inline delete button that calls DELETE and removes the row without expanding detail", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    // First delete button corresponds to first row (id=1)
    fireEvent.click(deleteButtons[0]);

    await waitFor(() =>
      expect(screen.queryByText(/450 SANCHEZ ST/i)).not.toBeInTheDocument()
    );
    // Second row should still be present
    expect(screen.getByText(/100 MAIN ST/i)).toBeInTheDocument();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/analyses/1"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("renders FixerAnalysisCard when detail includes renovation_data", async () => {
    const detailWithRenovation = {
      ...ANALYSIS_DETAIL,
      renovation_data: {
        is_fixer: true,
        fixer_signals: ["Fixer / Contractor Special"],
        offer_recommended: 900_000,
        renovation_estimate_low: 65_000,
        renovation_estimate_mid: 88_000,
        renovation_estimate_high: 111_000,
        line_items: [{ category: "Kitchen remodel", low: 35_000, high: 60_000 }],
        all_in_fixer_low: 965_000,
        all_in_fixer_mid: 988_000,
        all_in_fixer_high: 1_011_000,
        turnkey_value: 1_100_000,
        renovated_fair_value: 1_100_000,
        implied_equity_mid: 112_000,
        verdict: "cheaper_fixer" as const,
        savings_mid: 112_000,
        scope_notes: null,
        disclaimer: "Rough estimates only.",
      },
    };

    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(detailWithRenovation), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/450 SANCHEZ ST/i));

    await waitFor(() =>
      expect(screen.getByText(/fixer analysis/i)).toBeInTheDocument()
    );
  });

  it("does not render FixerAnalysisCard when renovation_data is null", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...ANALYSIS_DETAIL, renovation_data: null }), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/450 SANCHEZ ST/i));

    await waitFor(() =>
      expect(screen.getByText(/offer recommendation/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/fixer analysis/i)).not.toBeInTheDocument();
  });

  it("delete button in detail calls DELETE and removes the row", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSIS_DETAIL), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    // Open detail
    fireEvent.click(screen.getByText(/450 SANCHEZ ST/i));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete analysis/i })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /delete analysis/i }));

    await waitFor(() =>
      expect(screen.queryByText(/450 SANCHEZ ST/i)).not.toBeInTheDocument()
    );
  });
});

describe("HistoryPage — error handling", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a toast error when the analyses list fetch fails", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("Network error"));
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/failed to load/i);
  });

  it("shows a toast and keeps row collapsed when detail fetch returns non-2xx", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(new Response("Not found", { status: 500 }));

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/450 SANCHEZ ST/i));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
    expect(screen.queryByText(/offer recommendation/i)).not.toBeInTheDocument();
  });

  it("shows a toast and keeps row in list when delete returns non-2xx", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ANALYSES_LIST), { status: 200 })
      )
      .mockResolvedValueOnce(new Response("Server error", { status: 500 }));

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
    expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument();
  });
});
