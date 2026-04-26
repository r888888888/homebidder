import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import PricingPage from "./pricing";

const mockNavigate = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => mockNavigate,
}));

function renderPricing(user?: {
  subscription_tier?: "buyer" | "investor" | "agent";
  is_grandfathered?: boolean;
} | null) {
  if (user !== undefined && user !== null) {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "uuid-1",
          email: "alice@example.com",
          is_active: true,
          is_superuser: false,
          subscription_tier: user.subscription_tier ?? "buyer",
          is_grandfathered: user.is_grandfathered ?? false,
        }),
      })
    );
  } else if (user === null) {
    // Explicitly unauthenticated
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  }
  return render(
    <AuthProvider>
      <PricingPage />
    </AuthProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
});

describe("PricingPage", () => {
  it("renders three plan cards", async () => {
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getByText(/^Buyer$/i)).toBeInTheDocument();
      expect(screen.getByText(/^Investor$/i)).toBeInTheDocument();
      expect(screen.getByText(/^Agent$/i)).toBeInTheDocument();
    });
  });

  it("shows correct analysis limits for each tier", async () => {
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getByText(/5 analyses/i)).toBeInTheDocument();
      expect(screen.getByText(/30 analyses/i)).toBeInTheDocument();
      expect(screen.getByText(/100 analyses/i)).toBeInTheDocument();
    });
  });

  it("shows Free for Buyer tier", async () => {
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getByText("Free")).toBeInTheDocument();
    });
  });

  it("shows $10/month for Investor tier", async () => {
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getByText(/\$10/)).toBeInTheDocument();
    });
  });

  it("shows $30/month for Agent tier", async () => {
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getByText(/\$30/)).toBeInTheDocument();
    });
  });

  it("shows anonymous usage note", async () => {
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getByText(/3 free analyses per month/i)).toBeInTheDocument();
    });
  });

  it("shows 'Current plan' badge for authenticated user on their tier", async () => {
    renderPricing({ subscription_tier: "investor" });
    await waitFor(() => {
      expect(screen.getByText(/current plan/i)).toBeInTheDocument();
    });
  });

  it("upgrade button for unauthenticated user navigates to /login", async () => {
    const user = userEvent.setup();
    renderPricing(null);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /upgrade/i }).length).toBeGreaterThan(0);
    });
    await user.click(screen.getAllByRole("button", { name: /upgrade/i })[0]);
    expect(mockNavigate).toHaveBeenCalledWith({ to: "/login" });
  });

  it("upgrade button calls checkout session endpoint for authenticated buyer", async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "uuid-1",
          email: "alice@example.com",
          is_active: true,
          is_superuser: false,
          subscription_tier: "buyer",
          is_grandfathered: false,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ url: "https://checkout.stripe.com/pay/cs_test" }),
      });

    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal("fetch", mockFetch);

    const assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { href: "", assign: assignMock },
      writable: true,
    });

    render(
      <AuthProvider>
        <PricingPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /upgrade/i }).length).toBeGreaterThan(0);
    });

    await user.click(screen.getAllByRole("button", { name: /upgrade/i })[0]);

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const checkoutCall = calls.find(([url]: [string]) =>
        url.includes("/api/payments/create-checkout-session")
      );
      expect(checkoutCall).toBeTruthy();
    });
  });
});
