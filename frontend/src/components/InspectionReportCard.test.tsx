import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { InspectionReportCard, type InspectionFindings } from "./InspectionReportCard";

const BASE: InspectionFindings = {
  property_address: "318 Avalon Ave, San Francisco, CA 94112",
  inspector: "Alonzo Inspections",
  inspection_date: "2024-03-15",
  systems: [
    {
      name: "Plumbing - Waste Lines",
      status: "deficient",
      severity: "high",
      findings: "Bathtub waste lines actively leaking into crawlspace",
      renovation_category: "plumbing",
    },
    {
      name: "Windows",
      status: "deficient",
      severity: "moderate",
      findings: "Multiple fogged double-pane units",
      renovation_category: "windows",
    },
    {
      name: "Roof",
      status: "serviceable",
      severity: "low",
      findings: "",
      renovation_category: "roof",
    },
  ],
  summary: "2 deficiencies found; plumbing requires immediate attention.",
};

describe("InspectionReportCard", () => {
  it("renders inspector name and date", () => {
    render(<InspectionReportCard data={BASE} />);
    expect(screen.getByText(/Alonzo Inspections/)).toBeTruthy();
    expect(screen.getByText(/Mar 15, 2024/)).toBeTruthy();
  });

  it("renders all system names", () => {
    render(<InspectionReportCard data={BASE} />);
    expect(screen.getByText(/Plumbing - Waste Lines/)).toBeTruthy();
    expect(screen.getByText(/Windows/)).toBeTruthy();
    expect(screen.getByText(/Roof/)).toBeTruthy();
  });

  it("shows findings text for deficient systems", () => {
    render(<InspectionReportCard data={BASE} />);
    expect(
      screen.getByText(/Bathtub waste lines actively leaking into crawlspace/)
    ).toBeTruthy();
    expect(screen.getByText(/Multiple fogged double-pane units/)).toBeTruthy();
  });

  it("shows green badge for serviceable systems", () => {
    render(<InspectionReportCard data={BASE} />);
    // The serviceable badge text
    expect(screen.getByText(/Serviceable/i)).toBeTruthy();
  });

  it("shows red badge for high severity systems", () => {
    render(<InspectionReportCard data={BASE} />);
    expect(screen.getByText(/High/i)).toBeTruthy();
  });

  it("renders summary text", () => {
    render(<InspectionReportCard data={BASE} />);
    expect(
      screen.getByText(/2 deficiencies found; plumbing requires immediate attention\./)
    ).toBeTruthy();
  });
});
