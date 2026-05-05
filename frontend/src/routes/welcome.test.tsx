import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { WelcomePage } from "./welcome";

const mockNavigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  useNavigate: () => mockNavigate,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({ useAuth: () => mockUseAuth() }));

const INVESTOR_USER = {
  id: "investor-uuid",
  email: "investor@test.com",
  subscription_tier: "investor" as const,
  is_superuser: false,
  is_active: true,
};

const BUYER_USER = {
  id: "buyer-uuid",
  email: "buyer@test.com",
  subscription_tier: "buyer" as const,
  is_superuser: false,
  is_active: true,
};

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
});

describe("WelcomePage", () => {
  it("does not redirect while isLoading is true", async () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: true });
    render(<WelcomePage />);
    // Give any async effects a chance to run
    await new Promise((r) => setTimeout(r, 0));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("redirects to / when user is null after loading completes", async () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
  });

  it("redirects to / when onboarding localStorage key is already set", async () => {
    localStorage.setItem("homebidder_onboarding_done_investor-uuid", "1");
    mockUseAuth.mockReturnValue({ user: INVESTOR_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
  });

  it("renders welcome heading for Investor+ user", async () => {
    mockUseAuth.mockReturnValue({ user: INVESTOR_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /welcome/i })).toBeInTheDocument();
    });
  });

  it("renders buying plan form for Investor+ user", async () => {
    mockUseAuth.mockReturnValue({ user: INVESTOR_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => {
      expect(screen.getByLabelText(/buy.by date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/viewings.*week/i)).toBeInTheDocument();
    });
  });

  it("renders Buyer teaser (not form) for Buyer tier", async () => {
    mockUseAuth.mockReturnValue({ user: BUYER_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => {
      expect(screen.queryByLabelText(/buy.by date/i)).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: /upgrade to investor/i })).toBeInTheDocument();
    });
  });

  it("skip button sets localStorage and navigates to /", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({ user: BUYER_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => screen.getByRole("button", { name: /skip/i }));
    await user.click(screen.getByRole("button", { name: /skip/i }));
    expect(localStorage.getItem("homebidder_onboarding_done_buyer-uuid")).toBe("1");
    expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
  });

  it("form submit success for Investor+ navigates to /buying-plan and sets localStorage", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({
          plan: { id: 1, buy_by_date: "2026-12-01", viewings_per_week: 3, total_n: 30, explore_threshold: 11 },
          status: { phase: "explore", seen_count: 0, explore_max_score: null, explore_threshold: 11, properties_past_threshold: 0, bid_premium_pct: 0 },
          seen_properties: [],
        }),
      })
    );
    mockUseAuth.mockReturnValue({ user: INVESTOR_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => screen.getByLabelText(/buy.by date/i));
    await user.clear(screen.getByLabelText(/buy.by date/i));
    await user.type(screen.getByLabelText(/buy.by date/i), "2026-12-01");
    await user.click(screen.getByRole("button", { name: /set up/i }));
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/buying-plan" });
    });
    expect(localStorage.getItem("homebidder_onboarding_done_investor-uuid")).toBe("1");
  });

  it("form submit API failure shows error and does not navigate", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Invalid date" }),
      })
    );
    mockUseAuth.mockReturnValue({ user: INVESTOR_USER, isLoading: false });
    render(<WelcomePage />);
    await waitFor(() => screen.getByLabelText(/buy.by date/i));
    await user.type(screen.getByLabelText(/buy.by date/i), "2026-12-01");
    await user.click(screen.getByRole("button", { name: /set up/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalledWith({ to: "/buying-plan" });
  });
});
