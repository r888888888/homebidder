import { useEffect, useState } from "react";

export interface CompData {
  address: string;
  unit?: string | null;
  city: string;
  state: string;
  zip_code: string;
  sold_price: number | null;
  list_price: number | null;
  sold_date: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  lot_size: number | null;
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

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  // s is "YYYY-MM-DD" from the backend; parse as UTC to avoid timezone shifts
  const d = new Date(s + "T00:00:00Z");
  if (isNaN(d.getTime())) return s;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

interface Props {
  comps: CompData[];
}

const NEAREST_COUNT = 3;
const PAGE_SIZE = 10;

function compAddressLabel(comp: CompData): string {
  const addr = comp.address || "";
  const unit = comp.unit?.toString().trim();
  if (!unit) return addr;
  const lower = addr.toLowerCase();
  // Avoid duplicating unit text already present in the address string.
  if (lower.includes(`#${unit.toLowerCase()}`) || lower.includes(`unit ${unit.toLowerCase()}`)) {
    return addr;
  }
  return `${addr} #${unit}`;
}

export function CompsCard({ comps }: Props) {
  const [page, setPage] = useState(1);

  // Sort by distance ascending, nulls last
  const sorted = [...comps].sort((a, b) => {
    if (a.distance_miles == null && b.distance_miles == null) return 0;
    if (a.distance_miles == null) return 1;
    if (b.distance_miles == null) return -1;
    return a.distance_miles - b.distance_miles;
  });

  // Nearest N comps that actually have a distance get highlighted
  const nearestAddresses = new Set(
    sorted
      .filter((c) => c.distance_miles != null)
      .slice(0, NEAREST_COUNT)
      .map((c) => c.address)
  );
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const pageComps = sorted.slice(pageStart, pageStart + PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [comps]);

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
                <th className="px-4 py-3 text-right">Bed/Bath</th>
                <th className="px-4 py-3 text-right">Sqft</th>
                <th className="px-4 py-3 text-right">$/Sqft</th>
                <th className="px-4 py-3 text-right">% Over Ask</th>
                <th className="px-4 py-3 text-right">Distance</th>
                <th className="px-4 py-3">Sold Date</th>
              </tr>
            </thead>
            <tbody>
              {pageComps.map((comp, i) => {
                const pct = comp.pct_over_asking;
                const pctColor =
                  pct == null
                    ? ""
                    : pct >= 0
                    ? "text-[var(--green)]"
                    : "text-[var(--coral)]";

                const bedBath =
                  comp.bedrooms != null || comp.bathrooms != null
                    ? `${comp.bedrooms ?? "—"}bd / ${comp.bathrooms ?? "—"}ba`
                    : "—";

                const isNearest = nearestAddresses.has(comp.address);
                const addressLabel = compAddressLabel(comp);

                return (
                  <tr
                    key={`${comp.address}-${pageStart + i}`}
                    data-nearest={isNearest ? "true" : undefined}
                    className={`border-b border-[var(--line)] last:border-0 ${
                      isNearest
                        ? "bg-[color-mix(in_srgb,var(--green)_6%,transparent)] hover:bg-[color-mix(in_srgb,var(--green)_12%,transparent)]"
                        : "hover:bg-[var(--surface-raised)]"
                    }`}
                  >
                    <td className="px-4 py-3 text-[var(--ink)]">
                      <span className="flex items-center gap-1.5">
                        {isNearest && (
                          <span
                            className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--green)]"
                            aria-label="nearest comp"
                          />
                        )}
                        {comp.url ? (
                          <a
                            href={comp.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline decoration-dotted hover:text-[var(--green)]"
                          >
                            {addressLabel}
                          </a>
                        ) : (
                          addressLabel
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-[var(--ink)]">
                      {fmtUsd(comp.sold_price)}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--ink-soft)]">
                      {bedBath}
                    </td>
                    <td
                      className="px-4 py-3 text-right text-[var(--ink)]"
                      title={comp.lot_size != null ? `Lot size: ${fmt(comp.lot_size)} sqft` : undefined}
                    >
                      {fmt(comp.sqft)}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--ink)]">
                      {comp.price_per_sqft != null ? fmtUsd(comp.price_per_sqft) : "—"}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-semibold ${pctColor}`}
                      title={comp.list_price != null ? `List price: ${fmtUsd(comp.list_price)}` : undefined}
                    >
                      {fmtPct(pct)}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--ink-soft)]">
                      {fmtDist(comp.distance_miles)}
                    </td>
                    <td className="px-4 py-3 text-[var(--ink-soft)]">
                      {fmtDate(comp.sold_date)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {comps.length > PAGE_SIZE && (
        <div className="flex items-center justify-between border-t border-[var(--line)] px-4 py-3 text-sm">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="rounded-md border border-[var(--line)] px-3 py-1.5 text-[var(--ink)] transition disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <p className="text-[var(--ink-soft)]">
            Page {currentPage} of {totalPages}
          </p>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="rounded-md border border-[var(--line)] px-3 py-1.5 text-[var(--ink)] transition disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
