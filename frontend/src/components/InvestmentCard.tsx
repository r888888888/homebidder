export interface NearbySchool {
  name: string;
  type: "elementary" | "middle" | "high";
  grades: string | null;
  distance_miles: number;
  math_pct: number | null;
  ela_pct: number | null;
}

export interface InvestmentData {
  purchase_price: number | null;
  projected_value_10yr: number | null;
  projected_value_20yr: number | null;
  projected_value_30yr: number | null;
  rate_30yr_fixed: number | null;
  as_of_date: string | null;
  hpi_yoy_assumption_pct: number | null;
  monthly_buy_cost: number | null;
  monthly_rent_equivalent: number | null;
  monthly_cost_diff: number | null;
  opportunity_cost_10yr: number | null;
  opportunity_cost_20yr: number | null;
  opportunity_cost_30yr: number | null;
  adu_potential: boolean;
  adu_rent_estimate: number | null;
  rent_controlled: boolean;
  rent_control_city: string | null;
  rent_control_implications: string | null;
  nearest_bart_station: string | null;
  bart_distance_miles: number | null;
  nearest_muni_stop: string | null;
  muni_distance_miles: number | null;
  transit_premium_likely: boolean;
  nearby_schools: NearbySchool[];
}

interface Props {
  investment: InvestmentData;
}

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function fmtPct2(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(2)}%`;
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

export function InvestmentCard({ investment }: Props) {
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
        {/* Appreciation projections */}
        <div className="grid grid-cols-4 gap-3 rounded-xl bg-[var(--bg)] p-4 text-sm">
          <div>
            <p className="text-xs text-[var(--ink-muted)]">Today</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.purchase_price)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">10yr Projected Value</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.projected_value_10yr)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">20yr Projected Value</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.projected_value_20yr)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">30yr Projected Value</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.projected_value_30yr)}</p>
          </div>
        </div>

        <p className="text-xs text-[var(--ink-muted)]">
          Fair value {fmtUsd(investment.purchase_price)} projected at {fmtPct2(investment.hpi_yoy_assumption_pct)}/yr (5yr avg HPI) · Assumes {fmtPct2(investment.rate_30yr_fixed)} 30yr fixed (Freddie Mac PMMS, week of {investment.as_of_date ?? "—"})
        </p>

        {/* Opportunity cost vs. renting */}
        <div className="grid grid-cols-3 gap-3 rounded-xl bg-[var(--bg)] p-4 text-sm">
          <div>
            <p className="text-xs text-[var(--ink-muted)]">10yr Opp. Cost</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.opportunity_cost_10yr)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">20yr Opp. Cost</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.opportunity_cost_20yr)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">30yr Opp. Cost</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.opportunity_cost_30yr)}</p>
          </div>
        </div>

        {investment.monthly_rent_equivalent != null ? (
          <p className={`text-xs ${diffPositive ? "text-amber-600" : "text-emerald-600"}`}>
            Buying costs {fmtUsd(investment.monthly_buy_cost)}/mo vs.{" "}
            {fmtUsd(investment.monthly_rent_equivalent)}/mo to rent (diff:{" "}
            {investment.monthly_cost_diff != null && investment.monthly_cost_diff > 0 ? "+" : ""}
            {fmtUsd(investment.monthly_cost_diff)}/mo invested at 10%/yr; assumes 3%/yr rent growth)
          </p>
        ) : (
          <p className="text-xs text-[var(--ink-muted)]">
            Rent comparison unavailable (Census data not found for this ZIP)
          </p>
        )}

        {investment.adu_potential && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <p className="font-semibold">ADU Potential</p>
            <p className="text-xs">Estimated ADU rent: {fmtUsd(investment.adu_rent_estimate)} / month</p>
          </div>
        )}

        {investment.rent_controlled && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <p className="font-semibold">Rent Control</p>
            <p className="text-xs">{investment.rent_control_city}</p>
            <p className="text-xs">{investment.rent_control_implications}</p>
          </div>
        )}

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

        <p className="text-xs text-[var(--ink-muted)]">
          Based on FHFA HPI trend and 20% down, 30yr fixed, 0.5% annual maintenance, 10% stock return, 3%/yr rent growth — not financial advice.
        </p>
      </div>
    </div>
  );
}
