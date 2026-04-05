export interface ValidationResult {
  actual_sold_price: number;
  estimated_price: number;
  error_dollars: number;
  error_pct: number;
  within_ci: boolean;
  sold_date: string | null;
  address: string | null;
}

function fmt(n: number): string {
  return "$" + Math.abs(n).toLocaleString("en-US");
}

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function colorClasses(errorPct: number, withinCi: boolean): string {
  const abs = Math.abs(errorPct);
  if (withinCi || abs <= 5) {
    return "bg-emerald-50 border-emerald-300 text-emerald-800";
  }
  if (abs <= 15) {
    return "bg-amber-50 border-amber-300 text-amber-800";
  }
  return "bg-red-50 border-red-300 text-[var(--coral)]";
}

function accentBar(errorPct: number, withinCi: boolean): string {
  const abs = Math.abs(errorPct);
  if (withinCi || abs <= 5) return "bg-emerald-400";
  if (abs <= 15) return "bg-amber-400";
  return "bg-red-400";
}

export function ValidationBanner({ result }: { result: ValidationResult }) {
  const { actual_sold_price, estimated_price, error_dollars, error_pct, within_ci, sold_date } = result;
  const absPct = Math.abs(error_pct);
  const sign = error_dollars >= 0 ? "+" : "-";
  const direction = error_dollars >= 0 ? "above" : "below";

  return (
    <div
      className={`relative flex overflow-hidden rounded-xl border ${colorClasses(error_pct, within_ci)} shadow-sm`}
    >
      <div className={`w-1.5 shrink-0 ${accentBar(error_pct, within_ci)}`} />
      <div className="px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest opacity-70 mb-1">
          Validation Mode — This Property Has Sold
        </p>
        <p className="text-sm font-medium">
          Sold for <span className="font-bold">{fmt(actual_sold_price)}</span>
          {sold_date && <span className="font-normal opacity-80"> on {fmtDate(sold_date)}</span>}
          {" — "}our estimate was <span className="font-bold">{fmt(estimated_price)}</span>
          {" "}
          <span className="font-bold">
            ({sign}{absPct.toFixed(1)}% {direction}, {sign === "+" ? "+" : "-"}{fmt(error_dollars)} off)
          </span>
        </p>
        {within_ci && (
          <p className="text-xs mt-1 opacity-75">
            Actual sale was within our confidence interval.
          </p>
        )}
      </div>
    </div>
  );
}
