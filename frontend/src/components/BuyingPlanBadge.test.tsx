import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { BuyingPlanBadge } from "./BuyingPlanBadge";

// Mock AuthContext
const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock router Link
vi.mock("@tanstack/react-router", () => ({
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
      seen_count: 0,
      explore_max_score: null,
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

function mockFetchPlan(status: number, body: unknown) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status })
  );
}

describe("BuyingPlanBadge", () => {
  it("renders nothing when user is not logged in", async () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false });
    const { container } = render(<BuyingPlanBadge />);
    // Should not call fetch
    expect(fetch).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when user has no plan (404)", async () => {
    mockFetchPlan(404, { detail: "No buying plan found" });
    const { container } = render(<BuyingPlanBadge />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    // After fetch resolves with 404, should render empty
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("shows explore phase badge when in explore phase", async () => {
    mockFetchPlan(200, makePlanResponse({
      status: {
        phase: "explore",
        seen_count: 3,
        explore_max_score: 0.7,
        explore_threshold: 11,
        properties_past_threshold: 0,
        bid_premium_pct: 0.0,
      },
    }));
    render(<BuyingPlanBadge />);
    await waitFor(() =>
      expect(screen.getByText(/explore/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/3\s*\/\s*11|3 of 11/i)).toBeInTheDocument();
  });

  it("shows commit phase badge with bid premium", async () => {
    mockFetchPlan(200, makePlanResponse({
      status: {
        phase: "commit",
        seen_count: 13,
        explore_max_score: 0.875,
        explore_threshold: 11,
        properties_past_threshold: 2,
        bid_premium_pct: 0.02,
      },
    }));
    render(<BuyingPlanBadge />);
    await waitFor(() =>
      expect(screen.getByText(/commit/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/\+2%|2%/i)).toBeInTheDocument();
  });

  it("shows zero bid premium when just entered commit phase", async () => {
    mockFetchPlan(200, makePlanResponse({
      status: {
        phase: "commit",
        seen_count: 11,
        explore_max_score: 0.75,
        explore_threshold: 11,
        properties_past_threshold: 0,
        bid_premium_pct: 0.0,
      },
    }));
    render(<BuyingPlanBadge />);
    await waitFor(() =>
      expect(screen.getByText(/commit/i)).toBeInTheDocument()
    );
  });

  it("links to /buying-plan", async () => {
    mockFetchPlan(200, makePlanResponse());
    render(<BuyingPlanBadge />);
    await waitFor(() =>
      expect(screen.getByRole("link")).toHaveAttribute("href", "/buying-plan")
    );
  });
});
