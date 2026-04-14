import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AnalysisStream } from "../components/AnalysisStream";
import { useToast } from "../components/Toast";
import { apiBase } from "../lib/api";
import type { AnalysisEvent } from "./index";

export const Route = createFileRoute("/analysis")({
  component: AnalysisPage,
  validateSearch: (search: Record<string, unknown>) => ({
    address: String(search.address ?? ""),
    buyerContext: String(search.buyerContext ?? ""),
  }),
});

export function AnalysisPage() {
  const { address, buyerContext } = useSearch({ from: "/analysis" });
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [isRunning, setIsRunning] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const toast = useToast();
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!address) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setEvents([]);
    setIsRunning(true);

    let cancelled = false;

    async function stream() {
      let res: Response;
      try {
        res = await fetch(`${apiBase}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
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
          toast.error("Daily analysis limit reached. Please try again tomorrow.");
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
      {/* Header row */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Analysis
          </p>
          <h1 className="display-title text-2xl font-bold text-[var(--ink)] sm:text-3xl">
            {address}
          </h1>
        </div>
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          disabled={isRunning}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-[var(--card-border)] bg-white px-4 py-2 text-sm font-semibold text-[var(--ink)] shadow-sm hover:bg-[var(--bg)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <svg
            className={isRunning ? "animate-spin" : undefined}
            width="14"
            height="14"
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
          {isRunning ? "Refreshing\u2026" : "Refresh analysis"}
        </button>
        <Link
          to="/"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-[var(--card-border)] bg-white px-4 py-2 text-sm font-semibold text-[var(--ink)] shadow-sm no-underline hover:bg-[var(--bg)]"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 5l-7 7 7 7M5 12h14" />
          </svg>
          New analysis
        </Link>
      </div>

      <AnalysisStream events={events} isRunning={isRunning} />
    </main>
  );
}
