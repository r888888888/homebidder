export interface InvestmentData {
  projected_value_1yr: number | null;
  projected_value_3yr: number | null;
  projected_value_5yr: number | null;
  rate_30yr_fixed: number | null;
  as_of_date: string | null;
  hpi_yoy_assumption_pct: number | null;
  adu_potential: boolean;
  adu_rent_estimate: number | null;
  rent_controlled: boolean;
  rent_control_city: string | null;
  rent_control_implications: string | null;
  nearest_bart_station: string | null;
  bart_distance_miles: number | null;
  transit_premium_likely: boolean;
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

export function InvestmentCard({ investment }: Props) {
  return (
    <div className="card overflow-hidden fade-up">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Investment Analysis
        </p>
      </div>

      <div className="space-y-4 px-6 py-5">
        <div className="grid grid-cols-3 gap-3 rounded-xl bg-[var(--bg)] p-4 text-sm">
          <div>
            <p className="text-xs text-[var(--ink-muted)]">1yr Projected Value</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.projected_value_1yr)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">3yr Projected Value</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.projected_value_3yr)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">5yr Projected Value</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.projected_value_5yr)}</p>
          </div>
        </div>

        <p className="text-xs text-[var(--ink-muted)]">
          Assumes {fmtPct2(investment.rate_30yr_fixed)} 30yr fixed (Freddie Mac PMMS, week of {investment.as_of_date ?? "—"})
        </p>

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

        {investment.nearest_bart_station && investment.bart_distance_miles != null && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            <p className="font-semibold">Nearest Transit</p>
            <p className="text-xs">
              {investment.nearest_bart_station} ({investment.bart_distance_miles.toFixed(2)} miles)
            </p>
            {investment.transit_premium_likely && <p className="text-xs">Transit premium likely</p>}
          </div>
        )}

        <p className="text-xs text-[var(--ink-muted)]">
          Based on FHFA HPI trend — not financial advice.
        </p>
      </div>
    </div>
  );
}
