import { useEffect, useRef, useState } from "react";

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
  disabled_indices?: number[];
}

interface Props {
  data: FixerAnalysisData;
  analysisId?: number;
  initialDisabledIndices?: number[];
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

function deriveVerdict(savings: number, turnkeyValue: number): FixerAnalysisData["verdict"] {
  const ratio = turnkeyValue > 0 ? savings / turnkeyValue : 0;
  if (ratio > 0.03) return "cheaper_fixer";
  if (ratio < -0.03) return "cheaper_turnkey";
  return "comparable";
}

export function FixerAnalysisCard({ data, analysisId, initialDisabledIndices }: Props) {
  const [disabledIndices, setDisabledIndices] = useState<Set<number>>(
    new Set(initialDisabledIndices ?? []),
  );

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function persistToggles(indices: Set<number>) {
    if (analysisId === undefined) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetch(`/api/analyses/${analysisId}/renovation-toggles`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disabled_indices: [...indices] }),
      });
    }, 500);
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  function toggleItem(index: number) {
    setDisabledIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      persistToggles(next);
      return next;
    });
  }

  // Derive all totals from currently active items
  const activeItems = data.line_items.filter((_, i) => !disabledIndices.has(i));
  const activeLow = activeItems.reduce((sum, x) => sum + x.low, 0);
  const activeHigh = activeItems.reduce((sum, x) => sum + x.high, 0);
  const activeMid = Math.round((activeLow + activeHigh) / 2);
  const allInMid = data.offer_recommended + activeMid;
  const renoAdjustedOffer = data.offer_recommended - activeMid;
  const savings = data.turnkey_value - allInMid;
  const verdict = deriveVerdict(savings, data.turnkey_value);

  const absSavings = Math.abs(savings);
  const isWinner = verdict === "cheaper_fixer";
  const isLoser = verdict === "cheaper_turnkey";

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-base font-semibold text-[var(--ink)]">Fixer Analysis</h3>
        <span
          className={`rounded-full border px-3 py-0.5 text-xs font-medium ${VERDICT_STYLES[verdict]}`}
        >
          {VERDICT_LABELS[verdict]}
        </span>
      </div>

      {/* Cost comparison */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-[var(--surface)] p-3">
          <p className="mb-1 text-xs text-[var(--ink-soft)]">All-in fixer (mid)</p>
          <p className="text-base font-semibold text-[var(--ink)]">{fmt(allInMid)}</p>
          <p className="text-xs text-[var(--ink-soft)]">
            {fmt(data.offer_recommended)} offer + {fmt(activeMid)} reno
          </p>
        </div>
        <div className="rounded-lg bg-[var(--surface)] p-3">
          <p className="mb-1 text-xs text-[var(--ink-soft)]">Fair Value</p>
          <p className="text-base font-semibold text-[var(--ink)]">{fmt(data.turnkey_value)}</p>
          <p className="text-xs text-[var(--ink-soft)]">As-is (condition-adjusted)</p>
        </div>
      </div>

      {/* Reno-adjusted offer */}
      <div className="mb-4 rounded-lg bg-[var(--surface)] p-3">
        <p className="mb-1 text-xs text-[var(--ink-soft)]">Reno-adjusted offer</p>
        <p className="text-base font-semibold text-[var(--ink)]">{fmt(renoAdjustedOffer)}</p>
        <p className="text-xs text-[var(--ink-soft)]">
          {fmt(data.offer_recommended)} base − {fmt(activeMid)} reno
        </p>
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
          {data.line_items.map((item, i) => {
            const disabled = disabledIndices.has(i);
            return (
              <div key={item.category} className="flex cursor-pointer items-center gap-3 py-3 text-sm" onClick={() => toggleItem(i)}>
                {/* Custom animated checkbox */}
                <div
                  className={`flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded border-2 transition-[background-color,border-color] duration-150 ease-out ${
                    !disabled
                      ? "border-[var(--coral)] bg-[var(--coral)]"
                      : "border-zinc-300 bg-white"
                  }`}
                  role="checkbox"
                  aria-checked={!disabled}
                  aria-label={`Toggle ${item.category}`}
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); toggleItem(i); }}
                  onKeyDown={(e) => {
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      toggleItem(i);
                    }
                  }}
                >
                  <svg
                    className="h-3 w-3 text-white"
                    style={{
                      opacity: !disabled ? 1 : 0,
                      transform: !disabled ? "scale(1)" : "scale(0.3)",
                      transition: "opacity 150ms ease-out, transform 250ms cubic-bezier(0.34, 1.56, 0.64, 1)",
                    }}
                    viewBox="0 0 12 12"
                    fill="none"
                    aria-hidden="true"
                  >
                    <polyline
                      points="1.5,6 5,9.5 10.5,2"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
                <span className={`flex-1 text-[var(--ink)] transition-opacity duration-150 ${disabled ? "opacity-40 line-through" : ""}`}>
                  {item.category}
                </span>
                <span className={`text-[var(--ink-soft)] transition-opacity duration-150 ${disabled ? "opacity-40 line-through" : ""}`}>
                  ${item.low.toLocaleString("en-US")}–${item.high.toLocaleString("en-US")}
                </span>
              </div>
            );
          })}
          <div className="flex justify-between py-3 text-sm font-medium">
            <span className="text-[var(--ink)]">Total</span>
            <span className="text-[var(--ink)]">
              ${activeLow.toLocaleString("en-US")}–${activeHigh.toLocaleString("en-US")}
            </span>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-xs text-[var(--ink-soft)]">{data.disclaimer}</p>
    </div>
  );
}
