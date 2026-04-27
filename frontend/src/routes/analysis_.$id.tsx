import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PropertySummaryCard, type PropertyData } from "../components/PropertySummaryCard";
import { NeighborhoodCard, type NeighborhoodData } from "../components/NeighborhoodCard";
import { OfferRecommendationCard, type OfferData } from "../components/OfferRecommendationCard";
import { RiskAnalysisCard, type RiskData } from "../components/RiskAnalysisCard";
import { InvestmentCard, type InvestmentData } from "../components/InvestmentCard";
import { InvestmentTeaserCard } from "../components/InvestmentTeaserCard";
import { useAuth } from "../lib/AuthContext";
import { FixerAnalysisCard, type FixerAnalysisData } from "../components/FixerAnalysisCard";
import { CompsCard, type CompData } from "../components/CompsCard";
import { CompsTeaserCard } from "../components/CompsTeaserCard";
import { PermitsCard, type PermitsData } from "../components/PermitsCard";
import { CrimeCard, type CrimeData } from "../components/CrimeCard";
import { PdfExportButton } from "../components/PdfExportButton";
import { useToast } from "../components/Toast";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";

export const Route = createFileRoute("/analysis_/$id")({
  component: PermalinkPage,
});

export interface AnalysisDetail {
  id: number;
  address: string;
  created_at: string;
  offer_low: number | null;
  offer_recommended: number | null;
  offer_high: number | null;
  risk_level: string | null;
  investment_rating: string | null;
  rationale: string | null;
  property_data: PropertyData | null;
  neighborhood_data: NeighborhoodData | null;
  offer_data: OfferData | null;
  risk_data: RiskData | null;
  investment_data: InvestmentData | null;
  renovation_data: (FixerAnalysisData & { disabled_indices?: number[] }) | null;
  permits_data: PermitsData | null;
  crime_data: CrimeData | null;
  comps: CompData[];
  is_favorite: boolean;
}

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
              "relative flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
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

export function PermalinkPage() {
  const { id } = useParams({ from: "/analysis_/$id" });
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("decision");
  const toast = useToast();
  const { user } = useAuth();
  const isInvestorPlus =
    user?.is_superuser ||
    user?.subscription_tier === "investor" ||
    user?.subscription_tier === "agent";

  useEffect(() => {
    fetch(`${apiBase}/api/analyses/${id}`, { headers: authHeaders() })
      .then(async (resp) => {
        if (resp.status === 404) {
          setNotFound(true);
          return;
        }
        if (!resp.ok) throw new Error(resp.statusText);
        const data = await resp.json();
        setAnalysis(data);
        setIsFavorite(data.is_favorite ?? false);
      })
      .catch(() => toast.error("Failed to load analysis."))
      .finally(() => setLoading(false));
  }, [id, toast]);

  async function handleToggleFavorite() {
    try {
      const resp = await fetch(`${apiBase}/api/analyses/${id}/favorite`, {
        method: "PATCH",
        headers: authHeaders(),
      });
      if (!resp.ok) throw new Error(resp.statusText);
      const data = await resp.json();
      setIsFavorite(data.is_favorite);
    } catch {
      toast.error("Failed to update favorite.");
    }
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) {
    return (
      <main className="page-wrap py-10">
        <p className="text-[var(--ink-soft)]">Loading…</p>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="page-wrap py-10">
        <p className="text-[var(--ink-soft)]">Analysis not found.</p>
        <Link to="/" className="mt-4 inline-block text-sm underline text-[var(--navy)]">
          Go home
        </Link>
      </main>
    );
  }

  if (!analysis) return null;

  const tabHasContent: Record<TabId, boolean> = {
    decision: analysis.offer_data != null || analysis.renovation_data != null,
    property: analysis.property_data != null || analysis.neighborhood_data != null,
    market: analysis.comps.length > 0 || analysis.investment_data != null,
    risk: analysis.risk_data != null || analysis.permits_data != null || analysis.crime_data != null,
    analysis: analysis.rationale != null,
  };

  return (
    <main className="page-wrap py-10">
      <div className="mb-8">
        <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Saved Analysis
        </p>
        <h1 className="display-title text-2xl font-bold text-[var(--ink)] sm:text-3xl">
          {analysis.address}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
          <p className="text-xs text-[var(--ink-muted)]">
            {new Date(analysis.created_at).toLocaleDateString(undefined, {
              dateStyle: "long",
            })}
          </p>
          <span className="text-[var(--line)] select-none" aria-hidden="true">·</span>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              aria-label={isFavorite ? "Unfavorite" : "Favorite"}
              onClick={handleToggleFavorite}
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold shadow-sm hover:bg-[var(--bg)] transition-colors${isFavorite ? " text-rose-500" : " text-[var(--ink-muted)]"}`}
            >
              <Heart size={12} fill={isFavorite ? "currentColor" : "none"} />
              {isFavorite ? "Favorited" : "Favorite"}
            </button>
            <PdfExportButton
              analysis={analysis}
              isAgent={user?.is_superuser || user?.subscription_tier === "agent"}
            />
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink)] shadow-sm hover:bg-[var(--bg)]"
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
            <button
              type="button"
              onClick={() =>
                navigate({ to: "/analysis", search: { address: analysis.address, buyerContext: "", forceRefresh: "1" } })
              }
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink)] shadow-sm hover:bg-[var(--bg)]"
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
                <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                <path d="M21 3v5h-5" />
                <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                <path d="M8 16H3v5" />
              </svg>
              Refresh analysis
            </button>
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink)] shadow-sm no-underline hover:bg-[var(--bg)]"
            >
              New analysis
            </Link>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <TabBar active={activeTab} hasContent={tabHasContent} onSelect={setActiveTab} />

        {/* Decision tab */}
        <div
          id="tabpanel-decision"
          role="tabpanel"
          aria-labelledby="tab-decision"
          hidden={activeTab !== "decision"}
        >
          {activeTab === "decision" && (
            <div className="tab-enter space-y-4">
              {analysis.offer_data && (
                <OfferRecommendationCard offer={analysis.offer_data} />
              )}
              {analysis.renovation_data && (
                <FixerAnalysisCard
                  data={analysis.renovation_data}
                  analysisId={analysis.id}
                  initialDisabledIndices={analysis.renovation_data.disabled_indices ?? []}
                />
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
            <div className="tab-enter space-y-4">
              {analysis.property_data && (
                <PropertySummaryCard property={analysis.property_data} />
              )}
              {analysis.neighborhood_data && (
                <NeighborhoodCard
                  neighborhood={analysis.neighborhood_data}
                  neighborhoodName={(analysis.property_data?.neighborhoods as string | null) ?? null}
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
            <div className="tab-enter space-y-4">
              {analysis.comps.length > 0 && (
                isInvestorPlus
                  ? <CompsCard comps={analysis.comps} />
                  : <CompsTeaserCard comps={analysis.comps} />
              )}
              {analysis.investment_data && (
                isInvestorPlus
                  ? <InvestmentCard investment={analysis.investment_data} />
                  : <InvestmentTeaserCard investment={analysis.investment_data} />
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
            <div className="tab-enter space-y-4">
              {analysis.risk_data && (
                <RiskAnalysisCard risk={analysis.risk_data} />
              )}
              {analysis.permits_data && (
                <PermitsCard permits={analysis.permits_data} />
              )}
              {analysis.crime_data && (
                <CrimeCard crime={analysis.crime_data} />
              )}
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
          {activeTab === "analysis" && analysis.rationale && (
            <div className="tab-enter card overflow-hidden">
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
                  {analysis.rationale}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
