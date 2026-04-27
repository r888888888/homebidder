import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import Footer from "./Footer";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function renderFooter() {
  return render(
    <AuthProvider>
      <Footer />
    </AuthProvider>
  );
}

describe("Footer (unauthenticated)", () => {
  it("does not show Admin link when not authenticated", async () => {
    renderFooter();
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
    });
  });
});

describe("Footer (authenticated non-superuser)", () => {
  it("does not show Admin link for a regular user", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
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
    );

    renderFooter();

    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
    });
  });
});

describe("Footer (superuser)", () => {
  it("shows Admin link for a superuser", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "uuid-1",
          email: "admin@example.com",
          is_active: true,
          is_superuser: true,
          subscription_tier: "agent",
          is_grandfathered: false,
        }),
      })
    );

    renderFooter();

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /admin/i })).toHaveAttribute("href", "/admin");
    });
  });
});
