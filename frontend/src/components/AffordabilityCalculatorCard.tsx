import { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../lib/AuthContext";
import {
  computeMaxPurchasePrice,
  computeMonthlyHousingCost,
  getDtiCap,
  DEFAULT_RATE_FALLBACK_PCT,
} from "../lib/affordability";
import type { InvestmentData } from "./InvestmentCard";
import type { OfferData } from "./OfferRecommendationCard";

interface Props {
  investment: InvestmentData;
  offer: OfferData | null | undefined;
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

  const hoaPrefill = offer?.hoa_equivalent_sfh_value?.monthly_hoa_fee ?? 0;
  const [hoaStr, setHoaStr] = useState<string>(String(hoaPrefill));

  useEffect(() => {
    setHoaStr(String(offer?.hoa_equivalent_sfh_value?.monthly_hoa_fee ?? 0));
  }, [offer?.hoa_equivalent_sfh_value?.monthly_hoa_fee]);

  // Null guard must come after all hooks
  if (!user) return null;

  // Read financial profile from user object (set on the Profile page)
  const annualIncome = user.annual_income ?? 0;
  const monthlyDebts = user.monthly_debts ?? 0;
  const downPayment = user.down_payment ?? 0;
  const targetRatePct =
    user.target_rate_pct ?? investment.rate_30yr_fixed ?? DEFAULT_RATE_FALLBACK_PCT;
  const monthlyHOA = parseNum(hoaStr);

  const hasIncome = annualIncome > 0;

  const result = computeMaxPurchasePrice({
    annualIncome,
    monthlyDebts,
    downPayment,
    monthlyHOA,
    targetRatePct,
  });

  const dtiPct = hasIncome ? Math.round(getDtiCap(annualIncome) * 100) : 36;

  const referencePrice = offer?.offer_recommended ?? offer?.list_price ?? null;

  const propertyMonthlyCost =
    referencePrice != null
      ? computeMonthlyHousingCost(referencePrice, downPayment, targetRatePct) + monthlyHOA
      : null;
  const monthlyDelta =
    propertyMonthlyCost != null && hasIncome && !result.debtsBlown
      ? result.hMax - propertyMonthlyCost
      : null;
  const priceGap =
    referencePrice != null && hasIncome && !result.debtsBlown && !result.downPaymentExceedsMax
      ? result.maxPrice - referencePrice
      : null;

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
        {!hasIncome ? (
          <p className="text-sm text-[var(--ink-soft)]">
            <Link to="/profile" className="font-medium text-[var(--coral)] underline">
              Set up your financial profile
            </Link>{" "}
            to see your max purchase price and affordability for this property.
          </p>
        ) : (
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
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Your down payment exceeds the max purchase price from income alone. Your binding constraint is your income.
              </div>
            ) : (
              <div className="rounded-xl bg-[var(--bg)] px-4 py-4 space-y-2">
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

        {/* HOA is property-specific — always inline */}
        <div className="max-w-[12rem]">
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

        <p className="text-xs text-[var(--ink-muted)]">
          Assumes you have the down payment plus closing costs (~2–5% of purchase) and reserves
          separate from this calculation. Not financial advice.
        </p>
      </div>
    </div>
  );
}
