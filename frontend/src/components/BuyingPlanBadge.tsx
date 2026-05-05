import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../lib/AuthContext";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";

interface PlanStatus {
  phase: "explore" | "commit";
  seen_count: number;
  explore_max_score: number | null;
  explore_threshold: number;
  properties_past_threshold: number;
  bid_premium_pct: number;
}

interface PlanResponse {
  plan: {
    id: number;
    buy_by_date: string;
    total_n: number;
    explore_threshold: number;
  };
  status: PlanStatus;
}

export function BuyingPlanBadge() {
  const { user } = useAuth();
  const [planData, setPlanData] = useState<PlanResponse | null>(null);

  useEffect(() => {
    if (!user) return;
    fetch(`${apiBase}/api/buying-plan`, { headers: authHeaders() })
      .then((r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(r.statusText);
        return r.json() as Promise<PlanResponse>;
      })
      .then((data) => {
        // Validate expected shape before setting state.
        if (data?.status?.phase) setPlanData(data);
      })
      .catch(() => {});
  }, [user]);

  if (!user || !planData) return null;

  const { status } = planData;

  if (status.phase === "explore") {
    return (
      <Link
        to="/buying-plan"
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink-muted)] shadow-sm no-underline hover:bg-[var(--bg)] transition-colors"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden="true" />
        Explore phase — {status.seen_count}&nbsp;/&nbsp;{status.explore_threshold}
      </Link>
    );
  }

  const premiumPct = Math.round(status.bid_premium_pct * 100);
  return (
    <Link
      to="/buying-plan"
      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-emerald-600 shadow-sm no-underline hover:bg-[var(--bg)] transition-colors"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
      Commit phase
      {premiumPct > 0 && (
        <span className="ml-0.5 text-[var(--coral)]">+{premiumPct}%</span>
      )}
    </Link>
  );
}
