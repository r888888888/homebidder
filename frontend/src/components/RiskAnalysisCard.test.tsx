import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskAnalysisCard, type RiskData } from "./RiskAnalysisCard";

const LOW_RISK: RiskData = {
  overall_risk: "Low",
  score: 0,
  factors: [
    { name: "alquist_priolo_fault_zone", level: "low", description: "Not in fault zone." },
    { name: "flood_zone", level: "low", description: "Zone X — minimal flood risk." },
    { name: "fire_hazard_zone", level: "n/a", description: "Not in a mapped fire hazard zone." },
    { name: "liquefaction_risk", level: "n/a", description: "Not in a liquefaction zone." },
    { name: "home_age", level: "low", description: "Built in 2005." },
    { name: "days_on_market", level: "low", description: "Fresh listing at 7 days." },
    { name: "hpi_trend", level: "low", description: "Appreciating ZIP." },
    { name: "prop13_tax_shock", level: "low", description: "Small delta." },
    { name: "highway_proximity", level: "low", description: "Traffic proximity at 30th percentile." },
  ],
};

const HIGH_RISK: RiskData = {
  overall_risk: "High",
  score: 5,
  factors: [
    { name: "alquist_priolo_fault_zone", level: "high", description: "In an Alquist-Priolo Earthquake Fault Zone." },
    { name: "flood_zone", level: "low", description: "Zone X." },
    { name: "fire_hazard_zone", level: "n/a", description: "No data." },
    { name: "liquefaction_risk", level: "n/a", description: "No data." },
    { name: "home_age", level: "low", description: "Built in 2010." },
    { name: "days_on_market", level: "low", description: "7 days." },
    { name: "hpi_trend", level: "low", description: "Appreciating." },
    { name: "prop13_tax_shock", level: "low", description: "Small delta." },
  ],
};

const VERY_HIGH_RISK: RiskData = {
  overall_risk: "Very High",
  score: 22,
  factors: [
    { name: "alquist_priolo_fault_zone", level: "high", description: "In fault zone." },
    { name: "flood_zone", level: "high", description: "SFHA mandatory insurance." },
    { name: "fire_hazard_zone", level: "high", description: "Very High fire severity zone." },
    { name: "liquefaction_risk", level: "high", description: "High liquefaction risk." },
    { name: "home_age", level: "high", description: "Built in 1920." },
    { name: "days_on_market", level: "low", description: "7 days." },
    { name: "hpi_trend", level: "high", description: "Depreciating ZIP." },
    { name: "prop13_tax_shock", level: "high", description: "Large delta." },
  ],
};

describe("RiskAnalysisCard", () => {
  it("renders the overall risk level", () => {
    render(<RiskAnalysisCard risk={LOW_RISK} />);
    // "Low" appears in overall badge and factor badges — verify at least one is present
    expect(screen.getAllByText("Low").length).toBeGreaterThan(0);
  });

  it("renders 'High' overall risk badge", () => {
    render(<RiskAnalysisCard risk={HIGH_RISK} />);
    expect(screen.getAllByText("High").length).toBeGreaterThan(0);
  });

  it("renders 'Very High' overall risk badge", () => {
    render(<RiskAnalysisCard risk={VERY_HIGH_RISK} />);
    expect(screen.getAllByText("Very High").length).toBeGreaterThan(0);
  });

  it("renders all factor names with human-readable labels", () => {
    render(<RiskAnalysisCard risk={LOW_RISK} />);
    // Check a few expected labels are present
    expect(screen.getAllByText(/fault zone/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/flood/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/home age/i)).toBeInTheDocument();
    expect(screen.getByText(/days on market/i)).toBeInTheDocument();
    // highway_proximity must render with a friendly label, not the raw key
    expect(screen.getByText(/highway proximity/i)).toBeInTheDocument();
    expect(screen.queryByText("highway_proximity")).not.toBeInTheDocument();
  });

  it("renders factor descriptions", () => {
    render(<RiskAnalysisCard risk={HIGH_RISK} />);
    expect(screen.getByText(/Alquist-Priolo Earthquake Fault Zone/i)).toBeInTheDocument();
  });

  it("renders factor level badges", () => {
    const { container } = render(<RiskAnalysisCard risk={HIGH_RISK} />);
    // Should have a 'high' badge for the fault zone factor
    const badges = container.querySelectorAll("[data-level]");
    const levels = Array.from(badges).map((b) => b.getAttribute("data-level"));
    expect(levels).toContain("high");
    expect(levels).toContain("low");
  });

  it("shows n/a factors as muted, not alarming", () => {
    const { container } = render(<RiskAnalysisCard risk={LOW_RISK} />);
    const naBadges = Array.from(container.querySelectorAll("[data-level='n/a']"));
    expect(naBadges.length).toBeGreaterThan(0);
  });

  it("renders a section header", () => {
    render(<RiskAnalysisCard risk={LOW_RISK} />);
    expect(screen.getByText(/risk assessment/i)).toBeInTheDocument();
  });
});
