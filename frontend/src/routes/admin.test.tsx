import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useNavigate: () => vi.fn(),
}));

import { AdminPage } from "./admin";

const PAGE_SIZE = 25;

function renderAdmin() {
  return render(<AdminPage />);
}

function pagedResponse<T>(items: T[], total = items.length, page = 1, pages = 1) {
  return new Response(
    JSON.stringify({ items, total, page, page_size: PAGE_SIZE, pages }),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );
}

const USERS = [
  { id: "uuid-1", email: "alice@example.com", display_name: null, is_active: true, is_verified: false, is_superuser: false },
];
const ANALYSES = [
  {
    id: 1, address: "123 Main St, San Francisco, CA", user_id: "uuid-1", user_email: "alice@example.com",
    offer_low: 800000, offer_high: 950000, offer_recommended: 870000,
    risk_level: "medium", investment_rating: "good", created_at: "2026-04-24T00:00:00",
  },
];

function mockSuccess(usersPages = 1, analysesPages = 1) {
  vi.mocked(fetch)
    .mockResolvedValueOnce(pagedResponse(USERS, USERS.length, 1, usersPages))
    .mockResolvedValueOnce(pagedResponse(ANALYSES, ANALYSES.length, 1, analysesPages));
}

function mockUnauthorized() {
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ detail: "Incorrect username or password" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })
  );
}

async function loginAs(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/username/i), "admin");
  await user.type(screen.getByLabelText(/password/i), "testpass");
  await user.click(screen.getByRole("button", { name: /sign in/i }));
}

describe("AdminPage — login form", () => {
  beforeEach(() => { vi.spyOn(global, "fetch"); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("shows username and password fields with a Sign in button", () => {
    renderAdmin();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("does not show data tables before login", () => {
    renderAdmin();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("sends Basic Auth header on submit", async () => {
    const user = userEvent.setup();
    mockSuccess();
    renderAdmin();
    await loginAs(user);
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining("/api/admin/users"),
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: expect.stringMatching(/^Basic /) }),
        })
      )
    );
  });

  it("shows user and analysis data after successful login", async () => {
    const user = userEvent.setup();
    mockSuccess();
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());
    expect(screen.getByText("123 Main St, San Francisco, CA")).toBeInTheDocument();
  });

  it("shows an error message on 401", async () => {
    const user = userEvent.setup();
    mockUnauthorized();
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getByText(/incorrect/i)).toBeInTheDocument());
  });

  it("keeps the login form visible after a failed login", async () => {
    const user = userEvent.setup();
    mockUnauthorized();
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getByText(/incorrect/i)).toBeInTheDocument());
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  });
});

describe("AdminPage — pagination", () => {
  beforeEach(() => { vi.spyOn(global, "fetch"); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("includes page and page_size in the initial fetch URL", async () => {
    const user = userEvent.setup();
    mockSuccess();
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringMatching(/page=1/),
      expect.anything()
    );
  });

  it("hides pagination controls when there is only one page", async () => {
    const user = userEvent.setup();
    mockSuccess(1, 1);
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /prev/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /next/i })).not.toBeInTheDocument();
  });

  it("shows Prev/Next controls when there are multiple pages", async () => {
    const user = userEvent.setup();
    mockSuccess(3, 1); // users has 3 pages
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /prev/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it("Prev is disabled on page 1", async () => {
    const user = userEvent.setup();
    mockSuccess(3, 1);
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
  });

  it("Next is enabled on page 1 of 3", async () => {
    const user = userEvent.setup();
    mockSuccess(3, 1);
    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /next/i })).not.toBeDisabled();
  });

  it("clicking Next fetches page 2", async () => {
    const user = userEvent.setup();
    // Login: users p1 + analyses p1; then Next click: users p2
    vi.mocked(fetch)
      .mockResolvedValueOnce(pagedResponse(USERS, 50, 1, 2))     // users page 1
      .mockResolvedValueOnce(pagedResponse(ANALYSES, 1, 1, 1))   // analyses page 1
      .mockResolvedValueOnce(pagedResponse([], 50, 2, 2));        // users page 2

    renderAdmin();
    await loginAs(user);
    await waitFor(() => expect(screen.getAllByText("alice@example.com")[0]).toBeInTheDocument());

    const nextBtns = screen.getAllByRole("button", { name: /next/i });
    await user.click(nextBtns[0]); // first Next = users section

    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringMatching(/admin\/users.*page=2/),
        expect.anything()
      )
    );
  });
});
