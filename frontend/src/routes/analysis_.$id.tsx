import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PropertySummaryCard, type PropertyData } from "../components/PropertySummaryCard";
import { OfferRecommendationCard, type OfferData } from "../components/OfferRecommendationCard";
import { RiskAnalysisCard, type RiskData } from "../components/RiskAnalysisCard";
import { InvestmentCard, type InvestmentData } from "../components/InvestmentCard";
import { FixerAnalysisCard, type FixerAnalysisData } from "../components/FixerAnalysisCard";
import { useToast } from "../components/Toast";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";

export const Route = createFileRoute("/analysis_/$id")({
  component: PermalinkPage,
});

interface AnalysisDetail {
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
  offer_data: OfferData | null;
  risk_data: RiskData | null;
  investment_data: InvestmentData | null;
  renovation_data: (FixerAnalysisData & { disabled_indices?: number[] }) | null;
  comps: unknown[];
}

export function PermalinkPage() {
  const { id } = useParams({ from: "/analysis_/$id" });
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const toast = useToast();

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
      })
      .catch(() => toast.error("Failed to load analysis."))
      .finally(() => setLoading(false));
  }, [id, toast]);

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

  return (
    <main className="page-wrap py-10">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Saved Analysis
          </p>
          <h1 className="display-title text-2xl font-bold text-[var(--ink)] sm:text-3xl">
            {analysis.address}
          </h1>
          <p className="mt-1 text-xs text-[var(--ink-muted)]">
            {new Date(analysis.created_at).toLocaleDateString(undefined, {
              dateStyle: "long",
            })}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--card-border)] bg-white px-4 py-2 text-sm font-semibold text-[var(--ink)] shadow-sm hover:bg-[var(--bg)]"
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
            {copied ? "Copied!" : "Copy permalink"}
          </button>
          <Link
            to="/"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-[var(--card-border)] bg-white px-4 py-2 text-sm font-semibold text-[var(--ink)] shadow-sm no-underline hover:bg-[var(--bg)]"
          >
            New analysis
          </Link>
        </div>
      </div>

      <div className="space-y-4">
        {analysis.property_data && (
          <PropertySummaryCard property={analysis.property_data} />
        )}
        {analysis.offer_data && (
          <OfferRecommendationCard offer={analysis.offer_data} />
        )}
        {analysis.risk_data && (
          <RiskAnalysisCard risk={analysis.risk_data} />
        )}
        {analysis.investment_data && (
          <InvestmentCard investment={analysis.investment_data} />
        )}
        {analysis.renovation_data && (
          <FixerAnalysisCard
            data={analysis.renovation_data}
            analysisId={analysis.id}
            initialDisabledIndices={
              analysis.renovation_data.disabled_indices ?? []
            }
          />
        )}
      </div>
    </main>
  );
}
