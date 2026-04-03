export interface InvestmentData {
  gross_yield_pct: number | null;
  price_to_rent_ratio: number | null;
  monthly_cashflow_estimate: number | null;
  adu_gross_yield_boost_pct: number | null;
  projected_value_1yr: number | null;
  projected_value_3yr: number | null;
  projected_value_5yr: number | null;
  investment_rating: "Buy" | "Hold" | "Overpriced";
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

const RATING_STYLES: Record<InvestmentData["investment_rating"], string> = {
  Buy: "bg-emerald-100 border-emerald-300 text-emerald-900",
  Hold: "bg-amber-100 border-amber-300 text-amber-900",
  Overpriced: "bg-red-100 border-red-300 text-red-900",
};

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function fmtPct(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function fmtPct2(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(2)}%`;
}

function fmtNum(n: number | null): string {
  if (n == null) return "—";
  return n.toFixed(1);
}

export function InvestmentCard({ investment }: Props) {
  const ratingStyle = RATING_STYLES[investment.investment_rating] ?? RATING_STYLES.Hold;

  return (
    <div className="card overflow-hidden fade-up">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Investment Analysis
        </p>
        <span className={`rounded-full border px-3 py-0.5 text-xs font-semibold ${ratingStyle}`}>
          {investment.investment_rating}
        </span>
      </div>

      <div className="space-y-4 px-6 py-5">
        <div className="grid grid-cols-3 gap-3 rounded-xl bg-[var(--bg)] p-4 text-sm">
          <div>
            <p className="text-xs text-[var(--ink-muted)]">Gross Yield</p>
            <p className="font-semibold text-[var(--ink)]">{fmtPct(investment.gross_yield_pct)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">Price-to-Rent Ratio</p>
            <p className="font-semibold text-[var(--ink)]">{fmtNum(investment.price_to_rent_ratio)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)]">Monthly Cashflow</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(investment.monthly_cashflow_estimate)}</p>
          </div>
        </div>

        <p className="text-xs text-[var(--ink-muted)]">
          Assumes {fmtPct2(investment.rate_30yr_fixed)} 30yr fixed (Freddie Mac PMMS, week of {investment.as_of_date ?? "—"})
        </p>

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

        {investment.adu_potential && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <p className="font-semibold">ADU Potential</p>
            <p className="text-xs">Estimated ADU rent: {fmtUsd(investment.adu_rent_estimate)} / month</p>
            <p className="text-xs">Boosted gross yield: {fmtPct(investment.adu_gross_yield_boost_pct)}</p>
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
          Based on FHFA HPI trend and RentCast estimate — not financial advice.
        </p>
      </div>
    </div>
  );
}
