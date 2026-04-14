import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";

// A simple component that exercises the auth context.
function TestConsumer() {
  const { user, isLoading, logout } = useAuth();
  if (isLoading) return <div>loading</div>;
  return (
    <div>
      {user ? (
        <>
          <span>logged in as {user.email}</span>
          <button onClick={logout}>logout</button>
        </>
      ) : (
        <span>not logged in</span>
      )}
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("AuthProvider", () => {
  it("renders children as not logged in when no token in localStorage", async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );
    await waitFor(() => {
      expect(screen.queryByText("loading")).not.toBeInTheDocument();
    });
    expect(screen.getByText("not logged in")).toBeInTheDocument();
  });

  it("validates stored token against /api/users/me and sets user on success", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "uuid-1", email: "test@example.com", is_active: true }),
      })
    );

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("logged in as test@example.com")).toBeInTheDocument();
    });
  });

  it("clears stale token when /api/users/me returns 401", async () => {
    localStorage.setItem("hb_token", "stale.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({ ok: false, status: 401 })
    );

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("not logged in")).toBeInTheDocument();
    });
    expect(localStorage.getItem("hb_token")).toBeNull();
  });

  it("logout clears user and token", async () => {
    localStorage.setItem("hb_token", "valid.jwt");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "uuid-1", email: "me@example.com", is_active: true }),
      })
    );

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("logged in as me@example.com")).toBeInTheDocument();
    });

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /logout/i }));
    });

    expect(screen.getByText("not logged in")).toBeInTheDocument();
    expect(localStorage.getItem("hb_token")).toBeNull();
  });
});
