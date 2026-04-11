import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CrimeCard, type CrimeData } from "./CrimeCard";

const BASE: CrimeData = {
  violent_count: 3,
  property_count: 12,
  total_count: 15,
  radius_miles: 0.5,
  period_days: 90,
  source: "SFPD / DataSF",
  top_violent_types: ["Assault", "Robbery"],
  top_property_types: ["Larceny Theft", "Motor Vehicle Theft", "Burglary"],
};

describe("CrimeCard", () => {
  it("renders section header with radius and period", () => {
    render(<CrimeCard crime={BASE} />);
    expect(screen.getByText(/0\.5 mi radius/i)).toBeInTheDocument();
    expect(screen.getByText(/90-day window/i)).toBeInTheDocument();
  });

  it("renders source attribution", () => {
    render(<CrimeCard crime={BASE} />);
    expect(screen.getByText("SFPD / DataSF")).toBeInTheDocument();
  });

  it("renders violent crime count and top types", () => {
    render(<CrimeCard crime={BASE} />);
    expect(screen.getByText(/violent crime/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/assault/i)).toBeInTheDocument();
  });

  it("renders property crime count and top types", () => {
    render(<CrimeCard crime={BASE} />);
    expect(screen.getByText(/property crime/i)).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText(/larceny theft/i)).toBeInTheDocument();
  });

  it("shows unavailable message when violent_count is null", () => {
    render(
      <CrimeCard crime={{ ...BASE, violent_count: null, top_violent_types: [] }} />
    );
    expect(screen.getByText(/violent crime data unavailable/i)).toBeInTheDocument();
  });

  it("shows unavailable message when property_count is null", () => {
    render(
      <CrimeCard crime={{ ...BASE, property_count: null, top_property_types: [] }} />
    );
    expect(screen.getByText(/property crime data unavailable/i)).toBeInTheDocument();
  });

  it("omits source line when source is null", () => {
    const { container } = render(<CrimeCard crime={{ ...BASE, source: null }} />);
    // Should not find the "SFPD / DataSF" text
    expect(container.textContent).not.toContain("SFPD / DataSF");
  });
});
