import { createFileRoute, Link } from "@tanstack/react-router";
import React, { useEffect, useState, useCallback } from "react";
import { Heart } from "lucide-react";
import { useToast } from "../components/Toast";
import { apiBase, apiClient } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import { useFetch } from "../hooks/useFetch";

export const Route = createFileRoute("/history")({ component: HistoryPage });

interface AnalysisSummary {
  id: number;
  address: string;
  created_at: string;
  offer_recommended: number | null;
  risk_level: string | null;
  investment_rating: string | null;
  is_favorite: boolean;
}

const PAGE_SIZE = 20;

function RetentionBanner({ tier }: { tier: string }) {
  if (tier === "buyer") {
    return (
      <p className="text-xs text-[var(--ink-soft)] mb-4">
        Your Buyer plan shows the last 30 days of analyses.{" "}
        <Link to="/pricing" className="underline text-[var(--navy)]">
          Upgrade to Investor
        </Link>{" "}
        for 6 months of history.
      </p>
    );
  }
  if (tier === "investor") {
    return (
      <p className="text-xs text-[var(--ink-soft)] mb-4">
        Your Investor plan shows the last 6 months of analyses.{" "}
        <Link to="/pricing" className="underline text-[var(--navy)]">
          Upgrade to Agent
        </Link>{" "}
        for unlimited history.
      </p>
    );
  }
  return null;
}

export function HistoryPage() {
  const { user } = useAuth();
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const toast = useToast();

  const listParams = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String((page - 1) * PAGE_SIZE),
  });
  if (search.trim()) listParams.set("q", search.trim());
  const listUrl = `${apiBase}/api/analyses?${listParams.toString()}`;

  const { data: listData, error: listError } = useFetch<{ items: AnalysisSummary[]; total: number }>(listUrl);

  useEffect(() => {
    if (listData) {
      setAnalyses(listData.items);
      setTotal(listData.total);
    }
  }, [listData]);

  useEffect(() => {
    if (listError) {
      toast.error("Failed to load analysis history.");
    }
  }, [listError, toast]);

  const handleDelete = useCallback(async (id: number) => {
    try {
      await apiClient.deleteAnalysis(id);
      setAnalyses((prev) => prev.filter((a) => a.id !== id));
    } catch {
      toast.error("Failed to delete analysis.");
    }
  }, [toast]);

  const handleToggleFavorite = useCallback(async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const data = await apiClient.toggleFavorite(id);
      setAnalyses((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_favorite: data.is_favorite } : a))
      );
    } catch {
      toast.error("Failed to update favorite.");
    }
  }, [toast]);

  return (
    <main className="page-wrap py-10">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="display-title text-2xl font-bold text-[var(--ink)]">
          Analysis History
        </h1>
        <Link to="/" className="text-sm underline text-[var(--ink-soft)]">
          New analysis
        </Link>
      </div>
      {user && <RetentionBanner tier={user.subscription_tier} />}

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by address"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full sm:w-80 px-3 py-1.5 text-sm border border-[var(--line)] rounded-lg focus:outline-none focus:ring-1 focus:ring-[var(--navy)]"
        />
      </div>

      {analyses.length === 0 ? (
        <p className="text-[var(--ink-soft)]">{search.trim() ? "No analyses match your search." : "No saved analyses yet."}</p>
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
                  <tr
                    key={a.id}
                    className={`hover:bg-[var(--bg)] border-b border-[var(--line)] transition-colors${a.is_favorite ? " bg-rose-50" : ""}`}
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
                        <button
                          type="button"
                          onClick={(e) => handleToggleFavorite(a.id, e)}
                          aria-label={a.is_favorite ? "Unfavorite" : "Favorite"}
                          className={`flex-shrink-0 transition-colors${a.is_favorite ? " text-rose-500" : " text-[var(--ink-muted)] hover:text-rose-400"}`}
                        >
                          <Heart size={14} fill={a.is_favorite ? "currentColor" : "none"} />
                        </button>
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
              ))}
            </tbody>
          </table>
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-4 text-sm text-[var(--ink-soft)]">
              <div>
                {page > 1 && (
                  <button
                    type="button"
                    onClick={() => setPage((p) => p - 1)}
                    className="px-3 py-1 border border-[var(--line)] rounded hover:bg-[var(--bg)]"
                  >
                    Prev
                  </button>
                )}
              </div>
              <span>Page {page} of {Math.ceil(total / PAGE_SIZE)}</span>
              <div>
                {page < Math.ceil(total / PAGE_SIZE) && (
                  <button
                    type="button"
                    onClick={() => setPage((p) => p + 1)}
                    className="px-3 py-1 border border-[var(--line)] rounded hover:bg-[var(--bg)]"
                  >
                    Next
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
