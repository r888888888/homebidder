import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PropertySummaryCard } from "../components/PropertySummaryCard";
import { OfferRecommendationCard } from "../components/OfferRecommendationCard";
import { RiskAnalysisCard } from "../components/RiskAnalysisCard";
import { InvestmentCard } from "../components/InvestmentCard";

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
  property_data: Record<string, unknown> | null;
  neighborhood_data: Record<string, unknown> | null;
  offer_data: Record<string, unknown> | null;
  risk_data: Record<string, unknown> | null;
  investment_data: Record<string, unknown> | null;
  comps: unknown[];
}

export function HistoryPage() {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
    fetch(`${apiBase}/api/analyses`)
      .then((r) => r.json())
      .then(setAnalyses)
      .catch(() => {});
  }, []);

  async function handleRowClick(id: number) {
    if (selectedId === id) {
      setSelectedId(null);
      setDetail(null);
      return;
    }
    const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
    const resp = await fetch(`${apiBase}/api/analyses/${id}`);
    const data = await resp.json();
    setSelectedId(id);
    setDetail(data);
  }

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
                <th className="py-2">Rating</th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((a) => (
                <>
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
                    <td className="py-3">{a.investment_rating ?? "—"}</td>
                  </tr>
                  {selectedId === a.id && detail && (
                    <tr key={`detail-${a.id}`}>
                      <td colSpan={5} className="py-4">
                        <div className="space-y-4">
                          {detail.property_data && (
                            <PropertySummaryCard
                              property={detail.property_data as any}
                            />
                          )}
                          {detail.offer_data && (
                            <OfferRecommendationCard
                              offer={detail.offer_data as any}
                            />
                          )}
                          {detail.risk_data && (
                            <RiskAnalysisCard risk={detail.risk_data as any} />
                          )}
                          {detail.investment_data && (
                            <InvestmentCard
                              investment={detail.investment_data as any}
                            />
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
