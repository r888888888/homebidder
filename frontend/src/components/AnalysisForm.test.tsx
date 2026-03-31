import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { AnalysisForm } from "./AnalysisForm";

describe("AnalysisForm", () => {
  it("renders an address input field", () => {
    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    expect(screen.getByLabelText(/address/i)).toBeInTheDocument();
  });

  it("does not render a url-type input", () => {
    render(<AnalysisForm onSubmit={() => {}} isRunning={false} />);
    expect(screen.queryByRole("textbox", { name: /listing url/i })).not.toBeInTheDocument();
  });

  it("calls onSubmit with address string and empty buyer context", async () => {
    const onSubmit = vi.fn();
    render(<AnalysisForm onSubmit={onSubmit} isRunning={false} />);

    await userEvent.type(
      screen.getByLabelText(/address/i),
      "450 Sanchez St, San Francisco, CA 94114"
    );
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      "450 Sanchez St, San Francisco, CA 94114",
      ""
    );
  });

  it("includes buyer context when provided", async () => {
    const onSubmit = vi.fn();
    render(<AnalysisForm onSubmit={onSubmit} isRunning={false} />);

    await userEvent.type(screen.getByLabelText(/address/i), "123 Main St, Oakland, CA 94610");
    await userEvent.type(screen.getByLabelText(/buyer notes/i), "multiple offers expected");
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      "123 Main St, Oakland, CA 94610",
      "multiple offers expected"
    );
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
