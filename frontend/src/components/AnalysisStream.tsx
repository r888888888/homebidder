import { useState } from "react";
import type { AnalysisEvent } from "../routes/index";
import { Link } from "@tanstack/react-router";
import { Heart } from "lucide-react";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PropertySummaryCard, type PropertyData } from "./PropertySummaryCard";
import { NeighborhoodCard, type NeighborhoodData } from "./NeighborhoodCard";
import { CompsCard, type CompData } from "./CompsCard";
import { CompsTeaserCard } from "./CompsTeaserCard";
import { OfferRecommendationCard, type OfferData } from "./OfferRecommendationCard";
import { RiskAnalysisCard, type RiskData } from "./RiskAnalysisCard";
import { InvestmentCard, type InvestmentData } from "./InvestmentCard";
import { InvestmentTeaserCard } from "./InvestmentTeaserCard";
import { useAuth } from "../lib/AuthContext";
import { PermitsCard, type PermitsData } from "./PermitsCard";
import { FixerAnalysisCard, type FixerAnalysisData } from "./FixerAnalysisCard";
import { ValidationBanner, type ValidationResult } from "./ValidationBanner";
import { CrimeCard, type CrimeData } from "./CrimeCard";

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
  fetch_ba_value_drivers: "Computing Bay Area value drivers",
  compute_investment_metrics: "Computing investment metrics",
  fetch_sf_permits: "Fetching SF permit history",
  estimate_renovation_cost: "Estimating renovation costs",
  fetch_crime_data: "Fetching crime statistics",
};

type TabId = "decision" | "property" | "market" | "risk" | "analysis";

const TABS: { id: TabId; label: string }[] = [
  { id: "property", label: "Property" },
  { id: "decision", label: "Decision" },
  { id: "market", label: "Market" },
  { id: "risk", label: "Risk" },
  { id: "analysis", label: "Analysis" },
];

function TabBar({
  active,
  hasContent,
  onSelect,
}: {
  active: TabId;
  hasContent: Record<TabId, boolean>;
  onSelect: (id: TabId) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Analysis sections"
      className="flex gap-1 overflow-x-auto rounded-xl border border-[var(--line)] bg-[var(--card)] p-1"
    >
      {TABS.map(({ id, label }) => {
        const isActive = id === active;
        return (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={isActive}
            aria-controls={`tabpanel-${id}`}
            id={`tab-${id}`}
            onClick={() => onSelect(id)}
            className={[
              "relative flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              isActive
                ? "bg-[var(--navy)] text-white"
                : "text-[var(--ink-soft)] hover:bg-[var(--bg)] hover:text-[var(--ink)]",
            ].join(" ")}
          >
            {label}
            {hasContent[id] && !isActive && (
              <span
                aria-label="has content"
                className="h-1.5 w-1.5 rounded-full bg-[var(--coral)]"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

function PanelSkeleton({ label }: { label: string }) {
  return (
    <div className="card p-5">
      <div className="mb-4 space-y-3">
        <div className="skeleton h-4 w-3/4" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-2/3" />
      </div>
      <p className="text-xs text-[var(--ink-muted)]">{label}</p>
    </div>
  );
}

export function AnalysisStream({ events, isRunning }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("decision");
  const [copied, setCopied] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const { user } = useAuth();
  const isInvestorPlus =
    user?.subscription_tier === "investor" || user?.subscription_tier === "agent";

  async function handleCopyPermalink(id: number) {
    const url = `${window.location.origin}/analysis/${id}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleToggleFavorite(id: number) {
    try {
      const resp = await fetch(`${apiBase}/api/analyses/${id}/favorite`, {
        method: "PATCH",
        headers: authHeaders(),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      setIsFavorite(data.is_favorite);
    } catch {
      // ignore
    }
  }

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

  const permitsEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "fetch_sf_permits"
  );
  const permitsData = permitsEvent?.result as PermitsData | undefined;

  const renovationEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "estimate_renovation_cost"
  );
  const renovationData = renovationEvent?.result as FixerAnalysisData | undefined;

  const crimeEvent = events.find(
    (e) => e.type === "tool_result" && e.tool === "fetch_crime_data"
  );
  const crimeData = crimeEvent?.result as CrimeData | undefined;

  const validationEvent = events.find((e) => e.type === "validation_result");
  const validationData = validationEvent?.result as ValidationResult | undefined;

  const analysisIdEvent = events.find((e) => e.type === "analysis_id");

  const tabHasContent: Record<TabId, boolean> = {
    decision: offerData != null || renovationData != null,
    property: propertyData != null || neighborhoodData != null,
    market: compsData != null || investmentData != null,
    risk: riskData != null || permitsData != null,
    analysis: toolCalls.length > 0 || finalText.length > 0,
  };

  return (
    <div className="space-y-4 fade-up">
      {/* Validation banner — shown when the searched property has already sold */}
      {validationData && <ValidationBanner result={validationData} />}

      <TabBar active={activeTab} hasContent={tabHasContent} onSelect={setActiveTab} />

      {/* Decision tab */}
      <div
        id="tabpanel-decision"
        role="tabpanel"
        aria-labelledby="tab-decision"
        hidden={activeTab !== "decision"}
      >
        {activeTab === "decision" && (
          <div key="decision" className="tab-enter space-y-4">
            {offerData ? (
              <OfferRecommendationCard offer={offerData} />
            ) : (
              isRunning && <PanelSkeleton label="Computing offer range…" />
            )}
            {renovationData ? (
              <FixerAnalysisCard
                data={renovationData}
                analysisId={analysisIdEvent?.id as number | undefined}
              />
            ) : (
              isRunning && <PanelSkeleton label="Analyzing renovation potential…" />
            )}
          </div>
        )}
      </div>

      {/* Property tab */}
      <div
        id="tabpanel-property"
        role="tabpanel"
        aria-labelledby="tab-property"
        hidden={activeTab !== "property"}
      >
        {activeTab === "property" && (
          <div key="property" className="tab-enter space-y-4">
            {propertyData ? (
              <PropertySummaryCard property={propertyData} />
            ) : (
              isRunning && <PanelSkeleton label="Looking up property…" />
            )}
            {neighborhoodData && (
              <NeighborhoodCard
                neighborhood={neighborhoodData}
                neighborhoodName={(propertyData?.neighborhoods as string | null) ?? null}
              />
            )}
          </div>
        )}
      </div>

      {/* Market tab */}
      <div
        id="tabpanel-market"
        role="tabpanel"
        aria-labelledby="tab-market"
        hidden={activeTab !== "market"}
      >
        {activeTab === "market" && (
          <div key="market" className="tab-enter space-y-4">
            {compsData ? (
              isInvestorPlus
                ? <CompsCard comps={compsData} />
                : <CompsTeaserCard comps={compsData} />
            ) : (
              isRunning && <PanelSkeleton label="Fetching comparable sales…" />
            )}
            {investmentData && (
              isInvestorPlus
                ? <InvestmentCard investment={investmentData} />
                : <InvestmentTeaserCard investment={investmentData} />
            )}
          </div>
        )}
      </div>

      {/* Risk tab */}
      <div
        id="tabpanel-risk"
        role="tabpanel"
        aria-labelledby="tab-risk"
        hidden={activeTab !== "risk"}
      >
        {activeTab === "risk" && (
          <div key="risk" className="tab-enter space-y-4">
            {riskData ? (
              <RiskAnalysisCard risk={riskData} />
            ) : (
              isRunning && <PanelSkeleton label="Assessing risk factors…" />
            )}
            {permitsData && <PermitsCard permits={permitsData} />}
            {crimeData && <CrimeCard crime={crimeData} />}
          </div>
        )}
      </div>

      {/* Analysis tab */}
      <div
        id="tabpanel-analysis"
        role="tabpanel"
        aria-labelledby="tab-analysis"
        hidden={activeTab !== "analysis"}
      >
        {activeTab === "analysis" && (
          <div key="analysis" className="tab-enter space-y-4">
            {/* Agent step progress — hidden once analysis completes */}
            {toolCalls.length > 0 && isRunning && (
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
        )}
      </div>

      {/* Saved link + permalink */}
      {analysisIdEvent?.id && (
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-[var(--ink-soft)]">
          <span>
            Saved &mdash;{" "}
            <Link to="/history" className="underline">
              view history
            </Link>
          </span>
          <button
            type="button"
            aria-label={isFavorite ? "Unfavorite" : "Favorite"}
            onClick={() => handleToggleFavorite(analysisIdEvent.id as number)}
            className={`inline-flex items-center gap-1 rounded-lg border border-[var(--line)] bg-[var(--card)] px-2.5 py-1 text-xs font-medium transition-colors${isFavorite ? " text-rose-500" : " text-[var(--ink-muted)] hover:text-rose-400"}`}
          >
            <Heart size={12} fill={isFavorite ? "currentColor" : "none"} />
          </button>
          <button
            type="button"
            onClick={() => handleCopyPermalink(analysisIdEvent.id as number)}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--line)] bg-[var(--card)] px-2.5 py-1 text-xs font-medium text-[var(--ink-soft)] hover:text-[var(--ink)]"
          >
            <svg
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
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
            {copied ? "Copied!" : "Copy permalink"}
          </button>
        </div>
      )}
    </div>
  );
}
