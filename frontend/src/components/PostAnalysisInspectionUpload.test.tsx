import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { PostAnalysisInspectionUpload } from "./PostAnalysisInspectionUpload";

const _MOCK_FINDINGS = {
  property_address: "318 Avalon Ave, San Francisco, CA 94112",
  inspector: "Alonzo Inspections",
  inspection_date: "2024-03-15",
  systems: [
    {
      name: "Plumbing",
      status: "deficient",
      severity: "high",
      findings: "Active leak",
      renovation_category: "plumbing",
    },
  ],
  summary: "1 deficiency found.",
};

const _MOCK_RENOVATION = {
  is_fixer: true,
  fixer_signals: ["Fixer"],
  offer_recommended: 900_000,
  renovation_estimate_low: 60_000,
  renovation_estimate_mid: 80_000,
  renovation_estimate_high: 100_000,
  line_items: [],
  all_in_fixer_low: 960_000,
  all_in_fixer_mid: 980_000,
  all_in_fixer_high: 1_000_000,
  turnkey_value: 1_050_000,
  renovated_fair_value: 1_050_000,
  implied_equity_mid: 70_000,
  verdict: "cheaper_fixer" as const,
  savings_mid: 70_000,
  scope_notes: null,
  disclaimer: "Rough estimates only.",
  inspection_informed: true,
};

// Helpers for the two response shapes the backend now returns
function makeResponse(renovationData: typeof _MOCK_RENOVATION | null = null) {
  return new Response(
    JSON.stringify({ findings: _MOCK_FINDINGS, renovation_data: renovationData }),
    { status: 200 }
  );
}

function makePdf(name = "report.pdf") {
  return new File(["%PDF-1.4 fake"], name, { type: "application/pdf" });
}

describe("PostAnalysisInspectionUpload", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the upload dropzone when idle", () => {
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
      />
    );
    expect(screen.getByLabelText(/upload inspection report/i)).toBeInTheDocument();
    expect(screen.getByText(/upload pdf/i)).toBeInTheDocument();
  });

  it("shows processing state during upload", async () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {})); // never resolves
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    expect(screen.getByText(/processing/i)).toBeInTheDocument();
  });

  it("shows success chip after successful upload", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse());
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() =>
      expect(screen.getByText(/report uploaded/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/1 issue/i)).toBeInTheDocument();
  });

  it("calls onSuccess callback with findings on successful upload", async () => {
    const onSuccess = vi.fn();
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse());
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={onSuccess}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
    expect(onSuccess).toHaveBeenCalledWith(_MOCK_FINDINGS);
  });

  it("calls onRenovationUpdate when renovation_data is present", async () => {
    const onRenovationUpdate = vi.fn();
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse(_MOCK_RENOVATION));
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
        onRenovationUpdate={onRenovationUpdate}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() => expect(onRenovationUpdate).toHaveBeenCalledOnce());
    expect(onRenovationUpdate).toHaveBeenCalledWith(_MOCK_RENOVATION);
  });

  it("does not call onRenovationUpdate when renovation_data is null", async () => {
    const onRenovationUpdate = vi.fn();
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse(null));
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
        onRenovationUpdate={onRenovationUpdate}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() => expect(screen.getByText(/report uploaded/i)).toBeInTheDocument());
    expect(onRenovationUpdate).not.toHaveBeenCalled();
  });

  it("shows error on 400 (non-PDF or bad request)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("Bad Request", { status: 400 })
    );
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() =>
      expect(screen.getByText(/could not parse/i)).toBeInTheDocument()
    );
  });

  it("shows error on 422 (parse failure)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("Unprocessable", { status: 422 })
    );
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() =>
      expect(screen.getByText(/could not parse/i)).toBeInTheDocument()
    );
  });

  it("sends request to the correct URL", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse());
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        onSuccess={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [url] = vi.mocked(fetch).mock.calls[0] as [string, ...unknown[]];
    expect(url).toContain("/api/analyses/42/inspection-report");
  });

  it("sends X-Session-ID header when sessionId prop is provided", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse());
    render(
      <PostAnalysisInspectionUpload
        analysisId={42}
        sessionId="test-session-abc"
        onSuccess={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/upload inspection report/i);
    await userEvent.upload(input, makePdf());
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [, options] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    const headers = options.headers as Record<string, string>;
    expect(headers["X-Session-ID"]).toBe("test-session-abc");
  });
});
