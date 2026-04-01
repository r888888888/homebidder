import type { AnalysisEvent } from "../routes/index";
import { PropertySummaryCard, type PropertyData } from "./PropertySummaryCard";
import { NeighborhoodCard, type NeighborhoodData } from "./NeighborhoodCard";
import { CompsCard, type CompData } from "./CompsCard";

interface Props {
  events: AnalysisEvent[];
  isRunning: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  lookup_property_by_address: "Looking up property",
  fetch_neighborhood_context: "Fetching neighborhood & tax data",
  fetch_comps: "Fetching comparable sales",
  analyze_market: "Analyzing market data",
  recommend_offer: "Computing offer range",
};

export function AnalysisStream({ events, isRunning }: Props) {
  const textBlocks = events.filter((e) => e.type === "text");
  const toolCalls = events.filter((e) => e.type === "tool_call");
  const finalText = textBlocks.map((e) => e.text ?? "").join("");

  const propertyEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "lookup_property_by_address"
  );
  const propertyData = propertyEvent?.result as PropertyData | undefined;

  const neighborhoodEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "fetch_neighborhood_context"
  );
  const neighborhoodData = neighborhoodEvent?.result as NeighborhoodData | undefined;

  const compsEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "fetch_comps"
  );
  const compsData = compsEvent?.result as CompData[] | undefined;

  return (
    <div className="space-y-4 fade-up">
      {/* Property summary card */}
      {propertyData && <PropertySummaryCard property={propertyData} />}

      {/* Neighborhood & Prop 13 card */}
      {neighborhoodData && (
        <NeighborhoodCard
          neighborhood={neighborhoodData}
          purchasePrice={(propertyData?.price as number | null) ?? null}
          neighborhoodName={(propertyData?.neighborhoods as string | null) ?? null}
        />
      )}

      {/* Comps table */}
      {compsData && <CompsCard comps={compsData} />}

      {/* Agent step progress */}
      {toolCalls.length > 0 && (
        <div className="card p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Agent steps
          </p>
          <ol className="space-y-2">
            {toolCalls.map((e, i) => (
              <li key={i} className="flex items-center gap-3 text-sm text-[var(--ink)]">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--green)] text-white">
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M2 6l3 3 5-5" />
                  </svg>
                </span>
                <span>{TOOL_LABELS[e.tool ?? ""] ?? e.tool}</span>
              </li>
            ))}
            {isRunning && (
              <li className="flex items-center gap-3 text-sm text-[var(--ink-soft)]">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-[var(--coral)] border-t-transparent animate-spin" />
                <span>Working&hellip;</span>
              </li>
            )}
          </ol>
        </div>
      )}

      {/* Final analysis */}
      {finalText && (
        <div className="card overflow-hidden">
          <div className="border-b border-[var(--line)] px-6 py-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Analysis
            </p>
          </div>
          <div className="prose prose-sm max-w-none px-6 py-5 text-[var(--ink)]">
            {finalText.split("\n").map((line, i) =>
              line.startsWith("# ") ? (
                <h2 key={i} className="display-title mt-0 text-xl font-semibold">
                  {line.slice(2)}
                </h2>
              ) : line.startsWith("## ") ? (
                <h3 key={i} className="mt-4 text-base font-semibold">
                  {line.slice(3)}
                </h3>
              ) : line.trim() === "" ? (
                <br key={i} />
              ) : (
                <p key={i} className="my-1">
                  {line}
                </p>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
