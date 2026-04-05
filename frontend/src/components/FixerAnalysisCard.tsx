export interface RenovationLineItem {
  category: string;
  low: number;
  high: number;
}

export interface FixerAnalysisData {
  is_fixer: boolean;
  fixer_signals: string[];
  offer_recommended: number;
  renovation_estimate_low: number;
  renovation_estimate_mid: number;
  renovation_estimate_high: number;
  line_items: RenovationLineItem[];
  all_in_fixer_low: number;
  all_in_fixer_mid: number;
  all_in_fixer_high: number;
  turnkey_value: number;
  renovated_fair_value: number;
  implied_equity_mid: number;
  verdict: "cheaper_fixer" | "cheaper_turnkey" | "comparable";
  savings_mid: number;
  scope_notes?: string | null;
  disclaimer: string;
}

interface Props {
  data: FixerAnalysisData;
}

const VERDICT_STYLES: Record<FixerAnalysisData["verdict"], string> = {
  cheaper_fixer: "border-emerald-300 bg-emerald-50 text-emerald-800",
  comparable: "border-amber-300 bg-amber-50 text-amber-800",
  cheaper_turnkey: "border-red-300 bg-red-50 text-red-800",
};

const VERDICT_LABELS: Record<FixerAnalysisData["verdict"], string> = {
  cheaper_fixer: "Fixer May Win",
  comparable: "Comparable Cost",
  cheaper_turnkey: "Turn-key Cheaper",
};

function fmt(n: number): string {
  return "$" + Math.abs(n).toLocaleString("en-US");
}

export function FixerAnalysisCard({ data }: Props) {
  const totalLow = data.renovation_estimate_low;
  const totalHigh = data.renovation_estimate_high;
  const absSavings = Math.abs(data.savings_mid);
  const isWinner = data.verdict === "cheaper_fixer";
  const isLoser = data.verdict === "cheaper_turnkey";
  const equityPositive = data.implied_equity_mid >= 0;

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-base font-semibold text-[var(--ink)]">Fixer Analysis</h3>
        <span
          className={`rounded-full border px-3 py-0.5 text-xs font-medium ${VERDICT_STYLES[data.verdict]}`}
        >
          {VERDICT_LABELS[data.verdict]}
        </span>
      </div>

      {/* Cost comparison */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-[var(--surface)] p-3">
          <p className="mb-1 text-xs text-[var(--ink-soft)]">All-in fixer (mid)</p>
          <p className="text-base font-semibold text-[var(--ink)]">{fmt(data.all_in_fixer_mid)}</p>
          <p className="text-xs text-[var(--ink-soft)]">
            {fmt(data.offer_recommended)} offer + {fmt(data.renovation_estimate_mid)} reno
          </p>
        </div>
        <div className="rounded-lg bg-[var(--surface)] p-3">
          <p className="mb-1 text-xs text-[var(--ink-soft)]">Fair Value</p>
          <p className="text-base font-semibold text-[var(--ink)]">{fmt(data.turnkey_value)}</p>
          <p className="text-xs text-[var(--ink-soft)]">As-is (condition-adjusted)</p>
        </div>
      </div>

      {/* Post-renovation value + implied equity */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-[var(--surface)] p-3">
          <p className="mb-1 text-xs text-[var(--ink-soft)]">Post-reno value (est.)</p>
          <p className="text-base font-semibold text-[var(--ink)]">{fmt(data.renovated_fair_value)}</p>
          <p className="text-xs text-[var(--ink-soft)]">Fair value after renovation</p>
        </div>
        <div className="rounded-lg bg-[var(--surface)] p-3">
          <p className="mb-1 text-xs text-[var(--ink-soft)]">Implied equity (mid)</p>
          <p className={`text-base font-semibold ${equityPositive ? "text-emerald-700" : "text-red-700"}`}>
            {equityPositive ? "+" : "−"}{fmt(data.implied_equity_mid)}
          </p>
          <p className="text-xs text-[var(--ink-soft)]">Post-reno value − all-in cost</p>
        </div>
      </div>

      {/* vs fair value delta */}
      {(isWinner || isLoser) && (
        <div
          className={`mb-4 rounded-lg border px-3 py-2 text-sm font-medium ${
            isWinner
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {isWinner
            ? `Save ~${fmt(absSavings)} vs buying turn-key`
            : `Costs ~${fmt(absSavings)} more than buying turn-key`}
        </div>
      )}

      {/* Renovation line items */}
      <div className="mb-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
          Renovation estimate
        </p>
        <div className="divide-y divide-[var(--border)]">
          {data.line_items.map((item) => (
            <div key={item.category} className="flex justify-between py-1.5 text-sm">
              <span className="text-[var(--ink)]">{item.category}</span>
              <span className="text-[var(--ink-soft)]">
                ${item.low.toLocaleString("en-US")}–${item.high.toLocaleString("en-US")}
              </span>
            </div>
          ))}
          <div className="flex justify-between py-1.5 text-sm font-medium">
            <span className="text-[var(--ink)]">Total</span>
            <span className="text-[var(--ink)]">
              ${totalLow.toLocaleString("en-US")}–${totalHigh.toLocaleString("en-US")}
            </span>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-xs text-[var(--ink-soft)]">{data.disclaimer}</p>
    </div>
  );
}
