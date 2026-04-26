import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../../../lib/AuthContext";
import AppleCallbackPage from "./apple";

const mockNavigate = vi.fn();
// Apple POSTs to the backend; backend redirects to frontend with access_token in URL.
// The page reads access_token directly from search params — no backend fetch needed.
let mockSearch: Record<string, string> = { access_token: "apple-tok" };

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  useSearch: () => mockSearch,
  useNavigate: () => mockNavigate,
}));

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
  mockSearch = { access_token: "apple-tok" };
});

describe("AppleCallbackPage", () => {
  it("shows a loading state while processing", () => {
    // No /api/users/me mock yet — just check the initial render
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "uuid-2", email: "a@example.com", is_active: true }),
      })
    );
    render(
      <AuthProvider>
        <AppleCallbackPage />
      </AuthProvider>
    );
    expect(screen.getByText(/signing you in/i)).toBeInTheDocument();
  });

  it("stores token and navigates to / on successful callback", async () => {
    // access_token arrives in the URL from the backend redirect.
    // loginWithToken stores it then calls /api/users/me.
    // Two mock responses: React runs child effects before parent, so both
    // loginWithToken's fetchCurrentUser and AuthProvider's fetchCurrentUser
    // can each consume one response without racing.
    const userResponse = {
      ok: true,
      json: async () => ({ id: "uuid-2", email: "a@example.com", is_active: true }),
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(userResponse).mockResolvedValueOnce(userResponse)
    );

    render(
      <AuthProvider>
        <AppleCallbackPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
    expect(localStorage.getItem("hb_token")).toBe("apple-tok");
  });

  it("shows an error message when backend redirects with error param", async () => {
    mockSearch = { error: "OAuth+token+exchange+failed" };

    render(
      <AuthProvider>
        <AppleCallbackPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
