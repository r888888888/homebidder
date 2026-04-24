import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useNavigate: () => vi.fn(),
}));

import { AdminPage } from "./admin";

function renderAdmin() {
  return render(<AdminPage />);
}

const USERS_RESPONSE = [
  {
    id: "uuid-1",
    email: "alice@example.com",
    display_name: null,
    is_active: true,
    is_verified: false,
    is_superuser: false,
  },
];

const ANALYSES_RESPONSE = [
  {
    id: 1,
    address: "123 Main St, San Francisco, CA",
    user_id: "uuid-1",
    offer_low: 800000,
    offer_high: 950000,
    offer_recommended: 870000,
    risk_level: "medium",
    investment_rating: "good",
    created_at: "2026-04-24T00:00:00",
  },
];

function mockSuccess() {
  vi.mocked(fetch)
    .mockResolvedValueOnce(
      new Response(JSON.stringify(USERS_RESPONSE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify(ANALYSES_RESPONSE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
}

function mockUnauthorized() {
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ detail: "Incorrect username or password" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })
  );
}

describe("AdminPage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a login form initially", () => {
    renderAdmin();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("does not show data tables before login", () => {
    renderAdmin();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("fetches users and analyses with Basic Auth header on submit", async () => {
    const user = userEvent.setup();
    mockSuccess();
    renderAdmin();
    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "testpass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining("/api/admin/users"),
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: expect.stringMatching(/^Basic /) }),
        })
      )
    );
  });

  it("shows user data in a table after successful login", async () => {
    const user = userEvent.setup();
    mockSuccess();
    renderAdmin();
    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "testpass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );
  });

  it("shows analysis data in a table after successful login", async () => {
    const user = userEvent.setup();
    mockSuccess();
    renderAdmin();
    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "testpass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(
        screen.getByText("123 Main St, San Francisco, CA")
      ).toBeInTheDocument()
    );
  });

  it("shows an error message on 401 response", async () => {
    const user = userEvent.setup();
    mockUnauthorized();
    renderAdmin();
    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText(/incorrect/i)).toBeInTheDocument()
    );
  });

  it("keeps the login form visible after a failed login", async () => {
    const user = userEvent.setup();
    mockUnauthorized();
    renderAdmin();
    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText(/incorrect/i)).toBeInTheDocument());
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  });
});
