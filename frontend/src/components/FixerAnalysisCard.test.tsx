import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { FixerAnalysisCard, type FixerAnalysisData } from "./FixerAnalysisCard";

const BASE: FixerAnalysisData = {
  is_fixer: true,
  fixer_signals: ["Fixer / Contractor Special"],
  offer_recommended: 900_000,
  renovation_estimate_low: 65_000,
  renovation_estimate_mid: 88_000,
  renovation_estimate_high: 111_000,
  line_items: [
    { category: "Kitchen remodel", low: 35_000, high: 60_000 },
    { category: "Bathroom remodel", low: 30_000, high: 51_000 },
  ],
  all_in_fixer_low: 965_000,
  all_in_fixer_mid: 988_000,
  all_in_fixer_high: 1_011_000,
  turnkey_value: 1_100_000,
  renovated_fair_value: 1_100_000,
  implied_equity_mid: 112_000,
  verdict: "cheaper_fixer",
  savings_mid: 112_000,
  scope_notes: "Kitchen and bath are primary work.",
  disclaimer:
    "Renovation costs are rough Bay Area estimates based on current labor and material rates. Get contractor bids before committing.",
};

describe("FixerAnalysisCard", () => {
  it("renders card heading", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/fixer analysis/i)).toBeInTheDocument();
  });

  it("renders verdict badge 'Fixer May Win' for cheaper_fixer", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/fixer may win/i)).toBeInTheDocument();
  });

  it("renders verdict badge 'Turn-key Cheaper' for cheaper_turnkey", () => {
    render(<FixerAnalysisCard data={{ ...BASE, verdict: "cheaper_turnkey", savings_mid: -150_000 }} />);
    expect(screen.getByText(/turn-key cheaper/i)).toBeInTheDocument();
  });

  it("renders verdict badge 'Comparable Cost' for comparable", () => {
    render(<FixerAnalysisCard data={{ ...BASE, verdict: "comparable", savings_mid: 10_000 }} />);
    expect(screen.getByText(/comparable cost/i)).toBeInTheDocument();
  });

  it("shows all-in fixer mid cost", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // $988,000 formatted
    expect(screen.getByText(/988,000/)).toBeInTheDocument();
  });

  it("shows turn-key AVM", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // $1,100,000 formatted — may appear in both Fair Value and Post-reno value cells
    expect(screen.getAllByText(/1,100,000/).length).toBeGreaterThan(0);
  });

  it("shows savings amount when fixer is cheaper", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // savings_mid = 112,000 — may also appear as implied_equity
    expect(screen.getAllByText(/112,000/).length).toBeGreaterThan(0);
  });

  it("shows overage amount when turn-key is cheaper", () => {
    render(
      <FixerAnalysisCard data={{ ...BASE, verdict: "cheaper_turnkey", savings_mid: -150_000 }} />
    );
    expect(screen.getByText(/150,000/)).toBeInTheDocument();
  });

  it("renders renovation line item categories", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/kitchen remodel/i)).toBeInTheDocument();
    expect(screen.getByText(/bathroom remodel/i)).toBeInTheDocument();
  });

  it("renders disclaimer text", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/get contractor bids/i)).toBeInTheDocument();
  });

  it("shows post-renovation value", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getAllByText(/post-reno value/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/\$1,100,000/).length).toBeGreaterThan(0);
  });

  it("shows positive implied equity in green", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/implied equity/i)).toBeInTheDocument();
    // positive equity shows with + prefix
    expect(screen.getByText(/\+\$112,000/)).toBeInTheDocument();
  });

  it("shows negative implied equity with minus prefix", () => {
    render(
      <FixerAnalysisCard
        data={{ ...BASE, implied_equity_mid: -50_000, renovated_fair_value: 938_000 }}
      />
    );
    expect(screen.getByText(/−\$50,000/)).toBeInTheDocument();
  });
});
