export interface OfferData {
  list_price: number | null;
  fair_value_estimate: number | null;
  offer_low: number | null;
  offer_recommended: number | null;
  offer_high: number | null;
  posture: "competitive" | "at-market" | "negotiating";
  spread_vs_list_pct: number | null;
  median_pct_over_asking: number | null;
  pct_sold_over_asking: number | null;
  offer_review_advisory: string | null;
  contingency_recommendation: {
    waive_appraisal: boolean;
    waive_loan: boolean;
    keep_inspection: boolean;
  } | null;
}

const POSTURE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  competitive: {
    bg: "bg-[var(--coral)]/10 border-[var(--coral)]/30",
    text: "text-[var(--coral)]",
    label: "Competitive",
  },
  "at-market": {
    bg: "bg-[var(--green)]/10 border-[var(--green)]/30",
    text: "text-[var(--green)]",
    label: "At-Market",
  },
  negotiating: {
    bg: "bg-blue-50 border-blue-200",
    text: "text-blue-600",
    label: "Negotiating",
  },
};

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  return "$" + n.toLocaleString("en-US");
}

function fmtPct(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function ContingencyRow({ label, recommended }: { label: string; recommended: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 text-sm">
      <span className="text-[var(--ink)]">{label}</span>
      <span
        className={recommended ? "font-semibold text-[var(--coral)]" : "text-[var(--ink-muted)]"}
      >
        {recommended ? "Recommended" : "Not recommended"}
      </span>
    </div>
  );
}

interface Props {
  offer: OfferData;
}

export function OfferRecommendationCard({ offer }: Props) {
  const posture = POSTURE_STYLES[offer.posture] ?? POSTURE_STYLES["at-market"];
  const hasOverbidStats =
    offer.median_pct_over_asking != null || offer.pct_sold_over_asking != null;
  const contingency = offer.contingency_recommendation;

  // Range bar: position of recommended within [low, high]
  const low = offer.offer_low ?? 0;
  const high = offer.offer_high ?? 0;
  const rec = offer.offer_recommended ?? 0;
  const range = high - low;
  const recPct = range > 0 ? ((rec - low) / range) * 100 : 50;

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Offer Recommendation
        </p>
        <span
          className={`rounded-full border px-3 py-0.5 text-xs font-semibold ${posture.bg} ${posture.text}`}
        >
          {posture.label}
        </span>
      </div>

      <div className="px-6 py-5 space-y-6">
        {/* Offer range */}
        <div>
          <div className="flex items-end justify-between mb-1">
            <span className="text-xs text-[var(--ink-muted)]">Conservative</span>
            <span className="text-xs text-[var(--ink-muted)]">Aggressive</span>
          </div>

          {/* Range bar */}
          <div className="relative h-2 rounded-full bg-[var(--bg)] border border-[var(--line)] mb-3">
            <div
              className="absolute top-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 border-[var(--coral)] bg-white shadow"
              style={{ left: `calc(${recPct}% - 8px)` }}
              title={`Recommended: ${fmtUsd(offer.offer_recommended)}`}
            />
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--ink-muted)] mb-0.5">Low</p>
              <p className="text-base font-semibold text-[var(--ink)]">{fmtUsd(offer.offer_low)}</p>
            </div>
            <div className="border-x border-[var(--line)]">
              <p className="text-[10px] uppercase tracking-wider text-[var(--ink-muted)] mb-0.5">Recommended</p>
              <p className={`text-lg font-bold ${posture.text}`}>{fmtUsd(offer.offer_recommended)}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--ink-muted)] mb-0.5">High</p>
              <p className="text-base font-semibold text-[var(--ink)]">{fmtUsd(offer.offer_high)}</p>
            </div>
          </div>
        </div>

        {/* Fair value + list price */}
        <div className="grid grid-cols-2 gap-4 rounded-xl bg-[var(--bg)] p-4 text-sm">
          <div>
            <p className="text-xs text-[var(--ink-muted)] mb-0.5">Fair Value Estimate</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(offer.fair_value_estimate)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-muted)] mb-0.5">List Price</p>
            <p className="font-semibold text-[var(--ink)]">{fmtUsd(offer.list_price)}</p>
          </div>
        </div>

        {/* Overbid stats */}
        {hasOverbidStats && (
          <div className="grid grid-cols-2 gap-4 rounded-xl bg-[var(--bg)] p-4 text-sm">
            <div>
              <p className="text-xs text-[var(--ink-muted)] mb-0.5">Median Overbid</p>
              <p className="font-semibold text-[var(--ink)]">{fmtPct(offer.median_pct_over_asking)}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--ink-muted)] mb-0.5">Sold Over Asking</p>
              <p className="font-semibold text-[var(--ink)]">{fmtPct(offer.pct_sold_over_asking)}</p>
            </div>
          </div>
        )}

        {/* Offer review advisory */}
        {offer.offer_review_advisory && (
          <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
            <span>{offer.offer_review_advisory}</span>
          </div>
        )}

        {/* Contingency recommendations */}
        {contingency && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Contingencies
            </p>
            <div className="divide-y divide-[var(--line)]">
              <ContingencyRow label="Keep inspection" recommended={contingency.keep_inspection} />
              <ContingencyRow label="Waive appraisal" recommended={contingency.waive_appraisal} />
              <ContingencyRow label="Waive loan" recommended={contingency.waive_loan} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
