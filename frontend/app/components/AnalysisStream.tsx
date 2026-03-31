import type { AnalysisEvent } from "../routes/index";

interface Props {
  events: AnalysisEvent[];
  isRunning: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  scrape_listing: "Scraping listing details",
  fetch_comps: "Fetching comparable sales",
  analyze_market: "Analyzing market data",
  recommend_offer: "Computing offer range",
};

export function AnalysisStream({ events, isRunning }: Props) {
  const textBlocks = events.filter((e) => e.type === "text");
  const toolCalls = events.filter((e) => e.type === "tool_call");
  const finalText = textBlocks.map((e) => e.text ?? "").join("");

  return (
    <div className="space-y-4">
      {/* Tool call progress */}
      {toolCalls.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Agent steps
          </h3>
          <ul className="space-y-2">
            {toolCalls.map((e, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                <span className="text-green-500">✓</span>
                {TOOL_LABELS[e.tool ?? ""] ?? e.tool}
              </li>
            ))}
            {isRunning && (
              <li className="flex items-center gap-2 text-sm text-blue-600">
                <span className="animate-spin inline-block">⟳</span>
                Working…
              </li>
            )}
          </ul>
        </div>
      )}

      {/* Final analysis text */}
      {finalText && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 prose prose-sm max-w-none">
          {finalText.split("\n").map((line, i) => (
            <p key={i} className={line.startsWith("#") ? "font-bold text-lg" : ""}>
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
