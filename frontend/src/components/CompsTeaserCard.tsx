import { Link } from "@tanstack/react-router";
import type { CompData } from "./CompsCard";

interface Props {
  comps: CompData[];
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

export function CompsTeaserCard({ comps }: Props) {
  const prices = comps.map((c) => c.sold_price).filter((p): p is number => p != null);
  const psqfts = comps.map((c) => c.price_per_sqft).filter((p): p is number => p != null);

  const sortedPrices = [...prices].sort((a, b) => a - b);
  const priceLow = sortedPrices[0] ?? null;
  const priceHigh = sortedPrices[sortedPrices.length - 1] ?? null;
  const priceMid = median(prices);
  const medianPsqft = median(psqfts);

  const isEmpty = comps.length === 0;

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

      <div className="space-y-4 px-6 py-5">
        {isEmpty ? (
          <p className="text-sm text-[var(--ink-soft)]">No comparable sales found nearby.</p>
        ) : (
          <>
            <p className="text-sm text-[var(--ink-soft)]">
              {comps.length} comparable sale{comps.length !== 1 ? "s" : ""} found nearby.
            </p>

            {/* Price range summary */}
            <div className="grid grid-cols-3 gap-3 rounded-xl bg-[var(--bg)] p-4">
              <div className="text-center">
                <p className="text-xs text-[var(--ink-muted)] mb-1">Low</p>
                <p className="text-sm font-semibold text-[var(--ink)]">{fmtUsd(priceLow)}</p>
              </div>
              <div className="text-center border-x border-[var(--line)]">
                <p className="text-xs text-[var(--ink-muted)] mb-1">Mid</p>
                <p className="text-sm font-semibold text-[var(--ink)]">{fmtUsd(priceMid)}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--ink-muted)] mb-1">High</p>
                <p className="text-sm font-semibold text-[var(--ink)]">{fmtUsd(priceHigh)}</p>
              </div>
            </div>

            {medianPsqft != null && (
              <p className="text-xs text-[var(--ink-muted)]">
                Median $/sqft: <span className="font-semibold text-[var(--ink)]">{fmtUsd(medianPsqft)}</span>
              </p>
            )}
          </>
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
              Unlock Comparable Sales
            </p>
          </div>
          <p className="text-xs text-[var(--ink-soft)] mb-3">
            Full comp table with address, sale date, price, and $/sqft is available on Investor and Agent plans.
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
