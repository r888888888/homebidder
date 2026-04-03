import type { AnalysisEvent } from "../routes/index";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PropertySummaryCard, type PropertyData } from "./PropertySummaryCard";
import { NeighborhoodCard, type NeighborhoodData } from "./NeighborhoodCard";
import { CompsCard, type CompData } from "./CompsCard";
import { OfferRecommendationCard, type OfferData } from "./OfferRecommendationCard";
import { RiskAnalysisCard, type RiskData } from "./RiskAnalysisCard";
import { InvestmentCard, type InvestmentData } from "./InvestmentCard";

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
  assess_risk: "Assessing risk factors",
  fetch_mortgage_rates: "Fetching mortgage rates",
  fetch_rental_estimate: "Fetching rental estimate",
  fetch_ba_value_drivers: "Computing Bay Area value drivers",
  compute_investment_metrics: "Computing investment metrics",
};

export function AnalysisStream({ events, isRunning }: Props) {
  const textBlocks = events.filter((e) => e.type === "text");
  const toolCalls = events.filter((e) => e.type === "tool_call");
  const finalText = textBlocks.map((e) => e.text ?? "").join("");

  const propertyEvent = [...events].reverse().find(
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

  const offerEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "recommend_offer"
  );
  const offerData = offerEvent?.result as OfferData | undefined;

  const riskEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "assess_risk"
  );
  const riskData = riskEvent?.result as RiskData | undefined;

  const investmentEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "compute_investment_metrics"
  );
  const investmentData = investmentEvent?.result as InvestmentData | undefined;

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

      {/* Offer recommendation */}
      {offerData && <OfferRecommendationCard offer={offerData} />}

      {/* Risk assessment */}
      {riskData && <RiskAnalysisCard risk={riskData} />}

      {/* Investment analysis */}
      {investmentData && <InvestmentCard investment={investmentData} />}

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
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ node: _node, ...props }) => (
                  <h1 className="display-title mt-0 text-xl font-semibold" {...props} />
                ),
                h2: ({ node: _node, ...props }) => (
                  <h2 className="mt-4 text-base font-semibold" {...props} />
                ),
                h3: ({ node: _node, ...props }) => (
                  <h3 className="mt-4 text-sm font-semibold" {...props} />
                ),
                p: ({ node: _node, ...props }) => <p className="my-1" {...props} />,
                ul: ({ node: _node, ...props }) => (
                  <ul className="my-2 list-disc pl-5" {...props} />
                ),
                ol: ({ node: _node, ...props }) => (
                  <ol className="my-2 list-decimal pl-5" {...props} />
                ),
              }}
            >
              {finalText}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
