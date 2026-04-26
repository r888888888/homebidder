import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useNavigate: () => vi.fn(),
}));

// Mock AuthContext so we control what user state the component sees.
vi.mock("../lib/AuthContext", () => ({
  useAuth: vi.fn(),
}));

// Mock auth helpers so we can control the Bearer token returned.
vi.mock("../lib/auth", () => ({
  authHeaders: vi.fn(() => ({ Authorization: "Bearer test-token" })),
  getToken: vi.fn(() => "test-token"),
}));

import { useAuth } from "../lib/AuthContext";
import { AdminPage } from "./admin";

const PAGE_SIZE = 25;

function pagedResponse<T>(items: T[], total = items.length, page = 1, pages = 1) {
  return new Response(
    JSON.stringify({ items, total, page, page_size: PAGE_SIZE, pages }),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );
}

const USERS = [
  {
    id: "uuid-1",
    email: "alice@example.com",
    display_name: null,
    is_active: true,
    is_verified: false,
    is_superuser: true,
  },
];
const ANALYSES = [
  {
    id: 1,
    address: "123 Main St, San Francisco, CA",
    user_id: "uuid-1",
    user_email: "alice@example.com",
    offer_recommended: 1250000,
    risk_level: "medium",
    created_at: "2026-04-24T00:00:00",
  },
];

function mockSuccess(usersPages = 1, analysesPages = 1) {
  vi.mocked(fetch)
    .mockResolvedValueOnce(pagedResponse(USERS, USERS.length, 1, usersPages))
    .mockResolvedValueOnce(pagedResponse(ANALYSES, ANALYSES.length, 1, analysesPages));
}

function setupAuth(user: { is_superuser: boolean; email?: string } | null) {
  vi.mocked(useAuth).mockReturnValue({
    user: user
      ? {
          id: "uuid-1",
          email: user.email ?? "admin@example.com",
          is_active: true,
          is_superuser: user.is_superuser,
        }
      : null,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    loginWithToken: vi.fn(),
    logout: vi.fn(),
  });
}

describe("AdminPage — access control", () => {
  beforeEach(() => { vi.spyOn(global, "fetch"); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("shows a login prompt when unauthenticated", () => {
    setupAuth(null);
    render(<AdminPage />);
    expect(screen.getByText(/please log in/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows access denied when user is not a superuser", () => {
    setupAuth({ is_superuser: false });
    render(<AdminPage />);
    expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("loads and shows data tables for a superuser", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess();
    render(<AdminPage />);
    await waitFor(() =>
      expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument()
    );
    expect(screen.getByText("123 Main St, San Francisco, CA")).toBeInTheDocument();
  });

  it("sends Bearer token in API calls (not Basic auth)", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess();
    render(<AdminPage />);
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining("/api/admin/users"),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: expect.stringMatching(/^Bearer /),
          }),
        })
      )
    );
  });

  it("formats offer price in millions when >= $1M", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess();
    render(<AdminPage />);
    await waitFor(() => expect(screen.getByText("$1.25M")).toBeInTheDocument());
  });
});

describe("AdminPage — pagination", () => {
  beforeEach(() => { vi.spyOn(global, "fetch"); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("hides pagination controls when there is only one page", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess(1, 1);
    render(<AdminPage />);
    await waitFor(() =>
      expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /prev/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /next/i })).not.toBeInTheDocument();
  });

  it("shows Prev/Next controls when there are multiple pages", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess(3, 1);
    render(<AdminPage />);
    await waitFor(() =>
      expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /prev/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it("Prev is disabled on page 1", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess(3, 1);
    render(<AdminPage />);
    await waitFor(() =>
      expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
  });

  it("Next is enabled on page 1 of 3", async () => {
    setupAuth({ is_superuser: true });
    mockSuccess(3, 1);
    render(<AdminPage />);
    await waitFor(() =>
      expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /next/i })).not.toBeDisabled();
  });

  it("clicking Next fetches page 2", async () => {
    setupAuth({ is_superuser: true });
    const user = userEvent.setup();
    vi.mocked(fetch)
      .mockResolvedValueOnce(pagedResponse(USERS, 50, 1, 2))
      .mockResolvedValueOnce(pagedResponse(ANALYSES, 1, 1, 1))
      .mockResolvedValueOnce(pagedResponse([], 50, 2, 2));

    render(<AdminPage />);
    await waitFor(() =>
      expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument()
    );

    const nextBtns = screen.getAllByRole("button", { name: /next/i });
    await user.click(nextBtns[0]);

    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringMatching(/admin\/users.*page=2/),
        expect.anything()
      )
    );
  });
});
