import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MarkSeenButton } from "./MarkSeenButton";

// Mock AuthContext
const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock ToastContext
const mockToast = { success: vi.fn(), error: vi.fn() };
vi.mock("./Toast", () => ({
  useToast: () => mockToast,
}));

const LOGGED_IN_USER = { id: "user-1", email: "test@test.com", subscription_tier: "buyer" };

beforeEach(() => {
  mockUseAuth.mockReturnValue({ user: LOGGED_IN_USER, isLoading: false });
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetchList(rows: object[] = []) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(JSON.stringify({ seen_properties: rows }), { status: 200 })
  );
}

function mockFetchPost(status = 201, body?: object) {
  vi.mocked(fetch).mockResolvedValueOnce(
    new Response(
      JSON.stringify(
        body ?? {
          id: 1,
          analysis_id: 42,
          address_snapshot: "42 Test St",
          quality: "good",
          location: "good",
          composite_score: 0.875,
          seen_at: "2026-05-04T12:00:00",
          notes: null,
        }
      ),
      { status }
    )
  );
}

describe("MarkSeenButton", () => {
  it("renders nothing when user is not logged in", () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false });
    mockFetchList();
    const { container } = render(
      <MarkSeenButton analysisId={42} address="42 Test St" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders 'Mark Seen' button for logged-in user (not yet seen)", async () => {
    mockFetchList([]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /mark seen/i })).toBeInTheDocument()
    );
  });

  it("renders 'Seen' button when analysis is already marked seen", async () => {
    mockFetchList([
      {
        id: 1,
        analysis_id: 42,
        quality: "good",
        location: "good",
        composite_score: 0.875,
        seen_at: "2026-05-04T12:00:00",
      },
    ]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /seen/i })).toBeInTheDocument()
    );
  });

  it("opens modal when 'Mark Seen' is clicked", async () => {
    mockFetchList([]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);
    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/quality/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument();
  });

  it("submits quality and location on form submit", async () => {
    mockFetchList([]);
    mockFetchPost();
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);

    await userEvent.selectOptions(screen.getByLabelText(/quality/i), "good");
    await userEvent.selectOptions(screen.getByLabelText(/location/i), "good");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());
    // Modal should close
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
  });

  it("shows error toast on 409 (already seen)", async () => {
    mockFetchList([]);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Already seen" }), { status: 409 })
    );
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.selectOptions(screen.getByLabelText(/quality/i), "good");
    await userEvent.selectOptions(screen.getByLabelText(/location/i), "good");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockToast.error).toHaveBeenCalled());
  });

  it("cancels modal without submitting", async () => {
    mockFetchList([]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    expect(fetch).toHaveBeenCalledTimes(1); // only the initial GET
  });
});
