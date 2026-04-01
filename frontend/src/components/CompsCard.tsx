export interface CompData {
  address: string;
  city: string;
  state: string;
  zip_code: string;
  sold_price: number | null;
  list_price: number | null;
  sold_date: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  price_per_sqft: number | null;
  pct_over_asking: number | null;
  distance_miles: number | null;
  url: string;
  source: string;
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function fmtDist(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(2)} mi`;
}

interface Props {
  comps: CompData[];
}

export function CompsCard({ comps }: Props) {
  return (
    <div className="card overflow-hidden fade-up">
      <div className="border-b border-[var(--line)] px-6 py-4">
        <p className="mb-0.5 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Comparable Sales
        </p>
        <h2 className="display-title text-base font-semibold text-[var(--ink)]">
          Recent Sold Comps
        </h2>
      </div>

      {comps.length === 0 ? (
        <div className="px-6 py-5 text-sm text-[var(--ink-soft)]">
          No comparable sales found nearby.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--line)] text-left text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
                <th className="px-4 py-3">Address</th>
                <th className="px-4 py-3 text-right">Sold Price</th>
                <th className="px-4 py-3 text-right">Sqft</th>
                <th className="px-4 py-3 text-right">$/Sqft</th>
                <th className="px-4 py-3 text-right">% Over Ask</th>
                <th className="px-4 py-3 text-right">Distance</th>
                <th className="px-4 py-3">Sold Date</th>
              </tr>
            </thead>
            <tbody>
              {comps.map((comp, i) => {
                const pct = comp.pct_over_asking;
                const pctColor =
                  pct == null
                    ? ""
                    : pct >= 0
                    ? "text-[var(--green)]"
                    : "text-[var(--coral)]";

                return (
                  <tr
                    key={i}
                    className="border-b border-[var(--line)] last:border-0 hover:bg-[var(--surface-raised)]"
                  >
                    <td className="px-4 py-3 text-[var(--ink)]">
                      {comp.url ? (
                        <a
                          href={comp.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline decoration-dotted hover:text-[var(--green)]"
                        >
                          {comp.address}
                        </a>
                      ) : (
                        comp.address
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-[var(--ink)]">
                      {fmtUsd(comp.sold_price)}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--ink)]">
                      {fmt(comp.sqft)}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--ink)]">
                      {comp.price_per_sqft != null ? fmtUsd(comp.price_per_sqft) : "—"}
                    </td>
                    <td className={`px-4 py-3 text-right font-semibold ${pctColor}`}>
                      {fmtPct(pct)}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--ink-soft)]">
                      {fmtDist(comp.distance_miles)}
                    </td>
                    <td className="px-4 py-3 text-[var(--ink-soft)]">
                      {comp.sold_date || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
