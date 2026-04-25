import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AnalysisForm } from "../components/AnalysisForm";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";

export const Route = createFileRoute("/")({
  component: HomePage,
});

export interface AnalysisEvent {
  type:
    | "status"
    | "tool_call"
    | "tool_result"
    | "text"
    | "error"
    | "done"
    | "analysis_id"
    | "validation_result";
  text?: string;
  tool?: string;
  input?: Record<string, unknown>;
  result?: Record<string, unknown> | unknown[];
  retry_after?: number | null;
  id?: number;
}

const FEATURES = [
  "Comparable sales analysis",
  "Fire, flood & seismic risk",
  "School & crime ratings",
  "BART, MUNI & Caltrain proximity",
  "Fixer renovation estimate",
];

const HOW_IT_WORKS = [
  {
    step: "1",
    title: "Enter an address",
    body: "Paste any SF Bay Area listing address. We'll normalize it and look up parcel records.",
  },
  {
    step: "2",
    title: "AI researches comps",
    body: "Our agent pulls recent sales, hazard data, tax history, and market trends in real time.",
  },
  {
    step: "3",
    title: "Get an offer range",
    body: "Receive a data-backed offer recommendation with context for your specific situation.",
  },
];

interface RateLimitInfo {
  used: number;
  limit: number;
  remaining: number;
  reset_at: string | null;
}

function formatResetTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function HomePage() {
  const navigate = useNavigate();
  const [rateLimitInfo, setRateLimitInfo] = useState<RateLimitInfo | null>(null);

  useEffect(() => {
    fetch(`${apiBase}/api/rate-limit/status`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data && setRateLimitInfo(data))
      .catch(() => {});
  }, []);

  function handleSubmit(address: string, buyerContext: string) {
    navigate({ to: "/analysis", search: { address, buyerContext } });
  }

  const rateLimitReached = rateLimitInfo !== null && rateLimitInfo.remaining === 0;

  return (
    <>
      {/* Hero */}
      <section
        className="hero-grid relative overflow-hidden bg-[var(--navy)] px-4 py-20 sm:py-28"
        style={{
          background: `
            radial-gradient(ellipse 70% 60% at 50% -10%, rgba(221,95,59,0.18) 0%, transparent 70%),
            var(--navy)
          `,
        }}
      >
        <div className="content-wrap relative z-10 flex flex-col items-center text-center">
          <div className="fade-up mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium text-white/60 backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--coral)]" />
            SF Bay Area
          </div>

          <h1 className="display-title fade-up stagger-1 mb-5 text-4xl font-bold leading-tight text-white sm:text-5xl">
            Know exactly what to offer{" "}
            <span className="text-[var(--coral)]">
              before you walk in the door.
            </span>
          </h1>

          <p className="fade-up stagger-2 mb-10 max-w-lg text-base text-white/60 sm:text-lg">
            AI-powered offer analysis backed by real comp data, CA hazard zones,
            and live market trends.
          </p>

          {/* Form card */}
          <div className="fade-up stagger-3 card w-full p-6 sm:p-8">
            <AnalysisForm
              onSubmit={handleSubmit}
              isRunning={false}
              rateLimitReached={rateLimitReached}
            />
          </div>

          {/* Rate limit counter */}
          {rateLimitInfo && (
            <p
              className={`mt-3 text-xs ${
                rateLimitReached
                  ? "text-red-300/80"
                  : rateLimitInfo.remaining <= 2
                    ? "text-yellow-300/70"
                    : "text-white/40"
              }`}
            >
              {rateLimitReached
                ? rateLimitInfo.reset_at
                  ? `Resets at ${formatResetTime(rateLimitInfo.reset_at)}`
                  : "Try again tomorrow"
                : `${rateLimitInfo.remaining} of ${rateLimitInfo.limit} free analyses remaining today`}
            </p>
          )}

          {/* Dev shortcut — only rendered in development builds */}
          {import.meta.env.DEV && (
            <button
              type="button"
              onClick={() =>
                handleSubmit("319 Plymouth Ave, San Francisco, CA 94112", "")
              }
              className="mt-4 rounded-lg border border-dashed border-white/20 bg-white/5 px-4 py-1.5 text-xs text-white/50 hover:border-white/40 hover:text-white/70"
            >
              Dev: analyze 310 Plymouth Ave
            </button>
          )}

          {/* Feature chips */}
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {FEATURES.map((f, i) => (
              <span
                key={f}
                className={`fade-up stagger-${Math.min(i + 1, 5)} rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/50`}
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      </section>

      <div className="page-wrap py-14">
        <section>
          <h2 className="display-title fade-up mb-8 text-center text-2xl font-bold text-[var(--ink)] sm:text-3xl">
            How it works
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {HOW_IT_WORKS.map(({ step, title, body }, i) => (
              <div key={step} className={`card card-hover p-6 fade-up stagger-${i + 1}`}>
                <div
                  className="mb-4 flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white"
                  style={{
                    background: `linear-gradient(135deg, var(--navy-mid), var(--navy))`,
                    boxShadow: `0 0 0 3px rgba(221,95,59,0.15)`,
                  }}
                >
                  {step}
                </div>
                <h3 className="mb-2 text-base font-semibold text-[var(--ink)]">
                  {title}
                </h3>
                <p className="text-sm leading-relaxed text-[var(--ink-soft)]">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
