import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import ProfilePage from "./profile";

const mockNavigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => mockNavigate,
}));

function makeUserJson(overrides: Record<string, unknown> = {}) {
  return {
    id: "uuid-1",
    email: "alice@example.com",
    is_active: true,
    is_superuser: false,
    subscription_tier: "buyer",
    is_grandfathered: false,
    ...overrides,
  };
}

function makeStatusJson(overrides: Record<string, unknown> = {}) {
  return {
    used: 2,
    limit: 5,
    remaining: 3,
    tier: "buyer",
    window: "monthly",
    is_grandfathered: false,
    ...overrides,
  };
}

function renderProfile(token = "valid.jwt", email = "alice@example.com") {
  if (token) {
    localStorage.setItem("hb_token", token);
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => makeUserJson({ email }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => makeStatusJson(),
        })
    );
  }
  return render(
    <AuthProvider>
      <ProfilePage />
    </AuthProvider>
  );
}

function renderProfileWithTier(
  tier: "buyer" | "investor" | "agent",
  overrides: Record<string, unknown> = {}
) {
  localStorage.setItem("hb_token", "valid.jwt");
  const statusData = makeStatusJson({
    tier,
    limit: tier === "buyer" ? 5 : tier === "investor" ? 30 : 100,
    ...overrides,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeUserJson({ subscription_tier: tier }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => statusData,
      })
  );
  return render(
    <AuthProvider>
      <ProfilePage />
    </AuthProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
});

describe("ProfilePage", () => {
  it("redirects to /login when not authenticated", async () => {
    render(
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>
    );
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/login" });
    });
  });

  it("renders the user email when authenticated", async () => {
    renderProfile("valid.jwt", "alice@example.com");
    await waitFor(() => {
      expect(screen.getByText(/alice@example.com/i)).toBeInTheDocument();
    });
  });

  it("renders change-password form with submit button", async () => {
    renderProfile();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /update password/i })).toBeInTheDocument();
    });
  });

  it("calls PATCH /api/users/me with new password on submit", async () => {
    const user = userEvent.setup();
    // Initial /api/users/me for auth, rate-limit status, then PATCH response
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => makeUserJson(),
        })
        .mockResolvedValueOnce({ ok: true, json: async () => makeStatusJson() })
        .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    );
    localStorage.setItem("hb_token", "valid.jwt");

    render(
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /update password/i })).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/new password/i), "newpass123");
    await user.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      const patchCall = calls.find(
        ([url, opts]: [string, RequestInit]) =>
          url.includes("/api/users/me") && opts?.method === "PATCH"
      );
      expect(patchCall).toBeTruthy();
      const body = JSON.parse(patchCall![1].body as string);
      expect(body.password).toBe("newpass123");
    });
  });

  it("shows a delete-account danger section", async () => {
    renderProfile();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /delete account/i })).toBeInTheDocument();
    });
  });

  it("calls DELETE /api/users/me and navigates to / on confirmed delete", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => makeUserJson(),
        })
        .mockResolvedValueOnce({ ok: true, json: async () => makeStatusJson() }) // rate-limit/status
        .mockResolvedValueOnce({ ok: true }) // DELETE /api/users/me
    );
    localStorage.setItem("hb_token", "valid.jwt");

    render(
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /delete account/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /delete account/i }));

    // Confirmation dialog should appear
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /confirm delete/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /confirm delete/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
    expect(localStorage.getItem("hb_token")).toBeNull();
  });
});

describe("ProfilePage — subscription section", () => {
  it("shows 'Buyer' tier badge for buyer user", async () => {
    renderProfileWithTier("buyer");
    await waitFor(() => {
      expect(screen.getByText(/buyer/i)).toBeInTheDocument();
    });
  });

  it("shows 'Investor' tier badge for investor user", async () => {
    renderProfileWithTier("investor");
    await waitFor(() => {
      expect(screen.getByText(/investor/i)).toBeInTheDocument();
    });
  });

  it("shows 'Agent' tier badge for agent user", async () => {
    renderProfileWithTier("agent");
    await waitFor(() => {
      expect(screen.getByText(/agent/i)).toBeInTheDocument();
    });
  });

  it("shows monthly usage for buyer user", async () => {
    renderProfileWithTier("buyer");
    await waitFor(() => {
      expect(screen.getByText(/2 of 5/i)).toBeInTheDocument();
    });
  });

  it("shows Upgrade to Investor and Upgrade to Agent buttons for buyer", async () => {
    renderProfileWithTier("buyer");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /upgrade to investor/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /upgrade to agent/i })).toBeInTheDocument();
    });
  });

  it("shows Upgrade to Agent and Manage billing buttons for investor", async () => {
    renderProfileWithTier("investor");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /upgrade to agent/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /manage billing/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /upgrade to investor/i })).not.toBeInTheDocument();
  });

  it("shows only Manage billing button for agent", async () => {
    renderProfileWithTier("agent");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /manage billing/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /upgrade/i })).not.toBeInTheDocument();
  });

  it("Manage billing calls customer-portal and redirects", async () => {
    const user = userEvent.setup();
    localStorage.setItem("hb_token", "valid.jwt");
    const assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { href: "", assign: assignMock },
      writable: true,
    });

    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => makeUserJson({ subscription_tier: "investor" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => makeStatusJson({ tier: "investor", limit: 30 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ url: "https://billing.stripe.com/session/test" }),
        })
    );

    render(
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /manage billing/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /manage billing/i }));

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      const portalCall = calls.find(([url]: [string]) =>
        url.includes("/api/payments/customer-portal")
      );
      expect(portalCall).toBeTruthy();
    });
  });
});
