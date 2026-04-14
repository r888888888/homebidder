import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import Header from "./Header";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function renderHeader() {
  return render(
    <AuthProvider>
      <Header />
    </AuthProvider>
  );
}

describe("Header (unauthenticated)", () => {
  it("renders the HomeBidder logo link to /", async () => {
    renderHeader();
    await waitFor(() => {
      expect(screen.queryByText("loading")).not.toBeInTheDocument();
    });
    const homeLink = screen.getByRole("link", { name: /homebidder/i });
    expect(homeLink).toHaveAttribute("href", "/");
  });

  it("renders a History nav link to /history", async () => {
    renderHeader();
    await waitFor(() => {
      const historyLink = screen.getByRole("link", { name: /history/i });
      expect(historyLink).toHaveAttribute("href", "/history");
    });
  });

  it("shows Login and Sign up links when not authenticated", async () => {
    renderHeader();
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /log in/i })).toHaveAttribute("href", "/login");
      expect(screen.getByRole("link", { name: /sign up/i })).toHaveAttribute("href", "/register");
    });
  });
});

describe("Header (authenticated)", () => {
  it("shows user email abbreviation and a logout button when authenticated", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "uuid-1", email: "alice@example.com", is_active: true }),
      })
    );

    renderHeader();

    await waitFor(() => {
      // Email abbreviation (first part before @) or full email shown in nav
      expect(screen.getByText(/alice/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /log in/i })).not.toBeInTheDocument();
  });

  it("clears auth state after clicking logout", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "uuid-1", email: "alice@example.com", is_active: true }),
      })
    );

    renderHeader();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /log in/i })).toBeInTheDocument();
    });
    expect(localStorage.getItem("hb_token")).toBeNull();
  });
});
