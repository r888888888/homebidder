import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import LoginPage from "./login";

// Minimal router mock
const mockNavigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => mockNavigate,
}));

function renderLogin() {
  return render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
});

describe("LoginPage", () => {
  it("renders email and password fields and a submit button", () => {
    renderLogin();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders a link to /register", () => {
    renderLogin();
    const link = screen.getByRole("link", { name: /create an account/i });
    expect(link).toHaveAttribute("href", "/register");
  });

  it("calls login API and navigates to / on success", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn()
        // login call
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: "tok123", token_type: "bearer" }),
        })
        // /api/users/me call (triggered by AuthProvider after token set)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "uuid-1", email: "user@test.com", is_active: true }),
        })
    );

    renderLogin();
    await user.type(screen.getByLabelText(/email/i), "user@test.com");
    await user.type(screen.getByLabelText(/password/i), "pass123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
  });

  it("renders a Continue with Google button", () => {
    renderLogin();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("clicking Continue with Google calls /api/auth/google/authorize and redirects", async () => {
    const user = userEvent.setup();
    const originalLocation = window.location;
    // jsdom doesn't let you set href directly; use a spy on assign
    const assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, href: "" },
      writable: true,
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authorization_url: "https://accounts.google.com/o/oauth2/auth?test" }),
      })
    );

    renderLogin();
    await user.click(screen.getByRole("button", { name: /continue with google/i }));

    await waitFor(() => {
      expect(window.location.href).toBe("https://accounts.google.com/o/oauth2/auth?test");
    });

    // Restore
    Object.defineProperty(window, "location", { value: originalLocation, writable: true });
  });

  it("shows an error message on failed login", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: "LOGIN_BAD_CREDENTIALS" }),
      })
    );

    renderLogin();
    await user.type(screen.getByLabelText(/email/i), "bad@test.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
