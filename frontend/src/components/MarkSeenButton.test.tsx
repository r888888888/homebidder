import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MarkSeenButton } from "./MarkSeenButton";

const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

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
          quality: "neutral",
          location: "neutral",
          composite_score: 1.0,
          bidding_intent: "yes",
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
        quality: "neutral",
        location: "neutral",
        composite_score: 1.0,
        bidding_intent: "yes",
        seen_at: "2026-05-04T12:00:00",
      },
    ]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /seen/i })).toBeInTheDocument()
    );
  });

  it("opens modal with bidding-intent question (no quality/location dropdowns)", async () => {
    mockFetchList([]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);
    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // The single question is "Would you make an offer..."
    expect(screen.getByText(/would you make an offer/i)).toBeInTheDocument();
    // Yes / No radio buttons exist
    expect(screen.getByRole("radio", { name: /yes/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /no/i })).toBeInTheDocument();
    // Quality / Location should be gone
    expect(screen.queryByLabelText(/quality/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/location/i)).not.toBeInTheDocument();
  });

  it("requires a bidding intent selection before submit", async () => {
    mockFetchList([]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    // Click Save without selecting Yes/No
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    // Toast should fire and no POST should have been issued (only initial GET counted).
    expect(mockToast.error).toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("submits bidding_intent: 'yes' in the payload", async () => {
    mockFetchList([]);
    mockFetchPost();
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("radio", { name: /yes/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());

    // Inspect the POST body
    const lastCall = vi.mocked(fetch).mock.calls.at(-1);
    expect(lastCall).toBeDefined();
    const init = lastCall![1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.bidding_intent).toBe("yes");
    expect(body.analysis_id).toBe(42);
  });

  it("submits bidding_intent: 'no' in the payload", async () => {
    mockFetchList([]);
    mockFetchPost(201, {
      id: 2,
      analysis_id: 42,
      quality: "neutral",
      location: "neutral",
      composite_score: 0.0,
      bidding_intent: "no",
      seen_at: "2026-05-05T10:00:00",
      notes: null,
    });
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("radio", { name: /no/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());

    const lastCall = vi.mocked(fetch).mock.calls.at(-1);
    const body = JSON.parse((lastCall![1] as RequestInit).body as string);
    expect(body.bidding_intent).toBe("no");
  });

  it("does not send quality or location in the request body", async () => {
    mockFetchList([]);
    mockFetchPost();
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("radio", { name: /yes/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());

    const lastCall = vi.mocked(fetch).mock.calls.at(-1);
    const body = JSON.parse((lastCall![1] as RequestInit).body as string);
    expect(body).not.toHaveProperty("quality");
    expect(body).not.toHaveProperty("location");
  });

  it("shows error toast on 409 (already seen)", async () => {
    mockFetchList([]);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Already seen" }), { status: 409 })
    );
    render(<MarkSeenButton analysisId={42} address="42 Test St" />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("radio", { name: /yes/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockToast.error).toHaveBeenCalled());
  });

  it("calls onSeenEntry with bidding_intent when initial fetch finds existing entry", async () => {
    const onSeenEntry = vi.fn();
    mockFetchList([
      {
        id: 1,
        analysis_id: 42,
        quality: "neutral",
        location: "neutral",
        composite_score: 1.0,
        bidding_intent: "yes",
        seen_at: "2026-05-04T12:00:00",
        notes: null,
      },
    ]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" onSeenEntry={onSeenEntry} />);
    await waitFor(() => expect(onSeenEntry).toHaveBeenCalledWith("yes"));
  });

  it("calls onSeenEntry with null when initial fetch finds no entry", async () => {
    const onSeenEntry = vi.fn();
    mockFetchList([]);
    render(<MarkSeenButton analysisId={42} address="42 Test St" onSeenEntry={onSeenEntry} />);
    await waitFor(() => expect(onSeenEntry).toHaveBeenCalledWith(null));
  });

  it("calls onSeenEntry with new bidding_intent after marking seen", async () => {
    const onSeenEntry = vi.fn();
    mockFetchList([]);
    mockFetchPost(201, {
      id: 2,
      analysis_id: 42,
      quality: "neutral",
      location: "neutral",
      composite_score: 1.0,
      bidding_intent: "yes",
      seen_at: "2026-05-05T10:00:00",
      notes: null,
    });
    render(<MarkSeenButton analysisId={42} address="42 Test St" onSeenEntry={onSeenEntry} />);
    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("radio", { name: /yes/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(onSeenEntry).toHaveBeenCalledWith("yes"));
  });

  it("calls onSeenEntry with null after unmarking", async () => {
    const onSeenEntry = vi.fn();
    mockFetchList([
      {
        id: 1,
        analysis_id: 42,
        quality: "neutral",
        location: "neutral",
        composite_score: 1.0,
        bidding_intent: "yes",
        seen_at: "2026-05-04T12:00:00",
        notes: null,
      },
    ]);
    vi.mocked(fetch).mockResolvedValueOnce(new Response("{}", { status: 200 }));
    render(<MarkSeenButton analysisId={42} address="42 Test St" onSeenEntry={onSeenEntry} />);
    const seenBtn = await screen.findByRole("button", { name: /seen/i });
    await userEvent.click(seenBtn);
    await waitFor(() => expect(onSeenEntry).toHaveBeenLastCalledWith(null));
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
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("calls onChanged after successfully marking seen", async () => {
    const onChanged = vi.fn();
    mockFetchList([]);
    mockFetchPost();
    render(<MarkSeenButton analysisId={42} address="42 Test St" onChanged={onChanged} />);

    const btn = await screen.findByRole("button", { name: /mark seen/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("radio", { name: /yes/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  });

  it("calls onChanged after successfully unmarking", async () => {
    const onChanged = vi.fn();
    mockFetchList([
      {
        id: 1,
        analysis_id: 42,
        quality: "neutral",
        location: "neutral",
        composite_score: 1.0,
        bidding_intent: "yes",
        seen_at: "2026-05-04T12:00:00",
        notes: null,
      },
    ]);
    vi.mocked(fetch).mockResolvedValueOnce(new Response("{}", { status: 200 }));
    render(<MarkSeenButton analysisId={42} address="42 Test St" onChanged={onChanged} />);

    const seenBtn = await screen.findByRole("button", { name: /seen/i });
    await userEvent.click(seenBtn);

    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  });
});
