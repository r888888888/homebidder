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

function renderProfile(token = "valid.jwt", email = "alice@example.com") {
  if (token) {
    localStorage.setItem("hb_token", token);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "uuid-1", email, is_active: true }),
      })
    );
  }
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
    // Initial /api/users/me for auth, then PATCH response
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "uuid-1", email: "alice@example.com", is_active: true }),
        })
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
          json: async () => ({ id: "uuid-1", email: "alice@example.com", is_active: true }),
        })
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
