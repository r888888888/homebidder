import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { PermitsCard, type PermitsData } from "./PermitsCard";

const PERMITS_RESULT: PermitsData = {
  source: "dbi",
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  open_permits_count: 1,
  recent_permits_5y: 3,
  major_permits_10y: 1,
  oldest_open_permit_age_days: 480,
  permit_counts_by_type: {
    electrical: 1,
    plumbing: 0,
    building: 0,
  },
  complaints_open_count: 0,
  complaints_recent_3y: 2,
  flags: ["open_over_365_days", "recent_structural_work"],
  permits: [
    {
      permit_number: "202401011234",
      filed_date: "2024-01-10",
      issued_date: "2024-03-05",
      completed_date: null,
      status: "issued",
      permit_type: "ALTERATION",
      work_description: "Kitchen and bath remodel",
      estimated_cost: 120000,
      address: "450 SANCHEZ ST",
      unit: "2",
      source_url: "https://dbiweb02.sfgov.org/dbipts/default.aspx?page=EID_PermitDetails&PermitNo=202401011234",
    },
  ],
  complaints: [
    {
      complaint_number: "202295394",
      date_filed: "2022-09-09",
      status: "CLOSED",
      division: "HIS",
      expired: null,
      address: "319 PLYMOUTH AV",
      source_url: "https://dbiweb02.sfgov.org/dbipts/default.aspx?page=AddressComplaint&ComplaintNo=202295394",
    },
  ],
};

describe("PermitsCard", () => {
  it("renders permit summary metrics and flags", () => {
    render(<PermitsCard permits={PERMITS_RESULT} />);

    expect(screen.getByText(/permit history/i)).toBeInTheDocument();
    expect(screen.getByText(/department of building inspection/i)).toBeInTheDocument();
    expect(screen.getByText(/open permits/i)).toBeInTheDocument();
    expect(screen.getByText(/480 days/i)).toBeInTheDocument();
    expect(screen.getByText(/open permit older than 1 year/i)).toBeInTheDocument();
  });

  it("renders a permit row with key details", async () => {
    const user = userEvent.setup();
    render(<PermitsCard permits={PERMITS_RESULT} />);

    expect(screen.getByText(/status: issued/i)).toBeInTheDocument();
    // Work description is hidden until the toggle is clicked
    await user.click(screen.getByRole("button", { name: /show original description/i }));
    expect(screen.getByText(/kitchen and bath remodel/i)).toBeInTheDocument();
    expect(screen.getByText(/alteration permit 202401011234 is issued/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view permit/i })).toHaveAttribute(
      "href",
      "https://dbiweb02.sfgov.org/dbipts/default.aspx?page=EID_PermitDetails&PermitNo=202401011234"
    );
  });

  it("renders complaints section", () => {
    render(<PermitsCard permits={PERMITS_RESULT} />);

    expect(screen.getByText(/^Complaints$/i)).toBeInTheDocument();
    expect(screen.getByText(/status: closed/i)).toBeInTheDocument();
    expect(screen.getByText(/division his/i)).toBeInTheDocument();
    expect(screen.getByText(/complaint 202295394 is closed/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view complaint/i })).toHaveAttribute(
      "href",
      "https://dbiweb02.sfgov.org/dbipts/default.aspx?page=AddressComplaint&ComplaintNo=202295394"
    );
  });

  it("renders llm_overall_summary when provided", () => {
    const withOverallSummary = {
      ...PERMITS_RESULT,
      llm_overall_summary: "One completed electrical upgrade; no open complaints or red flags.",
    } as unknown as PermitsData;

    render(<PermitsCard permits={withOverallSummary} />);

    expect(screen.getByText(/one completed electrical upgrade; no open complaints or red flags/i)).toBeInTheDocument();
  });

  it("does not render overall summary section when llm_overall_summary is absent", () => {
    render(<PermitsCard permits={PERMITS_RESULT} />);

    expect(screen.queryByTestId("permits-overall-summary")).not.toBeInTheDocument();
  });

  it("hides work_description by default and shows it after clicking the toggle link", async () => {
    const user = userEvent.setup();
    render(<PermitsCard permits={PERMITS_RESULT} />);

    // Description hidden by default
    expect(screen.queryByText(/kitchen and bath remodel/i)).not.toBeInTheDocument();

    // Toggle link is present
    const toggle = screen.getByRole("button", { name: /show original description/i });
    await user.click(toggle);

    // Description now visible
    expect(screen.getByText(/kitchen and bath remodel/i)).toBeInTheDocument();
  });

  it("renders llm permit summary and impact label when available", () => {
    const withLlm = {
      ...PERMITS_RESULT,
      permits: [
        {
          ...PERMITS_RESULT.permits[0],
          llm_summary: "Main panel upgrade and branch rewiring completed.",
          llm_impact: "positive",
        },
      ],
    } as unknown as PermitsData;

    render(<PermitsCard permits={withLlm} />);

    expect(screen.getByText(/main panel upgrade and branch rewiring completed/i)).toBeInTheDocument();
    expect(screen.getByText(/impact: positive/i)).toBeInTheDocument();
  });
});
