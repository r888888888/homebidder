import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import Header from "./Header";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useMatchRoute: () => () => null,
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

  it("does not show History link when not authenticated", async () => {
    renderHeader();
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /log in/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: /history/i })).not.toBeInTheDocument();
  });

  it("shows Log in and Sign up links when not authenticated", async () => {
    renderHeader();
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /log in/i })).toHaveAttribute("href", "/login");
      expect(screen.getByRole("link", { name: /sign up/i })).toHaveAttribute("href", "/register");
    });
  });
});

describe("Header (authenticated)", () => {
  it("shows History link and account avatar when authenticated", async () => {
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
      expect(screen.getByRole("link", { name: /history/i })).toHaveAttribute("href", "/history");
    });
    expect(screen.getByRole("button", { name: /account menu/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /log in/i })).not.toBeInTheDocument();
  });

  it("shows initials from display_name in avatar", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "uuid-1",
          email: "alice@example.com",
          is_active: true,
          display_name: "Alice Smith",
        }),
      })
    );

    renderHeader();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /account menu/i })).toHaveTextContent("AS");
    });
  });

  it("opens dropdown with user info on avatar click", async () => {
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
      expect(screen.getByRole("button", { name: /account menu/i })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /account menu/i }));

    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("clears auth state after clicking sign out", async () => {
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
      expect(screen.getByRole("button", { name: /account menu/i })).toBeInTheDocument();
    });

    // Open dropdown then click sign out
    await userEvent.click(screen.getByRole("button", { name: /account menu/i }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /log in/i })).toBeInTheDocument();
    });
    expect(localStorage.getItem("hb_token")).toBeNull();
  });
});
