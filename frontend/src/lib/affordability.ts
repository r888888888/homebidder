export const PROPERTY_TAX_ANNUAL_PCT = 1.20;
export const INSURANCE_ANNUAL_PCT = 0.35;
export const PMI_ANNUAL_PCT = 0.7;
export const MIN_DP_PCT_NO_PMI = 0.20;
export const DEFAULT_RATE_FALLBACK_PCT = 6.5;

export const DTI_TIERS = [
  { maxIncome: 100_000, cap: 0.36 },
  { maxIncome: 200_000, cap: 0.40 },
  { maxIncome: 300_000, cap: 0.43 },
  { maxIncome: Infinity, cap: 0.45 },
];

export function getDtiCap(annualIncome: number): number {
  if (annualIncome < 100_000) return 0.36;
  if (annualIncome < 200_000) return 0.40;
  if (annualIncome < 300_000) return 0.43;
  return 0.45;
}

function amortizationFactor(monthlyRate: number, n = 360): number {
  if (monthlyRate === 0) return 1 / n;
  const pow = Math.pow(1 + monthlyRate, n);
  return (monthlyRate * pow) / (pow - 1);
}

export function computeMonthlyPMI(loan: number): number {
  return loan * (PMI_ANNUAL_PCT / 100 / 12);
}

export interface AffordabilityResult {
  maxPrice: number;
  regime: "no_pmi" | "with_pmi" | "boundary";
  impliedDpPct: number;
  monthlyPMI: number;
  hMax: number;
  debtsBlown: boolean;
  downPaymentExceedsMax: boolean;
}

export interface AffordabilityInputs {
  annualIncome: number;
  monthlyDebts: number;
  downPayment: number;
  monthlyHOA: number;
  targetRatePct: number;
}

const BLOWN: AffordabilityResult = {
  maxPrice: 0,
  regime: "no_pmi",
  impliedDpPct: 0,
  monthlyPMI: 0,
  hMax: 0,
  debtsBlown: true,
  downPaymentExceedsMax: false,
};

export function computeMaxPurchasePrice(inputs: AffordabilityInputs): AffordabilityResult {
  const { annualIncome, monthlyDebts, downPayment, monthlyHOA, targetRatePct } = inputs;

  if (annualIncome <= 0) return BLOWN;

  const dti = getDtiCap(annualIncome);
  const monthlyIncome = annualIncome / 12;
  const hMax = dti * monthlyIncome - monthlyDebts - monthlyHOA;

  if (hMax <= 0) return { ...BLOWN, hMax };

  const r = targetRatePct / 100 / 12;
  const M = amortizationFactor(r);
  const tax_m = PROPERTY_TAX_ANNUAL_PCT / 100 / 12;
  const ins_m = INSURANCE_ANNUAL_PCT / 100 / 12;
  const pmi_m = PMI_ANNUAL_PCT / 100 / 12;

  // Regime A: assume no PMI (dp_pct >= 20%)
  const P_max_A = (hMax + downPayment * M) / (M + tax_m + ins_m);
  const dpPctA = P_max_A > 0 ? downPayment / P_max_A : 0;

  if (dpPctA >= MIN_DP_PCT_NO_PMI) {
    return {
      maxPrice: Math.max(0, Math.round(P_max_A / 1000) * 1000),
      regime: "no_pmi",
      impliedDpPct: dpPctA,
      monthlyPMI: 0,
      hMax,
      debtsBlown: false,
      downPaymentExceedsMax: downPayment > P_max_A,
    };
  }

  // Regime B: assume PMI applies (dp_pct < 20%)
  const P_max_B = (hMax + downPayment * (M + pmi_m)) / (M + pmi_m + tax_m + ins_m);
  const dpPctB = P_max_B > 0 ? downPayment / P_max_B : 0;

  if (dpPctB < MIN_DP_PCT_NO_PMI) {
    const loan = Math.max(0, P_max_B - downPayment);
    return {
      maxPrice: Math.max(0, Math.round(P_max_B / 1000) * 1000),
      regime: "with_pmi",
      impliedDpPct: dpPctB,
      monthlyPMI: computeMonthlyPMI(loan),
      hMax,
      debtsBlown: false,
      downPaymentExceedsMax: downPayment > P_max_B,
    };
  }

  // Boundary: exactly 20% down
  const P_max_boundary = downPayment / MIN_DP_PCT_NO_PMI;
  return {
    maxPrice: Math.round(P_max_boundary / 1000) * 1000,
    regime: "boundary",
    impliedDpPct: MIN_DP_PCT_NO_PMI,
    monthlyPMI: 0,
    hMax,
    debtsBlown: false,
    downPaymentExceedsMax: false,
  };
}
