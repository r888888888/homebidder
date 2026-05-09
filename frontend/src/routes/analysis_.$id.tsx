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
import { AffordabilityCalculatorCard } from "../components/AffordabilityCalculatorCard";
import { AffordabilityCalculatorTeaserCard } from "../components/AffordabilityCalculatorTeaserCard";
import { useAuth } from "../lib/AuthContext";
import { FixerAnalysisCard, type FixerAnalysisData } from "../components/FixerAnalysisCard";
import { CompsCard, type CompData } from "../components/CompsCard";
import { CompsTeaserCard } from "../components/CompsTeaserCard";
import { PermitsCard, type PermitsData } from "../components/PermitsCard";
import { CrimeCard, type CrimeData } from "../components/CrimeCard";
import { InspectionReportCard, type InspectionFindings } from "../components/InspectionReportCard";
import { PostAnalysisInspectionUpload } from "../components/PostAnalysisInspectionUpload";
import { PdfExportButton } from "../components/PdfExportButton";
import { MarkSeenButton } from "../components/MarkSeenButton";
import { BuyingPlanBadge } from "../components/BuyingPlanBadge";
import { ValidationBanner, type ValidationResult } from "../components/ValidationBanner";
import { useToast } from "../components/Toast";
import { apiBase, apiClient, type PlanResponse } from "../lib/api";
import { useFetch } from "../hooks/useFetch";

export const Route = createFileRoute("/analysis_/$id")({
  // Prefetch the analysis when the user hovers over a link (intent preload).
  // The component reads this via Route.useLoaderData({ strict: false }) and
  // skips the redundant manual fetch, giving an instant render on click.
  loader: ({ params }) => apiClient.getAnalysis(params.id),
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
  inspection_data: InspectionFindings | null;
  validation_data: ValidationResult | null;
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

  // Loader data is present when TanStack Router prefetched the route (intent
  // preload on hover).  In tests, Route.useLoaderData is a vi.fn() returning
  // undefined, so the manual-fetch fallback below runs instead.
  const loaderData = Route.useLoaderData({ strict: false });
  const seedAnalysis =
    loaderData && "data" in loaderData
      ? (loaderData.data as AnalysisDetail)
      : null;

  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(seedAnalysis);
  const [notFound, setNotFound] = useState(
    loaderData !== undefined && "notFound" in loaderData
  );
  const [loading, setLoading] = useState(loaderData === undefined);
  const [copied, setCopied] = useState(false);
  const [isFavorite, setIsFavorite] = useState(seedAnalysis?.is_favorite ?? false);
  const [inspectionData, setInspectionData] = useState<InspectionFindings | null>(
    seedAnalysis?.inspection_data ?? null
  );
  const [renovationData, setRenovationData] = useState<AnalysisDetail["renovation_data"]>(
    seedAnalysis?.renovation_data ?? null
  );
  const [activeTab, setActiveTab] = useState<TabId>("decision");
  const [seenBiddingIntent, setSeenBiddingIntent] = useState<"yes" | "no" | null>(null);
  const [planRefreshKey, setPlanRefreshKey] = useState(0);
  const toast = useToast();
  const { user } = useAuth();
  const isInvestorPlus =
    user?.is_superuser ||
    user?.subscription_tier === "investor" ||
    user?.subscription_tier === "agent";

  useEffect(() => {
    // Skip manual fetch when the loader has already provided data.
    if (loaderData !== undefined) {
      setLoading(false);
      return;
    }
    apiClient.getAnalysis(id)
      .then((result) => {
        if ("notFound" in result) {
          setNotFound(true);
          return;
        }
        const data = result.data as AnalysisDetail;
        setAnalysis(data);
        setIsFavorite(data.is_favorite ?? false);
        setInspectionData(data.inspection_data ?? null);
        setRenovationData(data.renovation_data ?? null);
      })
      .catch(() => toast.error("Failed to load analysis."))
      .finally(() => setLoading(false));
  }, [id, toast, loaderData]);

  useEffect(() => {
    const flag = sessionStorage.getItem("analysis_just_refreshed");
    if (flag) {
      sessionStorage.removeItem("analysis_just_refreshed");
      toast.success("Analysis refreshed successfully.");
    }
  }, [toast]);

  const { data: planData, refetch: refetchPlan } = useFetch<PlanResponse>(
    isInvestorPlus ? `${apiBase}/api/buying-plan` : null
  );

  const planCommitData =
    !planData?.plan?.is_paused &&
    planData?.status?.phase === "commit" &&
    (planData.status.bid_premium_pct ?? 0) > 0
      ? {
          explore_max_score: planData.status.explore_max_score,
          bid_premium_pct: planData.status.bid_premium_pct,
        }
      : null;

  const bidPremiumPct =
    planCommitData !== null && seenBiddingIntent === "yes"
      ? planCommitData.bid_premium_pct
      : null;

  async function handleToggleFavorite() {
    try {
      const data = await apiClient.toggleFavorite(Number(id));
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
    decision: analysis.offer_data != null || renovationData != null,
    property: analysis.property_data != null || analysis.neighborhood_data != null || inspectionData != null,
    market: analysis.comps.length > 0 || analysis.investment_data != null,
    risk: analysis.risk_data != null || analysis.permits_data != null || analysis.crime_data != null,
    analysis: analysis.rationale != null,
  };

  return (
    <main className="page-wrap py-10">
      <div className="mb-8">
        <div className="mb-2 flex items-center gap-1.5">
          <Link
            to="/"
            className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--ink-muted)] no-underline hover:text-[var(--ink)] transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
            New analysis
          </Link>
          <span className="text-[var(--line)] select-none" aria-hidden="true">/</span>
          <span className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">Saved Analysis</span>
        </div>
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
              title={isFavorite ? "Unfavorite" : "Favorite"}
              onClick={handleToggleFavorite}
              className={`inline-flex cursor-pointer items-center justify-center rounded-lg border border-[var(--card-border)] bg-white p-2 shadow-sm hover:bg-[var(--bg)] transition-colors${isFavorite ? " text-rose-500" : " text-[var(--ink-muted)]"}`}
            >
              <Heart size={14} fill={isFavorite ? "currentColor" : "none"} />
            </button>
            <PdfExportButton
              analysis={analysis}
              isAgent={user?.is_superuser || user?.subscription_tier === "agent"}
            />
            <button
              type="button"
              aria-label={copied ? "Copied!" : "Copy permalink"}
              title={copied ? "Copied!" : "Copy permalink"}
              onClick={handleCopy}
              className={`inline-flex cursor-pointer items-center justify-center rounded-lg border border-[var(--card-border)] bg-white p-2 shadow-sm hover:bg-[var(--bg)] transition-colors${copied ? " text-emerald-600" : " text-[var(--ink-muted)]"}`}
            >
              <svg
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
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </button>
            {user && (
              <MarkSeenButton
                analysisId={analysis.id}
                address={analysis.address}
                onSeenEntry={setSeenBiddingIntent}
                onChanged={() => { refetchPlan(); setPlanRefreshKey((k) => k + 1); }}
              />
            )}
            {isInvestorPlus && (
              <BuyingPlanBadge refreshTrigger={planRefreshKey} />
            )}
            <button
              type="button"
              onClick={() =>
                navigate({ to: "/analysis", search: { address: analysis.address, buyerContext: "", forceRefresh: true } })
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
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {analysis.validation_data && (
          <ValidationBanner result={analysis.validation_data} />
        )}
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
                <OfferRecommendationCard offer={analysis.offer_data} bidPremiumPct={bidPremiumPct} />
              )}
              {renovationData && (
                <FixerAnalysisCard
                  data={renovationData}
                  analysisId={analysis.id}
                  initialDisabledIndices={renovationData.disabled_indices ?? []}
                />
              )}
              {analysis.investment_data && (
                isInvestorPlus
                  ? <AffordabilityCalculatorCard investment={analysis.investment_data} offer={analysis.offer_data} />
                  : <AffordabilityCalculatorTeaserCard />
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
              {inspectionData ? (
                <InspectionReportCard data={inspectionData} />
              ) : (
                <div className="card px-6 py-5 space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-[var(--ink)]">Inspection Report</p>
                    <p className="mt-1 text-xs text-[var(--ink-muted)]">
                      Upload a PDF inspection report and HomeBidder will parse the findings to flag systems that need attention. The results appear here and inform the renovation estimate on re-run.
                    </p>
                  </div>
                  <PostAnalysisInspectionUpload
                    analysisId={analysis.id}
                    onSuccess={(findings) => setInspectionData(findings)}
                    onRenovationUpdate={(data) => setRenovationData(data)}
                  />
                </div>
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
