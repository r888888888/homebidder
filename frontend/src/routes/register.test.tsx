import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../lib/AuthContext";
import RegisterPage from "./register";

const mockNavigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: unknown) => opts,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => mockNavigate,
}));

function renderRegister() {
  return render(
    <AuthProvider>
      <RegisterPage />
    </AuthProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockNavigate.mockReset();
});

describe("RegisterPage", () => {
  it("renders email, password fields and a submit button", () => {
    renderRegister();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("renders a link to /login", () => {
    renderRegister();
    const link = screen.getByRole("link", { name: /sign in/i });
    expect(link).toHaveAttribute("href", "/login");
  });

  it("registers then auto-logs in and navigates to / on success", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn()
        // register
        .mockResolvedValueOnce({
          ok: true,
          status: 201,
          json: async () => ({ id: "uuid-1", email: "new@test.com" }),
        })
        // auto-login after register
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: "tok123", token_type: "bearer" }),
        })
        // /api/users/me after token stored
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "uuid-1", email: "new@test.com", is_active: true }),
        })
    );

    renderRegister();
    await user.type(screen.getByLabelText(/email/i), "new@test.com");
    await user.type(screen.getByLabelText(/password/i), "pass123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" });
    });
  });

  it("shows an error on duplicate email (400)", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: "REGISTER_USER_ALREADY_EXISTS" }),
      })
    );

    renderRegister();
    await user.type(screen.getByLabelText(/email/i), "dup@test.com");
    await user.type(screen.getByLabelText(/password/i), "pass123");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
