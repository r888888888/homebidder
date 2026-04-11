export interface CrimeData {
  violent_count: number | null;
  property_count: number | null;
  total_count: number | null;
  radius_miles: number;
  period_days: number;
  source: string | null;
  top_violent_types: string[];
  top_property_types: string[];
}

interface Props {
  crime: CrimeData;
}

interface ColorSet {
  border: string;
  bg: string;
  text: string;
}

function riskColors(count: number | null, low: number, high: number): ColorSet {
  if (count == null) {
    return { border: "border-[var(--line)]", bg: "bg-[var(--bg)]", text: "text-[var(--ink)]" };
  }
  if (count <= low) {
    return { border: "border-emerald-200", bg: "bg-emerald-50", text: "text-emerald-900" };
  }
  if (count <= high) {
    return { border: "border-amber-200", bg: "bg-amber-50", text: "text-amber-900" };
  }
  return { border: "border-red-200", bg: "bg-red-50", text: "text-red-900" };
}

export function CrimeCard({ crime }: Props) {
  const vc = riskColors(crime.violent_count, 2, 8);
  const pc = riskColors(crime.property_count, 5, 20);

  return (
    <div className="card overflow-hidden fade-up">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Crime — {crime.radius_miles} mi radius · {crime.period_days}-day window
        </p>
        {crime.source && (
          <span className="text-xs text-[var(--ink-muted)]">{crime.source}</span>
        )}
      </div>

      <div className="space-y-3 px-6 py-5">
        {crime.violent_count != null ? (
          <div
            className={`rounded-xl border px-4 py-3 text-sm ${vc.border} ${vc.bg} ${vc.text}`}
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold">Violent Crime</p>
              <p className="text-lg font-bold">{crime.violent_count}</p>
            </div>
            {crime.top_violent_types.length > 0 && (
              <p className="mt-1 text-xs opacity-80">
                {crime.top_violent_types.join(" · ")}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-muted)]">Violent crime data unavailable</p>
        )}

        {crime.property_count != null ? (
          <div
            className={`rounded-xl border px-4 py-3 text-sm ${pc.border} ${pc.bg} ${pc.text}`}
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold">Property Crime</p>
              <p className="text-lg font-bold">{crime.property_count}</p>
            </div>
            {crime.top_property_types.length > 0 && (
              <p className="mt-1 text-xs opacity-80">
                {crime.top_property_types.join(" · ")}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-muted)]">Property crime data unavailable</p>
        )}

        <p className="text-xs text-[var(--ink-muted)]">
          Incident counts within {crime.radius_miles} miles, last {crime.period_days} days.
          {crime.source && ` Source: ${crime.source}.`}
          {" "}Not a guarantee of personal safety — conditions vary by block.
        </p>
      </div>
    </div>
  );
}
