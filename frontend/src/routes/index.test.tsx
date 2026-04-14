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
  reset_at: string | null = null
) {
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ remaining, used, limit, reset_at }), {
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

  it("shows full quota when no analyses used", async () => {
    mockRateLimitStatus(5, 0);
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/5.*analyses.*remaining/i)).toBeInTheDocument()
    );
  });

  it("shows daily limit reached message when remaining is zero", async () => {
    mockRateLimitStatus(0, 5, 5, "2026-04-15T10:00:00");
    renderHomePage();
    await waitFor(() =>
      expect(screen.getByText(/daily limit reached/i)).toBeInTheDocument()
    );
  });

  it("disables the submit button when remaining is zero", async () => {
    mockRateLimitStatus(0, 5);
    renderHomePage();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /daily limit reached/i })
      ).toBeDisabled()
    );
  });

  it("does not show the counter while status is loading", () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}));
    renderHomePage();
    expect(screen.queryByText(/analyses remaining/i)).not.toBeInTheDocument();
  });
});
