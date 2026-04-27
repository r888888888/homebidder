import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AnalysisStream } from "../components/AnalysisStream";
import { useToast } from "../components/Toast";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";
import type { AnalysisEvent } from "./index";

interface LimitReachedInfo {
  tier: string;
  limit: number;
  used: number;
}

export const Route = createFileRoute("/analysis")({
  component: AnalysisPage,
  validateSearch: (search: Record<string, unknown>) => ({
    address: String(search.address ?? ""),
    buyerContext: String(search.buyerContext ?? ""),
    forceRefresh: search.forceRefresh === "1",
  }),
});

export function AnalysisPage() {
  const { address, buyerContext, forceRefresh } = useSearch({ from: "/analysis" });
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [isRunning, setIsRunning] = useState(true);
  const [refreshKey, setRefreshKey] = useState(forceRefresh ? 1 : 0);
  const [limitReached, setLimitReached] = useState<LimitReachedInfo | null>(null);
  const toast = useToast();
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!address) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setEvents([]);
    setIsRunning(true);
    setLimitReached(null);

    let cancelled = false;

    async function stream() {
      let res: Response;
      try {
        res = await fetch(`${apiBase}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ address, buyer_context: buyerContext, force_refresh: refreshKey > 0 }),
          signal: controller.signal,
        });
      } catch {
        if (!cancelled) {
          toast.error("Could not reach the analysis server. Is it running?");
          setIsRunning(false);
        }
        return;
      }

      if (res.status === 429) {
        if (!cancelled) {
          try {
            const body = await res.json();
            const detail = body?.detail;
            if (detail?.code === "MONTHLY_LIMIT_REACHED") {
              setLimitReached({ tier: detail.tier, limit: detail.limit, used: detail.used });
            } else {
              toast.error("Monthly analysis limit reached.");
            }
          } catch {
            toast.error("Monthly analysis limit reached.");
          }
          setIsRunning(false);
        }
        return;
      }

      if (!res.ok || !res.body) {
        if (!cancelled) {
          toast.error(`Server error: ${res.statusText}`);
          setIsRunning(false);
        }
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done || cancelled) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event: AnalysisEvent = JSON.parse(line.slice(6));
              setEvents((prev) => [...prev, event]);
              if (event.type === "error") toast.error(event.text ?? "An error occurred.");
              if (event.type === "done") setIsRunning(false);
            } catch {
              // skip malformed
            }
          }
        }
      } catch {
        // AbortError from abort() or stream read error — stop reading
      }

      if (!cancelled) setIsRunning(false);
    }

    stream();
    return () => { cancelled = true; controller.abort(); };
  }, [address, buyerContext, refreshKey, toast]);

  return (
    <main className="page-wrap py-10">
      {/* Header */}
      <div className="mb-8">
        <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Analysis
        </p>
        <h1 className="display-title text-2xl font-bold text-[var(--ink)] sm:text-3xl">
          {address}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={isRunning}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink)] shadow-sm hover:bg-[var(--bg)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg
              className={isRunning ? "animate-spin" : undefined}
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
              <path d="M21 3v5h-5" />
              <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
              <path d="M8 16H3v5" />
            </svg>
            {isRunning ? "Refreshing\u2026" : "Refresh"}
          </button>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink)] shadow-sm no-underline hover:bg-[var(--bg)]"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 5l-7 7 7 7M5 12h14" />
            </svg>
            New analysis
          </Link>
        </div>
      </div>

      <AnalysisStream events={events} isRunning={isRunning} />

      {limitReached && (
        <div className="mt-8 rounded-lg border border-[var(--coral)] bg-red-50 p-4 text-sm">
          <p className="font-semibold text-red-700">
            Monthly limit reached ({limitReached.used} of {limitReached.limit} analyses used).
          </p>
          {limitReached.tier === "anonymous" ? (
            <p className="mt-1 text-red-600">
              <a href="/register" className="font-semibold underline hover:text-red-800">
                Sign up
              </a>{" "}
              for a free account to get more analyses each month.
            </p>
          ) : (
            <p className="mt-1 text-red-600">
              <a href="/pricing" className="font-semibold underline hover:text-red-800">
                Upgrade your plan
              </a>{" "}
              to get more analyses each month.
            </p>
          )}
        </div>
      )}
    </main>
  );
}
