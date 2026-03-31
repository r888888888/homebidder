import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AnalysisForm } from "../components/AnalysisForm";
import { AnalysisStream } from "../components/AnalysisStream";

export const Route = createFileRoute("/")({
  component: HomePage,
});

export interface AnalysisEvent {
  type: "status" | "tool_call" | "text" | "done";
  text?: string;
  tool?: string;
  input?: Record<string, unknown>;
}

const FEATURES = [
  "0.3-mile comp radius",
  "Prop 13 tax impact",
  "CA hazard zones",
  "Overbid trend analysis",
  "BART proximity",
  "ADU potential",
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

function HomePage() {
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const hasResults = events.length > 0;

  async function handleSubmit(address: string, buyerContext: string) {
    setEvents([]);
    setIsRunning(true);

    const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${apiBase}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address, buyer_context: buyerContext }),
    });

    if (!res.ok || !res.body) {
      setEvents([{ type: "text", text: `Error: ${res.statusText}` }]);
      setIsRunning(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event: AnalysisEvent = JSON.parse(line.slice(6));
          setEvents((prev) => [...prev, event]);
          if (event.type === "done") setIsRunning(false);
        } catch {
          // skip malformed
        }
      }
    }

    setIsRunning(false);
  }

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
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium text-white/60 backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--coral)]" />
            SF Bay Area
          </div>

          <h1 className="display-title mb-5 text-4xl font-bold leading-tight text-white sm:text-5xl">
            Know exactly what to offer{" "}
            <span className="text-[var(--coral)]">before you walk in the door.</span>
          </h1>

          <p className="mb-10 max-w-lg text-base text-white/60 sm:text-lg">
            AI-powered offer analysis backed by real comp data, Prop&nbsp;13 tax
            estimates, CA hazard zones, and live market trends.
          </p>

          {/* Form card */}
          <div className="card w-full p-6 sm:p-8">
            <AnalysisForm onSubmit={handleSubmit} isRunning={isRunning} />
          </div>

          {/* Feature chips */}
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {FEATURES.map((f) => (
              <span
                key={f}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/50"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      </section>

      <div className="page-wrap py-14">
        {/* Results */}
        {hasResults && (
          <section className="mb-14">
            <AnalysisStream events={events} isRunning={isRunning} />
          </section>
        )}

        {/* How it works */}
        {!hasResults && (
          <section>
            <h2 className="display-title mb-8 text-center text-2xl font-bold text-[var(--ink)] sm:text-3xl">
              How it works
            </h2>
            <div className="grid gap-4 sm:grid-cols-3">
              {HOW_IT_WORKS.map(({ step, title, body }) => (
                <div key={step} className="card p-6">
                  <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-full bg-[var(--navy)] text-sm font-bold text-white">
                    {step}
                  </div>
                  <h3 className="mb-2 text-base font-semibold text-[var(--ink)]">
                    {title}
                  </h3>
                  <p className="text-sm leading-relaxed text-[var(--ink-soft)]">{body}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
