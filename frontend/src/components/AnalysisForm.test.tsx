import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AnalysisForm } from "./AnalysisForm";

describe("AnalysisForm", () => {
  it("renders required fields", () => {
    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    expect(screen.getByLabelText(/address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/buyer notes/i)).toBeInTheDocument();
  });

  it.each([
    {
      name: "with empty buyer context",
      address: "450 Sanchez St, San Francisco, CA 94114",
      buyerContext: "",
      expected: ["450 Sanchez St, San Francisco, CA 94114", ""],
    },
    {
      name: "with buyer context",
      address: "123 Main St, Oakland, CA 94610",
      buyerContext: "multiple offers expected",
      expected: ["123 Main St, Oakland, CA 94610", "multiple offers expected"],
    },
    {
      name: "with trimmed inputs",
      address: "  88 King St, San Francisco, CA 94107  ",
      buyerContext: "  close in 21 days  ",
      expected: ["88 King St, San Francisco, CA 94107", "close in 21 days"],
    },
  ])("calls onSubmit $name", async ({ address, buyerContext, expected }) => {
    const onSubmit = vi.fn();
    render(<AnalysisForm onSubmit={onSubmit} isRunning={false} />);

    await userEvent.type(screen.getByLabelText(/address/i), address);
    if (buyerContext) {
      await userEvent.type(screen.getByLabelText(/buyer notes/i), buyerContext);
    }
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(onSubmit).toHaveBeenCalledWith(expected[0], expected[1], null);
  });

  it("disables the submit button when address is empty", () => {
    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    expect(screen.getByRole("button", { name: /analyze/i })).toBeDisabled();
  });

  it("disables inputs while running", () => {
    render(<AnalysisForm onSubmit={() => {}} isRunning={true} />);
    expect(screen.getByLabelText(/address/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /analyzing/i })).toBeDisabled();
  });

  it("passes null inspectionFindings when no PDF uploaded", async () => {
    const onSubmit = vi.fn();
    render(<AnalysisForm onSubmit={onSubmit} isRunning={false} />);
    await userEvent.type(screen.getByLabelText(/address/i), "450 Sanchez St");
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(onSubmit).toHaveBeenCalledWith("450 Sanchez St", "", null);
  });
});

describe("AnalysisForm — inspection report upload", () => {
  const _MOCK_FINDINGS = {
    property_address: "318 Avalon Ave, San Francisco, CA 94112",
    inspector: "Alonzo Inspections",
    inspection_date: "2024-03-15",
    systems: [],
    summary: "No major deficiencies.",
  };

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders the upload dropzone", () => {
    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    expect(
      screen.getByLabelText(/inspection report/i)
    ).toBeTruthy();
  });

  it("shows processing state during upload", async () => {
    let resolve!: (value: Response) => void;
    const pending = new Promise<Response>((r) => { resolve = r; });
    vi.mocked(fetch).mockReturnValueOnce(pending);

    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);

    const input = screen.getByLabelText(/inspection report/i) as HTMLInputElement;
    const file = new File(["%PDF-1.4 fake"], "report.pdf", { type: "application/pdf" });
    await userEvent.upload(input, file);

    expect(screen.getByText(/processing/i)).toBeTruthy();

    // resolve so the component cleans up
    resolve(new Response(JSON.stringify(_MOCK_FINDINGS), { status: 200 }));
  });

  it("shows summary chip after successful upload", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(_MOCK_FINDINGS), { status: 200 })
    );

    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    const input = screen.getByLabelText(/inspection report/i) as HTMLInputElement;
    const file = new File(["%PDF-1.4 fake"], "report.pdf", { type: "application/pdf" });
    await userEvent.upload(input, file);

    expect(screen.getByText(/report uploaded/i)).toBeTruthy();
  });

  it("shows error message on upload failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Parse failed" }), { status: 422 })
    );

    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    const input = screen.getByLabelText(/inspection report/i) as HTMLInputElement;
    const file = new File(["%PDF-1.4 fake"], "report.pdf", { type: "application/pdf" });
    await userEvent.upload(input, file);

    expect(screen.getByText(/could not parse/i)).toBeTruthy();
  });

  it("remove button clears findings", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(_MOCK_FINDINGS), { status: 200 })
    );

    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    const input = screen.getByLabelText(/inspection report/i) as HTMLInputElement;
    const file = new File(["%PDF-1.4 fake"], "report.pdf", { type: "application/pdf" });
    await userEvent.upload(input, file);

    expect(screen.getByText(/report uploaded/i)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(screen.queryByText(/report uploaded/i)).toBeNull();
  });

  it("passes inspection findings through onSubmit after successful upload", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(_MOCK_FINDINGS), { status: 200 })
    );

    const onSubmit = vi.fn();
    render(<AnalysisForm onSubmit={onSubmit} isRunning={false} />);
    const input = screen.getByLabelText(/inspection report/i) as HTMLInputElement;
    const file = new File(["%PDF-1.4 fake"], "report.pdf", { type: "application/pdf" });
    await userEvent.upload(input, file);

    await userEvent.type(screen.getByLabelText(/address/i), "318 Avalon Ave");
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(onSubmit).toHaveBeenCalledWith("318 Avalon Ave", "", _MOCK_FINDINGS);
  });
});
