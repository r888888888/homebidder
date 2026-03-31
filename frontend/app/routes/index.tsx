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

function HomePage() {
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  async function handleSubmit(url: string, buyerContext: string) {
    setEvents([]);
    setIsRunning(true);

    const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${apiBase}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, buyer_context: buyerContext }),
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
    <main className="max-w-3xl mx-auto px-4 py-10">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">
        What should I offer?
      </h1>
      <p className="text-gray-500 mb-8">
        Paste a Zillow or Redfin listing URL and our AI agent will research comps
        and recommend a realistic offer price.
      </p>

      <AnalysisForm onSubmit={handleSubmit} isRunning={isRunning} />

      {events.length > 0 && (
        <div className="mt-8">
          <AnalysisStream events={events} isRunning={isRunning} />
        </div>
      )}
    </main>
  );
}
