import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Must start with "mock" to be accessible inside vi.mock factory (Vitest hoisting rule)
const mockPDFDownloadLink = vi.fn(({ children, className, fileName }: any) => (
  <a href="blob:fake" download={fileName} className={className} data-testid="pdf-link">
    {typeof children === "function" ? children({ loading: false, url: "blob:fake" }) : children}
  </a>
));

vi.mock("@react-pdf/renderer", () => ({
  PDFDownloadLink: (props: any) => mockPDFDownloadLink(props),
  Document: ({ children }: any) => <>{children}</>,
  Page: ({ children }: any) => <div>{children}</div>,
  View: ({ children }: any) => <div>{children}</div>,
  Text: ({ children }: any) => <span>{children}</span>,
  StyleSheet: { create: (s: any) => s },
  Font: { register: () => {} },
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

import { PdfExportButton } from "./PdfExportButton";

const MINIMAL_ANALYSIS = {
  id: 1,
  address: "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
  created_at: "2026-04-01T12:00:00",
  offer_low: 1_170_000,
  offer_recommended: 1_200_000,
  offer_high: 1_250_000,
  risk_level: null,
  investment_rating: null,
  rationale: null,
  property_data: null,
  neighborhood_data: null,
  offer_data: null,
  risk_data: null,
  investment_data: null,
  renovation_data: null,
  permits_data: null,
  crime_data: null,
  comps: [],
};

describe("PdfExportButton", () => {
  beforeEach(() => {
    mockPDFDownloadLink.mockClear();
  });

  it("renders Download PDF link for agent tier", () => {
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={true} />);
    expect(screen.getByText(/download pdf/i)).toBeInTheDocument();
  });

  it("download link is an anchor element for agent tier", () => {
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={true} />);
    const link = screen.getByTestId("pdf-link");
    expect(link.tagName).toBe("A");
  });

  it("shows loading text when PDF is generating", () => {
    mockPDFDownloadLink.mockImplementationOnce(({ children, className, fileName }: any) => (
      <a href="#" download={fileName} className={className} data-testid="pdf-link">
        {typeof children === "function" ? children({ loading: true, url: null }) : children}
      </a>
    ));
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={true} />);
    expect(screen.getByText(/preparing pdf/i)).toBeInTheDocument();
  });

  it("renders upsell teaser for non-agent tier", () => {
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={false} />);
    expect(screen.queryByText(/download pdf/i)).not.toBeInTheDocument();
  });

  it("upsell link points to /pricing", () => {
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={false} />);
    const upgradeLink = screen.getByRole("link");
    expect(upgradeLink).toHaveAttribute("href", "/pricing");
  });

  it("upsell copy mentions Agent plan", () => {
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={false} />);
    expect(screen.getByText(/agent/i)).toBeInTheDocument();
  });

  it("does not show upsell teaser for agent tier", () => {
    render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={true} />);
    // The download link should be present; no /pricing upsell
    const links = screen.getAllByRole("link");
    const pricingLink = links.find((l) => l.getAttribute("href") === "/pricing");
    expect(pricingLink).toBeUndefined();
  });

  it("renders without crashing when all optional fields are null", () => {
    expect(() =>
      render(<PdfExportButton analysis={MINIMAL_ANALYSIS} isAgent={true} />)
    ).not.toThrow();
  });
});
