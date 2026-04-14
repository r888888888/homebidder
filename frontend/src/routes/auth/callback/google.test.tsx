import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../../../lib/AuthContext";
import GoogleCallbackPage from "./google";

const mockNavigate = vi.fn();
const mockSearch = { code: "fake-code", state: "fake-state" };

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  useSearch: () => mockSearch,
  useNavigate: () => mockNavigate,
}));

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
});

describe("GoogleCallbackPage", () => {
  it("shows a loading state while processing", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "uuid-1", email: "g@test.com", is_active: true }),
        })
        .mockResolvedValue({
          ok: true,
          json: async () => ({ access_token: "tok", token_type: "bearer" }),
        })
    );
    render(
      <AuthProvider>
        <GoogleCallbackPage />
      </AuthProvider>
    );
    // Loading text should appear initially
    expect(screen.getByText(/signing you in/i)).toBeInTheDocument();
  });

  it("stores token and navigates to / on successful callback", async () => {
    // No token in localStorage, so AuthProvider skips /api/users/me on mount.
    // Sequence: google callback → /api/users/me (from loginWithToken).
    vi.stubGlobal(
      "fetch",
      vi.fn()
        // /api/auth/google/callback
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: "google-tok", token_type: "bearer" }),
        })
        // /api/users/me after token stored via loginWithToken
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "uuid-1", email: "g@test.com", is_active: true }),
        })
    );

    render(
      <AuthProvider>
        <GoogleCallbackPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
    expect(localStorage.getItem("hb_token")).toBe("google-tok");
  });

  it("shows an error message when the callback API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        // callback fails (no initial /api/users/me because no token)
        .mockResolvedValueOnce({
          ok: false,
          status: 400,
          json: async () => ({ detail: "OAuth token exchange failed" }),
        })
    );

    render(
      <AuthProvider>
        <GoogleCallbackPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
