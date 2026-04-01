import { render, screen, waitFor, act } from "@testing-library/react";
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

describe("AnalysisPage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("displays the property address as a heading", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
    );
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

  it("renders tool call steps as they arrive", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([
        `data: ${JSON.stringify({ type: "tool_call", tool: "fetch_comps" })}\n\n`,
        `data: ${JSON.stringify({ type: "done" })}\n\n`,
      ])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    await waitFor(() =>
      expect(screen.getByText("Fetching comparable sales")).toBeInTheDocument()
    );
  });

  it("shows a link back to the home page", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockSseStream([`data: ${JSON.stringify({ type: "done" })}\n\n`])
    );
    renderAnalysisPage("450 Sanchez St, San Francisco, CA 94114");
    expect(screen.getByRole("link", { name: /new analysis/i })).toBeInTheDocument();
  });
});
