import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/AuthContext";
import { useToast } from "../components/Toast";
import { apiBase, apiClient } from "../lib/api";
import { authHeaders } from "../lib/auth";
import { useMutation } from "../hooks/useMutation";

export const Route = createFileRoute("/buying-plan")({
  component: BuyingPlanPage,
});

interface Plan {
  id: number;
  buy_by_date: string;
  viewings_per_week: number;
  total_n: number;
  explore_threshold: number;
  created_at: string;
  is_paused: boolean;
}

interface PlanStatus {
  phase: "explore" | "commit";
  seen_count: number;
  explore_max_score: number | null;
  explore_threshold: number;
  properties_past_threshold: number;
  bid_premium_pct: number;
}

interface SeenProperty {
  id: number;
  analysis_id: number | null;
  address_snapshot: string;
  quality: string;
  location: string;
  composite_score: number;
  bidding_intent: "yes" | "no" | null;
  seen_at: string;
  notes: string | null;
}

const LEGACY_INTENT_THRESHOLD = 0.5;

function deriveWouldBid(sp: SeenProperty): boolean {
  if (sp.bidding_intent !== null) return sp.bidding_intent === "yes";
  return sp.composite_score >= LEGACY_INTENT_THRESHOLD;
}

interface PlanResponse {
  plan: Plan;
  status: PlanStatus;
  seen_properties: SeenProperty[];
}

export function BuyingPlanPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [planData, setPlanData] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [buyByDate, setBuyByDate] = useState("");
  const [viewingsPerWeek, setViewingsPerWeek] = useState("3");

  const isInvestorPlus =
    user?.is_superuser ||
    user?.subscription_tier === "investor" ||
    user?.subscription_tier === "agent";

  useEffect(() => {
    if (!user || !isInvestorPlus) {
      setLoading(false);
      return;
    }
    fetch(`${apiBase}/api/buying-plan`, { headers: authHeaders() })
      .then(async (r) => {
        if (r.status === 404) {
          setPlanData(null);
          return;
        }
        if (!r.ok) throw new Error(r.statusText);
        const data = await r.json();
        setPlanData(data);
      })
      .catch(() => toast.error("Failed to load buying plan."))
      .finally(() => setLoading(false));
  }, [user, isInvestorPlus, toast]);

  const { mutate: createPlan, loading: submitting } = useMutation(
    (_: null) => apiClient.createBuyingPlan(buyByDate, parseFloat(viewingsPerWeek)),
    (data) => {
      setPlanData(data);
      toast.success("Buying plan created!");
    }
  );

  const { mutate: deletePlan } = useMutation(
    (_: null) => apiClient.deleteBuyingPlan(),
    () => {
      setPlanData(null);
      setBuyByDate("");
      setViewingsPerWeek("3");
      toast.success("Plan deleted.");
    }
  );

  const { mutate: togglePause } = useMutation(
    (isPaused: boolean) => apiClient.patchBuyingPlan(isPaused),
    (data) => setPlanData(data)
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createPlan(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create plan.");
    }
  }

  async function handleDelete() {
    try {
      await deletePlan(null);
    } catch {
      toast.error("Failed to delete plan.");
    }
  }

  async function handleTogglePause() {
    try {
      await togglePause(!planData!.plan.is_paused);
    } catch {
      toast.error("Failed to update plan.");
    }
  }

  // Not logged in
  if (!user) {
    return (
      <main className="page-wrap py-10">
        <h1 className="display-title mb-4 text-2xl font-bold text-[var(--ink)]">Buying Plan</h1>
        <p className="text-[var(--ink-soft)]">
          Please{" "}
          <Link to="/login" className="underline text-[var(--navy)]">
            log in
          </Link>{" "}
          to use the Buying Plan feature.
        </p>
      </main>
    );
  }

  // Buyer tier — teaser
  if (!isInvestorPlus) {
    return (
      <main className="page-wrap py-10">
        <h1 className="display-title mb-2 text-2xl font-bold text-[var(--ink)]">Buying Plan</h1>
        <p className="mb-6 text-[var(--ink-soft)]">
          Apply optimal stopping theory to your home search. Set a buy-by date and viewing pace —
          HomeBidder tells you exactly when to stop exploring and start committing.
        </p>
        <div className="card p-6 max-w-md">
          <p className="mb-1 text-sm font-semibold text-[var(--ink)]">
            Investor or Agent plan required
          </p>
          <p className="mb-4 text-sm text-[var(--ink-soft)]">
            The Buying Plan uses the secretary-problem algorithm to give you a principled
            decision rule: explore the first floor(N/e) properties, then commit to the next
            one that beats your explore-phase best.
          </p>
          <Link
            to="/pricing"
            className="inline-block rounded-lg bg-[var(--coral)] px-4 py-2 text-sm font-semibold text-white no-underline hover:opacity-90"
          >
            Upgrade to Investor
          </Link>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="page-wrap py-10">
        <p className="text-[var(--ink-soft)]">Loading…</p>
      </main>
    );
  }

  // No plan yet — setup form
  if (!planData) {
    return (
      <main className="page-wrap py-10 max-w-lg">
        <h1 className="display-title mb-2 text-2xl font-bold text-[var(--ink)]">
          Set Up Your Buying Plan
        </h1>
        <p className="mb-6 text-sm text-[var(--ink-soft)]">
          Tell us your timeline and viewing pace. HomeBidder will compute your explore
          threshold using the optimal stopping rule: review the first floor(N/e) properties,
          then commit to the next one that beats your explore-phase best.
        </p>
        <form onSubmit={handleCreate} className="card space-y-5 p-6">
          <div>
            <label
              htmlFor="buy-by-date"
              className="mb-1 block text-xs font-semibold text-[var(--ink)]"
            >
              Buy-by date
            </label>
            <input
              id="buy-by-date"
              type="date"
              required
              value={buyByDate}
              onChange={(e) => setBuyByDate(e.target.value)}
              className="w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--navy)]"
            />
          </div>
          <div>
            <label
              htmlFor="viewings-per-week"
              className="mb-1 block text-xs font-semibold text-[var(--ink)]"
            >
              Viewings per week
            </label>
            <input
              id="viewings-per-week"
              type="number"
              required
              min="0.5"
              max="20"
              step="0.5"
              value={viewingsPerWeek}
              onChange={(e) => setViewingsPerWeek(e.target.value)}
              className="w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--navy)]"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full cursor-pointer rounded-lg bg-[var(--navy)] py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create plan"}
          </button>
        </form>
      </main>
    );
  }

  // Dashboard — plan exists
  const { plan, status, seen_properties } = planData;
  const premiumPct = Math.round(status.bid_premium_pct * 100);

  return (
    <main className="page-wrap py-10">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Buying Plan
          </p>
          <h1 className="display-title text-2xl font-bold text-[var(--ink)]">
            Buy by {plan.buy_by_date}
          </h1>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            {plan.viewings_per_week} viewings/week · N&nbsp;=&nbsp;{plan.total_n} expected
          </p>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <button
            type="button"
            onClick={handleTogglePause}
            className="cursor-pointer rounded-lg border border-[var(--line)] px-3 py-1.5 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--bg)]"
          >
            {plan.is_paused ? "Resume plan" : "Pause plan"}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            aria-label="Delete plan"
            className="cursor-pointer rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-500 hover:bg-red-50"
          >
            Delete plan
          </button>
        </div>
      </div>

      {/* Phase card */}
      <div className="card mb-4 p-5">
        {plan.is_paused ? (
          <>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
              Algorithm paused
            </p>
            <p className="text-sm text-[var(--ink-soft)]">
              The buying plan algorithm is paused. Your progress and seen properties are preserved.
              Click <span className="font-semibold text-[var(--ink)]">Resume plan</span> to re-enable
              the explore/commit decision rule and bid premium.
            </p>
          </>
        ) : status.phase === "explore" ? (
          <>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-amber-600">
              Explore phase
            </p>
            <p className="text-2xl font-bold text-[var(--ink)]">
              {status.seen_count}&nbsp;/&nbsp;{status.explore_threshold} properties explored
            </p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              Mark{" "}
              <span className="font-semibold">
                {status.explore_threshold - status.seen_count}
              </span>{" "}
              more properties as seen to complete the explore phase.
            </p>
          </>
        ) : (
          <>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-emerald-600">
              Commit phase
            </p>
            <p className="text-2xl font-bold text-[var(--ink)]">
              {status.seen_count} properties reviewed
            </p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              Commit to the next property you mark as{" "}
              <span className="font-semibold">"Would bid"</span>.
            </p>
            {premiumPct > 0 && (
              <p className="mt-2 text-sm">
                <span className="font-semibold text-[var(--coral)]">
                  Bid premium: +{premiumPct}%
                </span>{" "}
                <span className="text-[var(--ink-muted)]">
                  ({status.properties_past_threshold} 'Would bid'{" "}
                  {status.properties_past_threshold === 1 ? "property" : "properties"} past threshold × 1%)
                </span>
              </p>
            )}
            <p className="mt-3 text-sm text-[var(--ink-soft)]">
              After visiting a property, open its analysis and click{" "}
              <span className="font-semibold text-[var(--ink)]">"Mark Seen"</span>{" "}
              to record your decision.{" "}
              <Link to="/history" className="underline text-[var(--navy)]">
                Open analysis
              </Link>
            </p>
          </>
        )}
      </div>

      {/* Seen properties list */}
      {seen_properties.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 text-sm font-semibold text-[var(--ink)]">
            Properties Reviewed ({seen_properties.length})
          </h2>
          <ul className="space-y-2">
            {seen_properties.map((sp, i) => {
              const isExploreProp = i < status.explore_threshold;
              const wouldBid = deriveWouldBid(sp);
              const isLegacy = sp.bidding_intent === null;
              const beatsMax =
                status.phase === "commit" && !isExploreProp && wouldBid;
              return (
                <li
                  key={sp.id}
                  className={[
                    "flex items-center justify-between rounded-lg border px-3 py-2 text-sm",
                    isExploreProp
                      ? "border-[var(--line)] bg-[var(--bg)]"
                      : beatsMax
                        ? "border-emerald-200 bg-emerald-50"
                        : "border-[var(--line)] bg-white",
                  ].join(" ")}
                >
                  <div>
                    <span className="font-medium text-[var(--ink)]">
                      {sp.address_snapshot}
                    </span>
                    {isLegacy && (
                      <span className="ml-2 text-xs text-[var(--ink-muted)]">
                        {sp.quality} / {sp.location} (legacy)
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {wouldBid ? (
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Would bid
                      </span>
                    ) : (
                      <span className="rounded bg-[var(--bg)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--ink-muted)]">
                        Skip
                      </span>
                    )}
                    {isExploreProp && (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                        Explore
                      </span>
                    )}
                    {beatsMax && (
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Commit
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </main>
  );
}
