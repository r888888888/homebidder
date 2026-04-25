import { createFileRoute, Link } from "@tanstack/react-router";
import React, { useEffect, useState, useCallback } from "react";
import { PropertySummaryCard, type PropertyData } from "../components/PropertySummaryCard";
import { OfferRecommendationCard, type OfferData } from "../components/OfferRecommendationCard";
import { RiskAnalysisCard, type RiskData } from "../components/RiskAnalysisCard";
import { InvestmentCard, type InvestmentData } from "../components/InvestmentCard";
import { FixerAnalysisCard, type FixerAnalysisData } from "../components/FixerAnalysisCard";
import { useToast } from "../components/Toast";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";

export const Route = createFileRoute("/history")({ component: HistoryPage });

interface AnalysisSummary {
  id: number;
  address: string;
  created_at: string;
  offer_recommended: number | null;
  risk_level: string | null;
  investment_rating: string | null;
}

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
  neighborhood_data: Record<string, unknown> | null;
  offer_data: OfferData | null;
  risk_data: RiskData | null;
  investment_data: InvestmentData | null;
  renovation_data: FixerAnalysisData | null;
  comps: unknown[];
}

export function HistoryPage() {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const toast = useToast();

  useEffect(() => {
    fetch(`${apiBase}/api/analyses`, { headers: authHeaders() })
      .then((r) => r.json())
      .then(setAnalyses)
      .catch(() => {
        toast.error("Failed to load analysis history.");
      });
  }, [toast]);

  async function handleRowClick(id: number) {
    if (selectedId === id) {
      setSelectedId(null);
      setDetail(null);
      return;
    }
    const resp = await fetch(`${apiBase}/api/analyses/${id}`, { headers: authHeaders() });
    if (!resp.ok) {
      toast.error(`Failed to load analysis: ${resp.statusText}`);
      return;
    }
    const data = await resp.json();
    setSelectedId(id);
    setDetail(data);
  }

  const handleDelete = useCallback(async (id: number) => {
    const resp = await fetch(`${apiBase}/api/analyses/${id}`, { method: "DELETE", headers: authHeaders() });
    if (!resp.ok) {
      toast.error("Failed to delete analysis.");
      return;
    }
    setAnalyses((prev) => prev.filter((a) => a.id !== id));
    setSelectedId(null);
    setDetail(null);
  }, [toast]);

  return (
    <main className="page-wrap py-10">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="display-title text-2xl font-bold text-[var(--ink)]">
          Analysis History
        </h1>
        <Link to="/" className="text-sm underline text-[var(--ink-soft)]">
          New analysis
        </Link>
      </div>

      {analyses.length === 0 ? (
        <p className="text-[var(--ink-soft)]">No saved analyses yet.</p>
      ) : (
        <div className="space-y-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)] border-b border-[var(--line)]">
                <th className="py-2 pr-4">Address</th>
                <th className="py-2 pr-4">Date</th>
                <th className="py-2 pr-4">Offer</th>
                <th className="py-2 pr-4">Risk</th>
                <th className="py-2 pr-4">Rating</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((a) => (
                <React.Fragment key={a.id}>
                  <tr
                    key={a.id}
                    className="cursor-pointer hover:bg-[var(--bg)] border-b border-[var(--line)]"
                    onClick={() => handleRowClick(a.id)}
                  >
                    <td className="py-3 pr-4">{a.address}</td>
                    <td className="py-3 pr-4">
                      {new Date(a.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 pr-4">
                      {a.offer_recommended
                        ? `$${a.offer_recommended.toLocaleString()}`
                        : "—"}
                    </td>
                    <td className="py-3 pr-4">{a.risk_level ?? "—"}</td>
                    <td className="py-3 pr-4">{a.investment_rating ?? "—"}</td>
                    <td className="py-3" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-3">
                        <Link
                          to="/analysis/$id"
                          params={{ id: String(a.id) }}
                          className="text-xs text-[var(--navy)] underline"
                        >
                          View
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleDelete(a.id)}
                          className="text-xs text-red-500 hover:text-red-700 underline"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                  {selectedId === a.id && detail && (
                    <tr key={`detail-${a.id}`}>
                      <td colSpan={6} className="py-4">
                        <div className="space-y-4">
                          {detail.property_data && (
                            <PropertySummaryCard
                              property={detail.property_data}
                            />
                          )}
                          {detail.offer_data && (
                            <OfferRecommendationCard
                              offer={detail.offer_data}
                            />
                          )}
                          {detail.risk_data && (
                            <RiskAnalysisCard risk={detail.risk_data} />
                          )}
                          {detail.investment_data && (
                            <InvestmentCard
                              investment={detail.investment_data}
                            />
                          )}
                          {detail.renovation_data && (
                            <FixerAnalysisCard
                              data={detail.renovation_data}
                              analysisId={detail.id}
                              initialDisabledIndices={detail.renovation_data.disabled_indices ?? []}
                            />
                          )}
                          <div className="flex justify-end pt-2">
                            <button
                              type="button"
                              onClick={() => handleDelete(a.id)}
                              className="text-xs text-red-500 hover:text-red-700 underline"
                            >
                              Delete analysis
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
