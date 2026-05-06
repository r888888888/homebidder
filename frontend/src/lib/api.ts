import { authHeaders } from "./auth";

export const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── Shared response types ─────────────────────────────────────────────────────

export interface AnalysisSummary {
  id: number;
  address: string;
  created_at: string;
  offer_recommended: number | null;
  risk_level: string | null;
  investment_rating: string | null;
  is_favorite: boolean;
}

export interface AnalysisListResponse {
  items: AnalysisSummary[];
  total: number;
}

export interface Plan {
  id: number;
  buy_by_date: string;
  viewings_per_week: number;
  total_n: number;
  explore_threshold: number;
  created_at: string;
  is_paused: boolean;
}

export interface PlanStatus {
  phase: "explore" | "commit";
  seen_count: number;
  explore_max_score: number | null;
  explore_threshold: number;
  properties_past_threshold: number;
  bid_premium_pct: number;
}

export interface SeenProperty {
  id: number;
  analysis_id: number | null;
  address_snapshot: string;
  quality: string;
  location: string;
  composite_score: number;
  seen_at: string;
  notes: string | null;
}

export interface PlanResponse {
  plan: Plan;
  status: PlanStatus;
  seen_properties: SeenProperty[];
}

export interface RateLimitStatus {
  used: number;
  limit: number;
  remaining: number;
  tier: string;
  window: string;
  is_grandfathered: boolean;
}

export interface SeenEntry {
  id: number;
  analysis_id: number | null;
  quality: string;
  location: string;
  composite_score: number;
  seen_at: string;
  notes: string | null;
}

export interface SeenListResponse {
  seen_properties: SeenEntry[];
}

export interface FavoriteResponse {
  is_favorite: boolean;
}

export interface BillingPortalResponse {
  url: string;
}

export interface CheckoutSessionResponse {
  url: string;
}

// ── API client ────────────────────────────────────────────────────────────────

/**
 * Typed wrappers around every backend endpoint.
 *
 * All methods:
 * - Attach auth headers automatically.
 * - Throw an Error on non-ok responses (message = statusText, or a
 *   domain-specific code like "ALREADY_SEEN" for known 409s).
 * - Return null (not throw) for expected empty states (e.g. no buying plan).
 *
 * Use with useFetch for reads and useMutation for writes.
 */
export const apiClient = {
  // ── Analyses ───────────────────────────────────────────────────────────────

  getAnalysis: async (
    id: string | number
  ): Promise<{ data: Record<string, unknown> } | { notFound: true }> => {
    const r = await fetch(`${apiBase}/api/analyses/${id}`, {
      headers: authHeaders(),
    });
    if (r.status === 404) return { notFound: true };
    if (!r.ok) throw new Error(r.statusText);
    return { data: (await r.json()) as Record<string, unknown> };
  },

  getAnalysesList: async (
    page: number,
    search: string,
    pageSize = 20
  ): Promise<AnalysisListResponse> => {
    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String((page - 1) * pageSize),
    });
    if (search.trim()) params.set("q", search.trim());
    const r = await fetch(`${apiBase}/api/analyses?${params}`, {
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<AnalysisListResponse>;
  },

  deleteAnalysis: async (id: number): Promise<void> => {
    const r = await fetch(`${apiBase}/api/analyses/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error(r.statusText);
  },

  toggleFavorite: async (id: number): Promise<FavoriteResponse> => {
    const r = await fetch(`${apiBase}/api/analyses/${id}/favorite`, {
      method: "PATCH",
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<FavoriteResponse>;
  },

  // ── Buying plan ────────────────────────────────────────────────────────────

  getBuyingPlan: async (): Promise<PlanResponse | null> => {
    const r = await fetch(`${apiBase}/api/buying-plan`, {
      headers: authHeaders(),
    });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<PlanResponse>;
  },

  createBuyingPlan: async (
    buyByDate: string,
    viewingsPerWeek: number
  ): Promise<PlanResponse> => {
    const r = await fetch(`${apiBase}/api/buying-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        buy_by_date: buyByDate,
        viewings_per_week: viewingsPerWeek,
      }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({})) as { detail?: string };
      throw new Error(err.detail ?? "Failed to create plan");
    }
    return r.json() as Promise<PlanResponse>;
  },

  patchBuyingPlan: async (isPaused: boolean): Promise<PlanResponse> => {
    const r = await fetch(`${apiBase}/api/buying-plan`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ is_paused: isPaused }),
    });
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<PlanResponse>;
  },

  deleteBuyingPlan: async (): Promise<void> => {
    const r = await fetch(`${apiBase}/api/buying-plan`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error(r.statusText);
  },

  // ── Seen properties ────────────────────────────────────────────────────────

  getSeenProperties: async (analysisId: number): Promise<SeenListResponse> => {
    const r = await fetch(
      `${apiBase}/api/seen-properties?analysis_id=${analysisId}`,
      { headers: authHeaders() }
    );
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<SeenListResponse>;
  },

  markSeen: async (
    analysisId: number,
    quality: string,
    location: string,
    notes: string | null
  ): Promise<SeenEntry> => {
    const r = await fetch(`${apiBase}/api/seen-properties`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ analysis_id: analysisId, quality, location, notes }),
    });
    if (r.status === 409) throw new Error("ALREADY_SEEN");
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<SeenEntry>;
  },

  unmarkSeen: async (seenId: number): Promise<void> => {
    const r = await fetch(`${apiBase}/api/seen-properties/${seenId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error(r.statusText);
  },

  // ── Rate limiting ──────────────────────────────────────────────────────────

  getRateLimitStatus: async (): Promise<RateLimitStatus> => {
    const r = await fetch(`${apiBase}/api/rate-limit/status`, {
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error(r.statusText);
    return r.json() as Promise<RateLimitStatus>;
  },

  // ── User account ───────────────────────────────────────────────────────────

  changePassword: async (newPassword: string): Promise<void> => {
    const r = await fetch(`${apiBase}/api/users/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ password: newPassword }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({})) as { detail?: string };
      throw new Error(err.detail ?? "Failed to update password");
    }
  },

  deleteAccount: async (): Promise<void> => {
    const r = await fetch(`${apiBase}/api/users/me`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error("Failed to delete account");
  },

  // ── Payments ───────────────────────────────────────────────────────────────

  getCustomerPortalUrl: async (): Promise<BillingPortalResponse> => {
    const r = await fetch(`${apiBase}/api/payments/customer-portal`, {
      headers: authHeaders(),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({})) as { detail?: string };
      throw new Error(err.detail ?? "Failed to open billing portal");
    }
    return r.json() as Promise<BillingPortalResponse>;
  },

  createCheckoutSession: async (
    priceId: string
  ): Promise<CheckoutSessionResponse> => {
    const r = await fetch(`${apiBase}/api/payments/create-checkout-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ price_id: priceId }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({})) as { detail?: string };
      throw new Error(err.detail ?? "Failed to start checkout");
    }
    return r.json() as Promise<CheckoutSessionResponse>;
  },
};
