import { useState, useEffect } from "react";
import { useAuth } from "../lib/AuthContext";
import {
  computeMaxPurchasePrice,
  getDtiCap,
  DEFAULT_RATE_FALLBACK_PCT,
} from "../lib/affordability";
import type { InvestmentData } from "./InvestmentCard";
import type { OfferData } from "./OfferRecommendationCard";

interface Props {
  investment: InvestmentData;
  offer: OfferData | null | undefined;
}

interface StoredAffordability {
  annualIncome: number | null;
  monthlyDebts: number;
  downPayment: number | null;
  targetRatePct: number;
}

function parseNum(s: string): number {
  const n = Number(s.replace(/[^0-9.]/g, ""));
  return isNaN(n) ? 0 : n;
}

function fmtUsdK(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}k`;
  return `$${Math.round(n)}`;
}

function fmtUsdFull(n: number): string {
  return "$" + Math.round(n).toLocaleString("en-US");
}

function fmtMonthly(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

export function AffordabilityCalculatorCard({ investment, offer }: Props) {
  const { user } = useAuth();

  const storageKey = user ? `homebidder_affordability_${user.id}` : null;
  const hoaPrefill = offer?.hoa_equivalent_sfh_value?.monthly_hoa_fee ?? 0;

  // Lazy-initialize state from localStorage so values are available on first render
  const [incomeStr, setIncomeStr] = useState<string>(() => {
    if (!storageKey) return "";
    try {
      const s = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Partial<StoredAffordability>;
      return s.annualIncome != null ? String(s.annualIncome) : "";
    } catch { return ""; }
  });

  const [debtsStr, setDebtsStr] = useState<string>(() => {
    if (!storageKey) return "0";
    try {
      const s = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Partial<StoredAffordability>;
      return s.monthlyDebts != null ? String(s.monthlyDebts) : "0";
    } catch { return "0"; }
  });

  const [downPaymentStr, setDownPaymentStr] = useState<string>(() => {
    if (!storageKey) return "";
    try {
      const s = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Partial<StoredAffordability>;
      return s.downPayment != null ? String(s.downPayment) : "";
    } catch { return ""; }
  });

  const [rateStr, setRateStr] = useState<string>(() => {
    if (!storageKey) {
      return String(investment.rate_30yr_fixed ?? DEFAULT_RATE_FALLBACK_PCT);
    }
    try {
      const s = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Partial<StoredAffordability>;
      if (s.targetRatePct != null) return String(s.targetRatePct);
    } catch { /* fall through */ }
    return String(investment.rate_30yr_fixed ?? DEFAULT_RATE_FALLBACK_PCT);
  });

  // HOA is property-specific — always from offer prefill, never from localStorage
  const [hoaStr, setHoaStr] = useState<string>(String(hoaPrefill));

  // Sync HOA when offer data changes (e.g. on re-mount with a new analysis)
  useEffect(() => {
    setHoaStr(String(offer?.hoa_equivalent_sfh_value?.monthly_hoa_fee ?? 0));
  }, [offer?.hoa_equivalent_sfh_value?.monthly_hoa_fee]);

  // Persist buyer-specific fields on every change
  useEffect(() => {
    if (!storageKey) return;
    try {
      const income = parseNum(incomeStr);
      const debts = parseNum(debtsStr);
      const dp = parseNum(downPaymentStr);
      const rate = parseNum(rateStr) || DEFAULT_RATE_FALLBACK_PCT;
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          annualIncome: income > 0 ? income : null,
          monthlyDebts: debts,
          downPayment: dp > 0 ? dp : null,
          targetRatePct: rate,
        } satisfies StoredAffordability)
      );
    } catch { /* ignore */ }
  }, [storageKey, incomeStr, debtsStr, downPaymentStr, rateStr]);

  // Derived values
  const annualIncome = parseNum(incomeStr);
  const monthlyDebts = parseNum(debtsStr);
  const downPayment = parseNum(downPaymentStr);
  const monthlyHOA = parseNum(hoaStr);
  const targetRatePct = parseNum(rateStr) || DEFAULT_RATE_FALLBACK_PCT;

  const hasIncome = annualIncome > 0;

  const result = computeMaxPurchasePrice({
    annualIncome,
    monthlyDebts,
    downPayment,
    monthlyHOA,
    targetRatePct,
  });

  const dtiPct = hasIncome ? Math.round(getDtiCap(annualIncome) * 100) : 36;

  // Monthly comparison: H_max vs property cost (monthly_buy_cost + HOA)
  const propertyMonthlyCost =
    investment.monthly_buy_cost != null
      ? investment.monthly_buy_cost + monthlyHOA
      : null;
  const monthlyDelta =
    propertyMonthlyCost != null && hasIncome && !result.debtsBlown
      ? result.hMax - propertyMonthlyCost
      : null;

  // Price gap vs recommended offer (fall back to list price)
  const referencePrice =
    offer?.offer_recommended ?? offer?.list_price ?? null;
  const priceGap =
    referencePrice != null && hasIncome && !result.debtsBlown && !result.downPaymentExceedsMax
      ? result.maxPrice - referencePrice
      : null;

  // Null guard must come after all hooks
  if (!user) return null;

  const inputClass =
    "w-full rounded-xl border border-[var(--card-border)] bg-white py-2.5 pl-8 pr-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--coral)]";
  const iconClass =
    "pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-[var(--ink-muted)] select-none";

  return (
    <div className="card overflow-hidden fade-up">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Affordability Calculator
        </p>
      </div>

      <div className="space-y-5 px-6 py-5">
        {/* Input grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="aff-income"
              className="mb-1.5 block text-xs font-medium text-[var(--ink-soft)]"
            >
              Annual income
            </label>
            <div className="relative">
              <span className={iconClass} aria-hidden="true">$</span>
              <input
                id="aff-income"
                aria-label="Annual income"
                type="text"
                inputMode="numeric"
                value={incomeStr}
                onChange={(e) => setIncomeStr(e.target.value)}
                placeholder="150,000"
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="aff-debts"
              className="mb-1.5 block text-xs font-medium text-[var(--ink-soft)]"
            >
              Monthly debts
            </label>
            <div className="relative">
              <span className={iconClass} aria-hidden="true">$</span>
              <input
                id="aff-debts"
                aria-label="Monthly debts"
                type="text"
                inputMode="numeric"
                value={debtsStr}
                onChange={(e) => setDebtsStr(e.target.value)}
                placeholder="0"
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="aff-down"
              className="mb-1.5 block text-xs font-medium text-[var(--ink-soft)]"
            >
              Down payment
            </label>
            <div className="relative">
              <span className={iconClass} aria-hidden="true">$</span>
              <input
                id="aff-down"
                aria-label="Down payment"
                type="text"
                inputMode="numeric"
                value={downPaymentStr}
                onChange={(e) => setDownPaymentStr(e.target.value)}
                placeholder="160,000"
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="aff-hoa"
              className="mb-1.5 block text-xs font-medium text-[var(--ink-soft)]"
            >
              Property HOA / mo
            </label>
            <div className="relative">
              <span className={iconClass} aria-hidden="true">$</span>
              <input
                id="aff-hoa"
                aria-label="Property HOA / mo"
                type="text"
                inputMode="numeric"
                value={hoaStr}
                onChange={(e) => setHoaStr(e.target.value)}
                placeholder="0"
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="aff-rate"
              className="mb-1.5 block text-xs font-medium text-[var(--ink-soft)]"
            >
              Target rate
            </label>
            <div className="relative">
              <input
                id="aff-rate"
                aria-label="Target rate"
                type="text"
                inputMode="decimal"
                value={rateStr}
                onChange={(e) => setRateStr(e.target.value)}
                className={inputClass + " pl-3 pr-7"}
              />
              <span
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[var(--ink-muted)] select-none"
                aria-hidden="true"
              >
                %
              </span>
            </div>
          </div>
        </div>

        {/* Outputs */}
        {hasIncome && (
          <div className="space-y-3">
            {result.debtsBlown ? (
              <div
                data-testid="debts-blown"
                className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
              >
                Your monthly debts and HOA exceed the maximum housing budget at the{" "}
                <strong>{dtiPct}% DTI cap</strong>.
              </div>
            ) : result.downPaymentExceedsMax ? (
              <div
                className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
              >
                Your down payment exceeds the max purchase price from income alone. Your binding constraint is your income.
              </div>
            ) : (
              <div className="rounded-xl bg-[var(--bg)] px-4 py-4 space-y-2">
                {/* Max price headline */}
                <div>
                  <p className="text-xs text-[var(--ink-muted)] uppercase tracking-wide">
                    Max purchase price
                  </p>
                  <p
                    data-testid="max-price-value"
                    className="text-2xl font-bold text-[var(--ink)]"
                  >
                    {fmtUsdFull(result.maxPrice)}
                  </p>
                </div>

                {/* DTI cap sub-line with tooltip */}
                <div className="flex items-center gap-1.5">
                  <span
                    data-testid="dti-cap-label"
                    className="text-xs text-[var(--ink-soft)]"
                  >
                    DTI cap: {dtiPct}% (your income bracket)
                  </span>
                  <div className="group relative">
                    <button
                      type="button"
                      aria-label="About DTI cap"
                      aria-describedby="dti-cap-tooltip"
                      className="flex h-4 w-4 cursor-pointer items-center justify-center rounded-full border border-[var(--line)] text-[0.6rem] text-[var(--ink-muted)] leading-none hover:border-[var(--ink-soft)] focus:outline-none focus:ring-1 focus:ring-[var(--coral)]"
                    >
                      i
                    </button>
                    <div
                      id="dti-cap-tooltip"
                      role="tooltip"
                      className="invisible absolute left-1/2 top-6 z-10 w-64 -translate-x-1/2 rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-xs text-[var(--ink-soft)] shadow-md group-hover:visible group-focus-within:visible"
                    >
                      Higher incomes can sustain higher DTI ratios because fixed essentials don't scale linearly with housing. HomeBidder's tiered caps are an informed product judgment, not a regulatory standard.
                    </div>
                  </div>
                </div>

                {/* Down payment % and PMI indicator */}
                {downPayment > 0 && (
                  <p
                    data-testid="dp-pct-line"
                    className="text-xs text-[var(--ink-soft)]"
                  >
                    Down payment {fmtUsdFull(downPayment)} (
                    {(result.impliedDpPct * 100).toFixed(0)}% of max price)
                    {result.regime === "with_pmi"
                      ? ` — includes ~${fmtUsdFull(result.monthlyPMI)}/mo PMI`
                      : ""}
                  </p>
                )}
              </div>
            )}

            {/* Monthly comparison */}
            {monthlyDelta != null && (
              <div
                data-testid="monthly-comparison"
                data-positive={monthlyDelta >= 0 ? "true" : "false"}
                className={`rounded-xl border px-4 py-3 text-sm ${
                  monthlyDelta >= 0
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                    : "border-amber-200 bg-amber-50 text-amber-900"
                }`}
              >
                {monthlyDelta >= 0 ? (
                  <>
                    This property's housing cost (
                    <strong>${fmtMonthly(propertyMonthlyCost!)}/mo</strong>) fits inside your max
                    housing budget (<strong>${fmtMonthly(result.hMax)}/mo</strong>) with{" "}
                    <strong>${fmtMonthly(monthlyDelta)}/mo</strong> of margin.
                  </>
                ) : (
                  <>
                    This property's housing cost (
                    <strong>${fmtMonthly(propertyMonthlyCost!)}/mo</strong>) is{" "}
                    <strong>${fmtMonthly(Math.abs(monthlyDelta))}/mo</strong> over your max budget (
                    <strong>${fmtMonthly(result.hMax)}/mo</strong>).
                  </>
                )}
              </div>
            )}

            {/* Price gap (secondary) */}
            {priceGap != null && (
              <div
                data-testid="price-gap"
                className={`text-xs px-4 py-2 rounded-xl ${
                  priceGap >= 0
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-amber-50 text-amber-800"
                }`}
              >
                {priceGap >= 0 ? (
                  <>
                    Max price {fmtUsdK(result.maxPrice)} vs. recommended offer{" "}
                    {fmtUsdK(referencePrice!)} — {fmtUsdK(priceGap)} of headroom.
                  </>
                ) : (
                  <>
                    Max price {fmtUsdK(result.maxPrice)} vs. recommended offer{" "}
                    {fmtUsdK(referencePrice!)} — {fmtUsdK(Math.abs(priceGap))} over your max.
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Disclaimer */}
        <p className="text-xs text-[var(--ink-muted)]">
          Assumes you have the down payment plus closing costs (~2–5% of purchase) and reserves
          separate from this calculation. Not financial advice.
        </p>
      </div>
    </div>
  );
}
