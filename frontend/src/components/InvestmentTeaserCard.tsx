import { Link } from "@tanstack/react-router";
import type { InvestmentData } from "./InvestmentCard";

interface Props {
  investment: InvestmentData;
}

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function schoolProficiencyColor(pct: number | null): string {
  if (pct == null) return "text-[var(--ink-muted)]";
  if (pct >= 60) return "text-emerald-700";
  if (pct >= 40) return "text-amber-700";
  return "text-red-700";
}

const SCHOOL_TYPE_LABEL: Record<string, string> = {
  elementary: "Elementary",
  middle: "Middle",
  high: "High School",
};

export function InvestmentTeaserCard({ investment }: Props) {
  const diffPositive =
    investment.monthly_cost_diff != null && investment.monthly_cost_diff > 0;

  return (
    <div className="card overflow-hidden fade-up">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Investment Analysis
        </p>
      </div>

      <div className="space-y-4 px-6 py-5">
        {/* Monthly cost comparison */}
        {investment.monthly_rent_equivalent != null ? (
          <>
            <div className="grid grid-cols-2 gap-3 rounded-xl bg-[var(--bg)] p-4 text-sm">
              <div>
                <p className="text-xs text-[var(--ink-muted)]">Buy (monthly)</p>
                <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.monthly_buy_cost)}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--ink-muted)]">Rent equivalent</p>
                <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.monthly_rent_equivalent)}</p>
              </div>
            </div>
            <p className={`text-xs ${diffPositive ? "text-amber-600" : "text-emerald-600"}`}>
              Buying costs {fmtUsd(investment.monthly_buy_cost)}/mo vs.{" "}
              {fmtUsd(investment.monthly_rent_equivalent)}/mo to rent (assumes 3%/yr rent growth)
            </p>
          </>
        ) : (
          <p className="text-xs text-[var(--ink-muted)]">
            Rent comparison unavailable (Census data not found for this ZIP)
          </p>
        )}

        {/* ADU potential */}
        {investment.adu_potential && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <p className="font-semibold">ADU Potential</p>
            <p className="text-xs">Estimated ADU rent: {fmtUsd(investment.adu_rent_estimate)} / month</p>
          </div>
        )}

        {/* Rent control */}
        {investment.rent_controlled && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <p className="font-semibold">Rent Control</p>
            <p className="text-xs">{investment.rent_control_city}</p>
            <p className="text-xs">{investment.rent_control_implications}</p>
          </div>
        )}

        {/* Transit */}
        {(investment.nearest_bart_station || investment.nearest_muni_stop) && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            <p className="font-semibold mb-1">Nearest Transit</p>
            {investment.nearest_bart_station && investment.bart_distance_miles != null && (
              <p className="text-xs">
                <span className="font-medium text-sky-700 uppercase tracking-wide mr-1.5">BART</span>
                {investment.nearest_bart_station} ({investment.bart_distance_miles.toFixed(2)} mi)
              </p>
            )}
            {investment.nearest_muni_stop && investment.muni_distance_miles != null && (
              <p className="text-xs">
                <span className="font-medium text-sky-700 uppercase tracking-wide mr-1.5">MUNI</span>
                {investment.nearest_muni_stop} ({investment.muni_distance_miles.toFixed(2)} mi)
              </p>
            )}
            {investment.transit_premium_likely && (
              <p className="text-xs mt-1">Transit premium likely</p>
            )}
          </div>
        )}

        {/* Schools */}
        {investment.nearby_schools && investment.nearby_schools.length > 0 && (
          <div className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-900">
            <p className="font-semibold mb-2">Nearby Schools</p>
            <div className="space-y-1.5">
              {investment.nearby_schools.map((school) => (
                <div key={school.name} className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-medium text-violet-700 uppercase tracking-wide mr-1.5">
                      {SCHOOL_TYPE_LABEL[school.type] ?? school.type}
                    </span>
                    <span className="text-xs">{school.name}</span>
                    {school.grades && (
                      <span className="text-xs text-violet-600 ml-1">({school.grades})</span>
                    )}
                  </div>
                  <div className="text-xs text-right shrink-0">
                    <span className="text-violet-600">{school.distance_miles != null ? `${school.distance_miles.toFixed(2)} mi · ` : ""}</span>
                    <span className={schoolProficiencyColor(school.math_pct)}>
                      Math {school.math_pct != null ? `${school.math_pct.toFixed(0)}%` : "—"}
                    </span>
                    <span className="text-violet-400 mx-1">·</span>
                    <span className={schoolProficiencyColor(school.ela_pct)}>
                      ELA {school.ela_pct != null ? `${school.ela_pct.toFixed(0)}%` : "—"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-violet-500 mt-2">
              % students meeting/exceeding CA standards (CAASPP). Green ≥60%, yellow 40–59%, red &lt;40%.
            </p>
          </div>
        )}

        {/* Upgrade upsell */}
        <div className="rounded-xl border border-[var(--line)] bg-[var(--bg)] px-4 py-4">
          <div className="flex items-center gap-2 mb-2">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-[var(--ink-muted)]"
              aria-hidden="true"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <p className="text-sm font-semibold text-[var(--ink)]">
              Unlock Investment Projections
            </p>
          </div>
          <p className="text-xs text-[var(--ink-soft)] mb-3">
            10/20/30-year appreciation projections and opportunity cost analysis are available on Investor and Agent plans.
          </p>
          <Link
            to="/pricing"
            className="inline-flex items-center rounded-lg bg-[var(--coral)] px-3 py-1.5 text-xs font-semibold text-white no-underline hover:opacity-90"
          >
            Upgrade to Investor
          </Link>
        </div>
      </div>
    </div>
  );
}
