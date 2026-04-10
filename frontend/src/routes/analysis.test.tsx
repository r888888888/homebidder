import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AnalysisPage } from "./analysis";
import { ToastProvider } from "../components/Toast";

// Mock TanStack Router search params
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useSearch: vi.fn(),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

import { useSearch } from "@tanstack/react-router";

function renderAnalysisPage(address: string, buyerContext = "") {
  vi.mocked(useSearch).mockReturnValue({ address, buyerContext });
  return render(
    <ToastProvider>
      <AnalysisPage />
    </ToastProvider>
  );
}

function mockSseStream(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  const stream = new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index++]));
      } else {
        controller.close();
      }
    },
  });
  return new Response(stream, { status: 200 });
}

/** Like mockSseStream but never closes — keeps isRunning=true after events are sent. */
function mockOpenSseStream(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  const stream = new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index++]));
      }
      // intentionally never closes
    },
  });
  return new Response(stream, { status: 200 });
}

describe("AnalysisPage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("displays the property address as a heading", async () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>);
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    expect(screen.getByText("450 Sanchez St, San Francisco, CA 94114")).toBeInTheDocument();
  });

  it("calls the API with the address from search params on mount", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114", "fast close");

    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const [, init] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.address).toBe("450 Sanchez St, San Francisco, CA 94114");
    expect(body.buyer_context).toBe("fast close");
  });

  it("renders tool call steps as they arrive (while running)", async () => {
    const user = userEvent.setup();
    // Open stream (never closes) — keeps isRunning=true so the agent steps card stays visible
    vi.mocked(fetch).mockResolvedValue(
      mockOpenSseStream([
        `data: ${JSON.stringify({ type: "tool_call", tool: "fetch_comps" })}\n\n`,
      ])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    // Agent steps are on the Analysis tab
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: /analysis/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("tab", { name: /analysis/i }));
    await waitFor(() =>
      expect(screen.getByText("Fetching comparable sales")).toBeInTheDocument()
    );
  });

  it("hides agent steps card once analysis completes", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([
        `data: ${JSON.stringify({ type: "tool_call", tool: "fetch_comps" })}\n\n`,
        `data: ${JSON.stringify({ type: "done" })}\n\n`,
      ])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: /analysis/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("tab", { name: /analysis/i }));
    await waitFor(() =>
      expect(screen.queryByText(/agent steps/i)).not.toBeInTheDocument()
    );
  });

  it("shows a link back to the home page", async () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>);
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    expect(screen.getByRole("link", { name: /new analysis/i })).toBeInTheDocument();
  });

  it("shows a Refresh button", async () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>);
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    // While running, the button label is "Refreshing…"; once done, "Refresh analysis"
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });

  it("disables the Refresh button while analysis is running", async () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>);
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    expect(screen.getByRole("button", { name: /refresh/i })).toBeDisabled();
  });

  it("enables the Refresh button after analysis finishes", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /refresh analysis/i })).not.toBeDisabled()
    );
  });

  it("clicking Refresh re-calls the API for the same address", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        mockSseStream([
          `data: ${JSON.stringify({ type: "tool_call", tool: "fetch_comps" })}\n\n`,
          `data: ${JSON.stringify({ type: "done" })}\n\n`,
        ])
      )
      .mockResolvedValueOnce(
        mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
      );

    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /refresh analysis/i })).not.toBeDisabled()
    );

    await userEvent.click(screen.getByRole("button", { name: /refresh analysis/i }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const [, init1] = vi.mocked(fetch).mock.calls[0];
    const [, init2] = vi.mocked(fetch).mock.calls[1];
    expect(JSON.parse((init1 as RequestInit).body as string).address).toBe(
      "450 Sanchez St, San Francisco, CA 94114"
    );
    expect(JSON.parse((init2 as RequestInit).body as string).address).toBe(
      "450 Sanchez St, San Francisco, CA 94114"
    );
  });

  it("shows 'Refreshing…' text while re-running after a click", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
      )
      .mockReturnValueOnce(new Promise(() => {}) as Promise<Response>);

    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /refresh analysis/i })).not.toBeDisabled()
    );

    await userEvent.click(screen.getByRole("button", { name: /refresh analysis/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /refreshing/i })).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /refreshing/i })).toBeDisabled();
  });

  it("sends force_refresh: false on initial mount", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");

    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const [, init] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.force_refresh).toBe(false);
  });

  it("sends force_refresh: true when Refresh button is clicked", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
      )
      .mockResolvedValueOnce(
        mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
      );

    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /refresh analysis/i })).not.toBeDisabled()
    );

    await userEvent.click(screen.getByRole("button", { name: /refresh analysis/i }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const [, init2] = vi.mocked(fetch).mock.calls[1];
    const body2 = JSON.parse((init2 as RequestInit).body as string);
    expect(body2.force_refresh).toBe(true);
  });

  it("passes an AbortSignal to fetch and aborts it on unmount", async () => {
    const abortSpy = vi.fn();
    const mockSignal = {} as AbortSignal;
    const mockController = { signal: mockSignal, abort: abortSpy };
    vi.spyOn(global, "AbortController").mockImplementation(
      () => mockController as unknown as AbortController
    );

    vi.mocked(fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>);

    const { unmount } = renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");

    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).signal).toBe(mockSignal);

    unmount();
    expect(abortSpy).toHaveBeenCalled();
  });
});
