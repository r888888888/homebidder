import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ValidationBanner, type ValidationResult } from "./ValidationBanner";

const WITHIN_CI: ValidationResult = {
  actual_sold_price: 1_200_000,
  estimated_price: 1_200_000,
  error_dollars: 0,
  error_pct: 0.0,
  within_ci: true,
  sold_date: "2026-01-15",
  address: "400 Hearst Ave",
};

const SLIGHT_MISS: ValidationResult = {
  actual_sold_price: 1_350_000,
  estimated_price: 1_215_000,
  error_dollars: -135_000,
  error_pct: -10.0,
  within_ci: false,
  sold_date: "2026-01-15",
  address: "400 Hearst Ave",
};

const BIG_MISS: ValidationResult = {
  actual_sold_price: 1_000_000,
  estimated_price: 1_220_000,
  error_dollars: 220_000,
  error_pct: 22.0,
  within_ci: false,
  sold_date: null,
  address: null,
};

describe("ValidationBanner", () => {
  it("renders estimated price and actual sale price", () => {
    render(<ValidationBanner result={WITHIN_CI} />);
    const matches = screen.getAllByText(/1,200,000/);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("shows the sold date when provided", () => {
    render(<ValidationBanner result={WITHIN_CI} />);
    expect(screen.getByText(/Jan 15, 2026/i)).toBeInTheDocument();
  });

  it("does not crash when sold_date is null", () => {
    render(<ValidationBanner result={BIG_MISS} />);
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument();
  });

  it("shows the error percentage", () => {
    render(<ValidationBanner result={SLIGHT_MISS} />);
    expect(screen.getByText(/10\.0%|10%/)).toBeInTheDocument();
  });
});
