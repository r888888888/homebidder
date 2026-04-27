import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ToastProvider } from "../components/Toast";

// Mock TanStack Router
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useNavigate: () => vi.fn(),
}));

// Import after mocks are set up
import { HomePage } from "./index";

function renderHomePage() {
  return render(
    <ToastProvider>
      <HomePage />
    </ToastProvider>
  );
}

function mockRateLimitStatus(
  remaining: number,
  used: number,
  limit = 5,
  reset_at: string | null = null,
  window: string = "monthly"
) {
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ remaining, used, limit, reset_at, window }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  );
}

describe("HomePage rate limit indicator", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows remaining analyses count after status loads", async () => {
    mockRateLimitStatus(3, 2);
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/3.*analyses.*remaining/i)).toBeInTheDocument()
    );
  });

  it("shows 'this month' in the remaining counter text", async () => {
    mockRateLimitStatus(3, 2);
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/this month/i)).toBeInTheDocument()
    );
  });

  it("shows full quota when no analyses used", async () => {
    mockRateLimitStatus(5, 0);
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/5.*analyses.*remaining/i)).toBeInTheDocument()
    );
  });

  it("shows monthly limit reached message when remaining is zero", async () => {
    mockRateLimitStatus(0, 5, 5, "2026-05-01T00:00:00");
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/monthly limit reached/i)).toBeInTheDocument()
    );
  });

  it("shows Resets on [date] when limit reached and reset_at is set", async () => {
    mockRateLimitStatus(0, 5, 5, "2026-05-01T00:00:00");
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/resets on/i)).toBeInTheDocument()
    );
  });

  it("shows Resets next month when limit reached and reset_at is null", async () => {
    mockRateLimitStatus(0, 5, 5, null);
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/resets next month/i)).toBeInTheDocument()
    );
  });

  it("disables the submit button when remaining is zero", async () => {
    mockRateLimitStatus(0, 5);
    renderHomePage();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /monthly limit reached/i })
      ).toBeDisabled()
    );
  });

  it("does not show the counter while status is loading", () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}));
    renderHomePage();
    expect(screen.queryByText(/analyses remaining/i)).not.toBeInTheDocument();
  });

  it("sends Authorization header when a token is stored", async () => {
    localStorage.setItem("hb_token", "test.jwt.token");
    mockRateLimitStatus(15, 5, 20);
    renderHomePage();
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining("/api/rate-limit/status"),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer test.jwt.token",
          }),
        })
      )
    );
    localStorage.removeItem("hb_token");
  });

  it("sends no Authorization header when no token is stored", async () => {
    localStorage.removeItem("hb_token");
    mockRateLimitStatus(5, 0, 5);
    renderHomePage();
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining("/api/rate-limit/status"),
        expect.not.objectContaining({
          headers: expect.objectContaining({ Authorization: expect.anything() }),
        })
      )
    );
  });
});
