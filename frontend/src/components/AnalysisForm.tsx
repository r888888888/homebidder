import { useState } from "react";
import type { FormEvent } from "react";

interface Props {
  onSubmit: (address: string, buyerContext: string) => void;
  isRunning: boolean;
  rateLimitReached?: boolean;
}

export function AnalysisForm({ onSubmit, isRunning, rateLimitReached = false }: Props) {
  const [address, setAddress] = useState("");
  const [buyerContext, setBuyerContext] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!address.trim() || isRunning || rateLimitReached) return;
    onSubmit(address.trim(), buyerContext.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="address"
          className="mb-1.5 block text-sm font-semibold text-[var(--ink)]"
        >
          Property address
        </label>
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-[var(--ink-muted)]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20 10c0 6-8 13-8 13S4 16 4 10a8 8 0 0 1 16 0Z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          </span>
          <input
            id="address"
            type="text"
            required
            placeholder="450 Sanchez St, San Francisco, CA 94114"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            disabled={isRunning}
            autoComplete="off"
            data-1p-ignore
            className="w-full rounded-xl border border-[var(--card-border)] bg-white py-3 pl-10 pr-4 text-sm shadow-sm placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
          />
        </div>
      </div>

      <div>
        <label
          htmlFor="buyer-context"
          className="mb-1.5 block text-sm font-semibold text-[var(--ink)]"
        >
          Buyer notes{" "}
          <span className="font-normal text-[var(--ink-muted)]">(optional)</span>
        </label>
        <textarea
          id="buyer-context"
          rows={2}
          placeholder="e.g. multiple offers expected, need to close in 30 days, flexible on repairs"
          value={buyerContext}
          onChange={(e) => setBuyerContext(e.target.value)}
          disabled={isRunning}
          className="w-full resize-none rounded-xl border border-[var(--card-border)] bg-white px-4 py-3 text-sm shadow-sm placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
        />
      </div>

      <button
        type="submit"
        disabled={isRunning || !address.trim() || rateLimitReached}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--coral)] px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[var(--coral-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {rateLimitReached ? (
          "Monthly limit reached"
        ) : isRunning ? (
          <>
            <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            Analyzing&hellip;
          </>
        ) : (
          <>
            Analyze listing
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </>
        )}
      </button>
    </form>
  );
}
