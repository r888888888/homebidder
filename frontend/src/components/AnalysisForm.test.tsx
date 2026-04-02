import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
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
    expect(onSubmit).toHaveBeenCalledWith(expected[0], expected[1]);
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
});
