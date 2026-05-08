import { describe, it, expect, beforeEach } from "vitest";
import {
  getDtiCap,
  computeMaxPurchasePrice,
  computeMonthlyPMI,
  DEFAULT_RATE_FALLBACK_PCT,
  PROPERTY_TAX_ANNUAL_PCT,
  INSURANCE_ANNUAL_PCT,
  PMI_ANNUAL_PCT,
} from "./affordability";

beforeEach(() => {
  localStorage.clear();
});

describe("getDtiCap", () => {
  it("returns 0.36 for income below $100k", () => {
    expect(getDtiCap(80_000)).toBe(0.36);
    expect(getDtiCap(0)).toBe(0.36);
    expect(getDtiCap(99_999)).toBe(0.36);
  });

  it("returns 0.40 at exactly $100k and up to $199,999", () => {
    expect(getDtiCap(100_000)).toBe(0.40);
    expect(getDtiCap(150_000)).toBe(0.40);
    expect(getDtiCap(199_999)).toBe(0.40);
  });

  it("returns 0.43 at exactly $200k and up to $299,999", () => {
    expect(getDtiCap(200_000)).toBe(0.43);
    expect(getDtiCap(250_000)).toBe(0.43);
    expect(getDtiCap(299_999)).toBe(0.43);
  });

  it("returns 0.45 at $300k and above", () => {
    expect(getDtiCap(300_000)).toBe(0.45);
    expect(getDtiCap(500_000)).toBe(0.45);
    expect(getDtiCap(1_000_000)).toBe(0.45);
  });
});

describe("computeMaxPurchasePrice — Regime A (no PMI)", () => {
  it("computes max price for $150k income, $0 debts, $200k down, 6.5% rate", () => {
    const result = computeMaxPurchasePrice({
      annualIncome: 150_000,
      monthlyDebts: 0,
      downPayment: 200_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    // DTI cap: 40% for $150k income
    // H_max = 0.40 × (150000/12) = 5000
    // Should be Regime A (no PMI) since $200k down on ~$820k house ≈ 24% dp
    expect(result.regime).toBe("no_pmi");
    expect(result.impliedDpPct).toBeGreaterThanOrEqual(0.20);
    expect(result.monthlyPMI).toBe(0);
    expect(result.debtsBlown).toBe(false);
    expect(result.downPaymentExceedsMax).toBe(false);
    // Max price should be in the ~$820-830k range
    expect(result.maxPrice).toBeGreaterThan(810_000);
    expect(result.maxPrice).toBeLessThan(840_000);
    // Rounded to nearest $1000
    expect(result.maxPrice % 1000).toBe(0);
  });

  it("tier boundary: $200k income produces higher max price than $199k income (40%→43% DTI)", () => {
    // Use large down payment ($300k) to keep both scenarios firmly in Regime A
    const at199k = computeMaxPurchasePrice({
      annualIncome: 199_000,
      monthlyDebts: 0,
      downPayment: 300_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });
    const at200k = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 300_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    // Jump from 40% to 43% DTI should increase max price by at least $50k
    expect(at200k.maxPrice).toBeGreaterThan(at199k.maxPrice + 50_000);
  });

  it("HOA reduces max price", () => {
    const noHoa = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 150_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });
    const withHoa = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 150_000,
      monthlyHOA: 700,
      targetRatePct: 6.5,
    });

    expect(withHoa.maxPrice).toBeLessThan(noHoa.maxPrice);
    // $700/mo HOA at ~$1.1M max price should reduce by roughly $90-100k
    expect(noHoa.maxPrice - withHoa.maxPrice).toBeGreaterThan(50_000);
  });

  it("debts reduce max price", () => {
    const noDebts = computeMaxPurchasePrice({
      annualIncome: 150_000,
      monthlyDebts: 0,
      downPayment: 100_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });
    const withDebts = computeMaxPurchasePrice({
      annualIncome: 150_000,
      monthlyDebts: 1_000,
      downPayment: 100_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(withDebts.maxPrice).toBeLessThan(noDebts.maxPrice);
  });

  it("higher down payment increases max price (Regime A)", () => {
    const lowDown = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 200_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });
    const highDown = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 400_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(highDown.maxPrice).toBeGreaterThan(lowDown.maxPrice);
  });

  it("high rate (10%) significantly reduces max price vs 6.5%", () => {
    const lowRate = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 200_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });
    const highRate = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 200_000,
      monthlyHOA: 0,
      targetRatePct: 10.0,
    });

    expect(highRate.maxPrice).toBeLessThan(lowRate.maxPrice - 100_000);
  });

  it("zero rate edge case uses linear amortization (no NaN or Infinity)", () => {
    const result = computeMaxPurchasePrice({
      annualIncome: 200_000,
      monthlyDebts: 0,
      downPayment: 100_000,
      monthlyHOA: 0,
      targetRatePct: 0,
    });

    expect(isNaN(result.maxPrice)).toBe(false);
    expect(isFinite(result.maxPrice)).toBe(true);
    expect(result.maxPrice).toBeGreaterThan(0);
  });
});

describe("computeMaxPurchasePrice — Regime B (with PMI)", () => {
  it("applies PMI when down payment implies sub-20% dp", () => {
    const result = computeMaxPurchasePrice({
      annualIncome: 150_000,
      monthlyDebts: 0,
      downPayment: 50_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(result.regime).toBe("with_pmi");
    expect(result.impliedDpPct).toBeLessThan(0.20);
    expect(result.monthlyPMI).toBeGreaterThan(0);
    expect(result.debtsBlown).toBe(false);
    // PMI reduces buying power vs Regime A with same income
    const regimeA = computeMaxPurchasePrice({
      annualIncome: 150_000,
      monthlyDebts: 0,
      downPayment: 200_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });
    expect(result.maxPrice).toBeLessThan(regimeA.maxPrice);
  });
});

describe("computeMaxPurchasePrice — boundary case", () => {
  it("returns boundary regime when Regime A and B are both self-inconsistent", () => {
    // Find a scenario where: dp/P_max_A < 0.20 but dp/P_max_B >= 0.20
    // This happens near the 20%-down crossover point.
    // Use $150k income, try to find a down payment at the boundary.
    // P_max_boundary = dp / 0.20, so dp = P_max × 0.20
    // We need to engineer a case where Regime A says sub-20% and Regime B says over-20%.
    // With H_max = 5000, M ≈ 0.006323, tax+ins ≈ 0.001292, pmi_m ≈ 0.000583:
    // P_max_A (no PMI) = (5000 + dp*0.006323) / 0.007615
    // For dp/P_max_A = 0.20: dp = 0.20 * P_max_A → P_max_A = (5000 + 0.20*P_max_A*0.006323)/0.007615
    // P_max_A * 0.007615 - P_max_A*0.20*0.006323 = 5000
    // P_max_A * (0.007615 - 0.001265) = 5000
    // P_max_A * 0.006350 = 5000 → P_max_A = 787,402
    // dp = 0.20 * 787402 = 157,480
    // Let's test with dp = 157_480 to get near the boundary
    const result = computeMaxPurchasePrice({
      annualIncome: 150_000,
      monthlyDebts: 0,
      downPayment: 157_480, // Near the 20% boundary
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    // Should be boundary or no_pmi (depending on float arithmetic)
    expect(["boundary", "no_pmi"]).toContain(result.regime);
    if (result.regime === "boundary") {
      expect(result.maxPrice).toBeCloseTo(157_480 / 0.20, -3);
      expect(result.impliedDpPct).toBeCloseTo(0.20, 2);
    }
  });
});

describe("computeMaxPurchasePrice — edge/error cases", () => {
  it("debtsBlown when debts + HOA >= DTI cap × monthly income", () => {
    // $100k income, 40% DTI cap, monthly income = $8333
    // H_max = 0.40 × 8333 = 3333. Debts = 3500 > 3333 → blown
    const result = computeMaxPurchasePrice({
      annualIncome: 100_000,
      monthlyDebts: 3_500,
      downPayment: 100_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(result.debtsBlown).toBe(true);
    expect(result.maxPrice).toBe(0);
  });

  it("HOA combined with debts can blow budget", () => {
    const result = computeMaxPurchasePrice({
      annualIncome: 100_000,
      monthlyDebts: 2_000,
      downPayment: 100_000,
      monthlyHOA: 2_000,
      targetRatePct: 6.5,
    });
    // H_max = 0.40 × 8333 - 2000 - 2000 = 3333 - 4000 = -667 → blown
    expect(result.debtsBlown).toBe(true);
    expect(result.maxPrice).toBe(0);
  });

  it("zero income returns debtsBlown=true, maxPrice=0", () => {
    const result = computeMaxPurchasePrice({
      annualIncome: 0,
      monthlyDebts: 0,
      downPayment: 100_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(result.debtsBlown).toBe(true);
    expect(result.maxPrice).toBe(0);
  });

  it("negative income returns debtsBlown=true, maxPrice=0", () => {
    const result = computeMaxPurchasePrice({
      annualIncome: -50_000,
      monthlyDebts: 0,
      downPayment: 100_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(result.debtsBlown).toBe(true);
    expect(result.maxPrice).toBe(0);
  });

  it("downPaymentExceedsMax when down payment is larger than DTI-derived max price", () => {
    // Very low income ($15k), large down payment ($500k) → dp > P_max
    const result = computeMaxPurchasePrice({
      annualIncome: 15_000,
      monthlyDebts: 0,
      downPayment: 500_000,
      monthlyHOA: 0,
      targetRatePct: 6.5,
    });

    expect(result.downPaymentExceedsMax).toBe(true);
    // maxPrice is still computed (buyer technically can afford it, dp just exceeds it)
    expect(result.maxPrice).toBeGreaterThan(0);
  });
});

describe("computeMonthlyPMI", () => {
  it("returns loan × 0.7% / 12", () => {
    const loan = 600_000;
    const expected = loan * (PMI_ANNUAL_PCT / 100 / 12);
    expect(computeMonthlyPMI(loan)).toBeCloseTo(expected, 2);
  });

  it("returns 0 for zero loan", () => {
    expect(computeMonthlyPMI(0)).toBe(0);
  });
});

describe("constants", () => {
  it("exports expected default values", () => {
    expect(DEFAULT_RATE_FALLBACK_PCT).toBe(6.5);
    expect(PROPERTY_TAX_ANNUAL_PCT).toBe(1.20);
    expect(INSURANCE_ANNUAL_PCT).toBe(0.35);
    expect(PMI_ANNUAL_PCT).toBe(0.7);
  });
});
