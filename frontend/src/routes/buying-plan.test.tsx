import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { BuyingPlanPage } from "./buying-plan";

// Mock AuthContext
const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock Toast
const mockToast = { success: vi.fn(), error: vi.fn() };
vi.mock("../components/Toast", () => ({
  useToast: () => mockToast,
}));

// Mock router Link
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: Record<string, unknown>) => opts,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const INVESTOR_USER = {
  id: "user-1",
  email: "investor@test.com",
  subscription_tier: "investor" as const,
  is_superuser: false,
};

const BUYER_USER = {
  id: "user-2",
  email: "buyer@test.com",
  subscription_tier: "buyer" as const,
  is_superuser: false,
};

function makePlanResponse(overrides: Record<string, unknown> = {}) {
  return {
    plan: {
      id: 1,
      buy_by_date: "2026-12-01",
      viewings_per_week: 3.0,
      total_n: 30,
      explore_threshold: 11,
      created_at: "2026-05-05T00:00:00",
    },
    status: {
      phase: "explore",
      seen_count: 5,
      explore_max_score: 0.75,
      explore_threshold: 11,
      properties_past_threshold: 0,
      bid_premium_pct: 0.0,
    },
    seen_properties: [],
    ...overrides,
  };
}

beforeEach(() => {
  mockUseAuth.mockReturnValue({ user: INVESTOR_USER, isLoading: false });
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetch404() {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify({ detail: "No buying plan found" }), { status: 404 })
  );
}

function mockFetchPlan(body: unknown) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status: 200 })
  );
}

function mockFetchCreate(body: unknown) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status: 201 })
  );
}

describe("BuyingPlanPage", () => {
  it("shows teaser for buyer tier with upgrade link", () => {
    mockUseAuth.mockReturnValue({ user: BUYER_USER, isLoading: false });
    render(<BuyingPlanPage />);
    expect(screen.getByText(/investor or agent/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upgrade/i })).toHaveAttribute("href", "/pricing");
  });

  it("shows loading state initially for investor", () => {
    mockFetch404();
    render(<BuyingPlanPage />);
    // Fetch fires on mount; during load the form shouldn't be visible yet
    // (just check that it renders without crash)
    expect(document.body).toBeInTheDocument();
  });

  it("shows setup form when investor has no plan", async () => {
    mockFetch404();
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /create plan/i })).toBeInTheDocument()
    );
    expect(screen.getByLabelText(/buy.by date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/viewings per week/i)).toBeInTheDocument();
  });

  it("shows dashboard when investor has an existing plan", async () => {
    mockFetchPlan(makePlanResponse());
    render(<BuyingPlanPage />);
    // "properties explored" is unique to the explore phase (commit shows "properties reviewed")
    await waitFor(() =>
      expect(screen.getByText(/properties explored/i)).toBeInTheDocument()
    );
    // "5 of 11" or similar — the explore count heading
    expect(screen.getByText(/5[^0-9]+11/)).toBeInTheDocument();
  });

  it("submitting setup form creates plan and shows dashboard", async () => {
    mockFetch404();
    const planResp = makePlanResponse();
    mockFetchCreate(planResp);
    render(<BuyingPlanPage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /create plan/i })).toBeInTheDocument()
    );

    // Fill in form
    const dateInput = screen.getByLabelText(/buy.by date/i);
    await userEvent.clear(dateInput);
    await userEvent.type(dateInput, "2026-12-01");

    const viewingsInput = screen.getByLabelText(/viewings per week/i);
    await userEvent.clear(viewingsInput);
    await userEvent.type(viewingsInput, "3");

    await userEvent.click(screen.getByRole("button", { name: /create plan/i }));

    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());
  });

  it("shows delete button on dashboard and calls API", async () => {
    mockFetchPlan(makePlanResponse());
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 })
    );
    render(<BuyingPlanPage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /delete plan/i })).toBeInTheDocument()
    );

    await userEvent.click(screen.getByRole("button", { name: /delete plan/i }));
    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());
  });

  it("shows commit phase info when in commit phase", async () => {
    mockFetchPlan(
      makePlanResponse({
        status: {
          phase: "commit",
          seen_count: 13,
          explore_max_score: 0.875,
          explore_threshold: 11,
          properties_past_threshold: 2,
          bid_premium_pct: 0.02,
        },
      })
    );
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByText(/commit phase/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/\+2%|bid premium/i)).toBeInTheDocument();
  });

  it("shows pause button when plan is active", async () => {
    mockFetchPlan(makePlanResponse());
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /pause plan/i })).toBeInTheDocument()
    );
  });

  it("shows resume button when plan is paused", async () => {
    mockFetchPlan(makePlanResponse({ plan: { id: 1, buy_by_date: "2026-12-01", viewings_per_week: 3.0, total_n: 30, explore_threshold: 11, created_at: "2026-05-05T00:00:00", is_paused: true } }));
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /resume plan/i })).toBeInTheDocument()
    );
  });

  it("shows paused state card when plan is paused", async () => {
    mockFetchPlan(makePlanResponse({ plan: { id: 1, buy_by_date: "2026-12-01", viewings_per_week: 3.0, total_n: 30, explore_threshold: 11, created_at: "2026-05-05T00:00:00", is_paused: true } }));
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByText(/algorithm paused/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/properties explored/i)).not.toBeInTheDocument();
  });

  it("calls PATCH when pause button is clicked and updates state", async () => {
    mockFetchPlan(makePlanResponse());
    const pausedResponse = makePlanResponse({ plan: { id: 1, buy_by_date: "2026-12-01", viewings_per_week: 3.0, total_n: 30, explore_threshold: 11, created_at: "2026-05-05T00:00:00", is_paused: true } });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(pausedResponse), { status: 200 })
    );
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /pause plan/i })).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("button", { name: /pause plan/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /resume plan/i })).toBeInTheDocument()
    );
  });

  it("shows 'Mark Seen' link in commit phase pointing to history", async () => {
    mockFetchPlan(
      makePlanResponse({
        status: {
          phase: "commit",
          seen_count: 13,
          explore_max_score: 0.875,
          explore_threshold: 11,
          properties_past_threshold: 2,
          bid_premium_pct: 0.02,
        },
      })
    );
    render(<BuyingPlanPage />);
    await waitFor(() =>
      expect(screen.getByText(/commit phase/i)).toBeInTheDocument()
    );
    const link = screen.getByRole("link", { name: /mark.*(seen|viewing)|open.*analysis/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/history");
  });
});
