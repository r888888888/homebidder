import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { HistoryPage } from "./history";
import { ToastProvider } from "../components/Toast";

// Mutable so individual describe blocks can set the active user.
let _mockAuthUser: Record<string, unknown> | null = null;

vi.mock("../lib/AuthContext", () => ({
  useAuth: () => ({ user: _mockAuthUser, isLoading: false }),
}));

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
    is_favorite: false,
  },
  {
    id: 2,
    address: "100 MAIN ST, OAKLAND, CA, 94607",
    created_at: "2026-03-28T08:00:00",
    offer_recommended: null,
    risk_level: "Low",
    investment_rating: "Hold",
    is_favorite: false,
  },
];

// Paginated envelope wrappers used by all tests
const PAGE_1 = { items: ANALYSES_LIST, total: 2, limit: 20, offset: 0 };
const PAGE_1_EMPTY = { items: [], total: 0, limit: 20, offset: 0 };
// Simulate 25 total analyses so there is a second page
const PAGE_1_LARGE = { items: ANALYSES_LIST, total: 25, limit: 20, offset: 0 };
const PAGE_2_LARGE = { items: ANALYSES_LIST, total: 25, limit: 20, offset: 20 };

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
      new Response(JSON.stringify(PAGE_1_EMPTY), { status: 200 })
    );
    renderHistoryPage();
    expect(screen.getByRole("heading", { name: /analysis history/i })).toBeInTheDocument();
  });

  it("links to the /compare page so users can compare favorited analyses", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1_EMPTY), { status: 200 })
    );
    renderHistoryPage();
    const compareLink = screen.getByRole("link", { name: /compare/i });
    expect(compareLink).toHaveAttribute("href", "/compare");
  });

  it("shows empty state when no analyses exist", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1_EMPTY), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/no saved analyses/i)).toBeInTheDocument()
    );
  });

  it("renders analysis rows with address, date, offer, risk level, investment rating", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1), { status: 200 })
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
      new Response(JSON.stringify(PAGE_1), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    const links = screen.getAllByRole("link", { name: /view/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links[0]).toHaveAttribute("href", "/analysis/1");
  });

  it("each row has an inline delete button that calls DELETE and removes the row without expanding detail", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1), { status: 200 })
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

  it("does not show pagination controls when total fits on one page", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /next/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /prev/i })).not.toBeInTheDocument();
  });

  it("shows Next button and page indicator when total > limit", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1_LARGE), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
  });

  it("Prev button is hidden on the first page", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1_LARGE), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /prev/i })).not.toBeInTheDocument();
  });

  it("clicking Next fetches the second page with offset=20", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1_LARGE), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_2_LARGE), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(screen.getByText(/page 2 of 2/i)).toBeInTheDocument()
    );
    // Confirm offset=20 was sent
    const calls = vi.mocked(fetch).mock.calls;
    expect(calls[1][0]).toMatch(/offset=20/);
  });

  it("shows Prev button on page 2 and clicking it goes back to page 1", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1_LARGE), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_2_LARGE), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1_LARGE), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /prev/i })).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /prev/i }));
    await waitFor(() =>
      expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /prev/i })).not.toBeInTheDocument();
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

  it("shows a toast and keeps row in list when delete returns non-2xx", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1), { status: 200 })
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

// ---------------------------------------------------------------------------
// Retention banner tests — use _mockAuthUser to control the active user tier
// ---------------------------------------------------------------------------

const EMPTY_PAGE = { items: [], total: 0, limit: 20, offset: 0 };

describe("HistoryPage — retention banner (buyer)", () => {
  beforeEach(() => {
    _mockAuthUser = { subscription_tier: "buyer", is_grandfathered: false };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(EMPTY_PAGE), { status: 200 })
    );
  });
  afterEach(() => {
    _mockAuthUser = null;
    vi.restoreAllMocks();
  });

  it("shows 30-day retention notice for buyer tier", async () => {
    render(<ToastProvider><HistoryPage /></ToastProvider>);
    await waitFor(() =>
      expect(screen.getByText(/30 days/i)).toBeInTheDocument()
    );
  });

  it("shows upgrade-to-investor CTA link for buyer tier", async () => {
    render(<ToastProvider><HistoryPage /></ToastProvider>);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /investor/i })).toBeInTheDocument()
    );
  });
});

describe("HistoryPage — retention banner (investor)", () => {
  beforeEach(() => {
    _mockAuthUser = { subscription_tier: "investor", is_grandfathered: false };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(EMPTY_PAGE), { status: 200 })
    );
  });
  afterEach(() => {
    _mockAuthUser = null;
    vi.restoreAllMocks();
  });

  it("shows 6-month retention notice for investor tier", async () => {
    render(<ToastProvider><HistoryPage /></ToastProvider>);
    await waitFor(() =>
      expect(screen.getByText(/6 months/i)).toBeInTheDocument()
    );
  });

  it("shows upgrade-to-agent CTA link for investor tier", async () => {
    render(<ToastProvider><HistoryPage /></ToastProvider>);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /agent/i })).toBeInTheDocument()
    );
  });
});

describe("HistoryPage — retention banner (agent)", () => {
  beforeEach(() => {
    _mockAuthUser = { subscription_tier: "agent", is_grandfathered: false };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(EMPTY_PAGE), { status: 200 })
    );
  });
  afterEach(() => {
    _mockAuthUser = null;
    vi.restoreAllMocks();
  });

  it("does not show a retention banner for agent tier", async () => {
    render(<ToastProvider><HistoryPage /></ToastProvider>);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /analysis history/i })).toBeInTheDocument()
    );
    expect(screen.queryByText(/30 days/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/6 months/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

describe("HistoryPage — favorites", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a favorite button for each analysis row", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(PAGE_1), { status: 200 })
    );
    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );
    const favButtons = screen.getAllByRole("button", { name: /favorite/i });
    expect(favButtons.length).toBe(2);
  });

  it("calls PATCH /api/analyses/{id}/favorite when favorite button is clicked", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ is_favorite: true }), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    const favButtons = screen.getAllByRole("button", { name: /favorite/i });
    fireEvent.click(favButtons[0]);

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/analyses/1/favorite"),
        expect.objectContaining({ method: "PATCH" })
      )
    );
  });

  it("updates aria-label from Favorite to Unfavorite after toggling on", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(PAGE_1), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ is_favorite: true }), { status: 200 })
      );

    renderHistoryPage();
    await waitFor(() =>
      expect(screen.getByText(/450 SANCHEZ ST/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getAllByRole("button", { name: /^favorite$/i })[0]);

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: /unfavorite/i }).length).toBeGreaterThan(0)
    );
  });

  describe("address search", () => {
    it("renders a search input", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify(PAGE_1_EMPTY), { status: 200 })
      );
      renderHistoryPage();
      expect(screen.getByPlaceholderText(/search by address/i)).toBeInTheDocument();
    });

    it("typing in the search input calls the API with q param", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify(PAGE_1_EMPTY), { status: 200 })
      );
      renderHistoryPage();
      await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

      const searchInput = screen.getByPlaceholderText(/search by address/i);
      fireEvent.change(searchInput, { target: { value: "Sanchez" } });

      await waitFor(() => {
        const calls = vi.mocked(fetch).mock.calls;
        expect(calls.some(([url]) => (url as string).includes("q=Sanchez"))).toBe(true);
      });
    });

    it("clearing the search input drops the q param", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify(PAGE_1_EMPTY), { status: 200 })
      );
      renderHistoryPage();
      await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

      const searchInput = screen.getByPlaceholderText(/search by address/i);
      fireEvent.change(searchInput, { target: { value: "Sanchez" } });
      await waitFor(() => {
        const calls = vi.mocked(fetch).mock.calls;
        expect(calls.some(([url]) => (url as string).includes("q=Sanchez"))).toBe(true);
      });

      fireEvent.change(searchInput, { target: { value: "" } });
      await waitFor(() => {
        const calls = vi.mocked(fetch).mock.calls;
        const lastUrl = calls[calls.length - 1][0] as string;
        expect(lastUrl).not.toContain("q=");
      });
    });
  });
});
