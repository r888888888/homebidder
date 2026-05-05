import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../lib/AuthContext";
import { authHeaders } from "../lib/auth";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/welcome")({ component: WelcomePage });

export function WelcomePage() {
  const navigate = useNavigate();
  const { user, isLoading } = useAuth();

  const isInvestorPlus =
    user?.is_superuser ||
    user?.subscription_tier === "investor" ||
    user?.subscription_tier === "agent";

  const onboardingKey = user ? `homebidder_onboarding_done_${user.id}` : null;

  useEffect(() => {
    if (!isLoading && (!user || (onboardingKey && localStorage.getItem(onboardingKey)))) {
      navigate({ to: "/" });
    }
  }, [isLoading, user, onboardingKey, navigate]);

  if (isLoading || !user) return null;

  function markDone() {
    localStorage.setItem(onboardingKey!, "1");
  }

  function skip() {
    markDone();
    navigate({ to: "/" });
  }

  return (
    <main className="page-wrap flex flex-col items-center py-16">
      <div className="w-full max-w-md space-y-8">
        <div>
          <h1 className="display-title text-3xl font-bold text-[var(--ink)] mb-2">
            Welcome to HomeBidder
          </h1>
          <p className="text-[var(--ink-soft)]">
            AI-powered offer analysis for SF Bay Area properties. Let's get you set up.
          </p>
        </div>

        {isInvestorPlus ? (
          <BuyingPlanSetupForm markDone={markDone} onSkip={skip} navigate={navigate} />
        ) : (
          <BuyerTeaserCard onSkip={skip} />
        )}
      </div>
    </main>
  );
}

interface SetupFormProps {
  markDone: () => void;
  onSkip: () => void;
  navigate: (opts: { to: string }) => void;
}

function BuyingPlanSetupForm({ markDone, onSkip, navigate }: SetupFormProps) {
  const [buyByDate, setBuyByDate] = useState("");
  const [viewingsPerWeek, setViewingsPerWeek] = useState("3");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const resp = await fetch(`${apiBase}/api/buying-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          buy_by_date: buyByDate,
          viewings_per_week: parseFloat(viewingsPerWeek),
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? "Failed to create plan.");
      }
      markDone();
      navigate({ to: "/buying-plan" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create plan.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card p-6 space-y-5">
      <div>
        <p className="text-sm font-semibold text-[var(--ink)] mb-1">Set up your Buying Plan</p>
        <p className="text-sm text-[var(--ink-soft)]">
          HomeBidder uses the <strong>secretary-problem algorithm</strong> to tell you exactly when to
          stop exploring and commit to the best home you've seen. Enter your timeline and we'll
          compute your optimal explore threshold.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="buy-by-date" className="mb-1.5 block text-sm font-semibold text-[var(--ink)]">
            Buy-by date
          </label>
          <input
            id="buy-by-date"
            type="date"
            required
            value={buyByDate}
            onChange={(e) => setBuyByDate(e.target.value)}
            className="w-full rounded-xl border border-[var(--card-border)] bg-white px-4 py-3 text-sm text-[var(--ink)] shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
          />
        </div>

        <div>
          <label htmlFor="viewings-per-week" className="mb-1.5 block text-sm font-semibold text-[var(--ink)]">
            Viewings per week
          </label>
          <input
            id="viewings-per-week"
            type="number"
            min="0.5"
            max="20"
            step="0.5"
            required
            value={viewingsPerWeek}
            onChange={(e) => setViewingsPerWeek(e.target.value)}
            className="w-full rounded-xl border border-[var(--card-border)] bg-white px-4 py-3 text-sm text-[var(--ink)] shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-[var(--coral)] px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 cursor-pointer"
        >
          {submitting ? "Setting up…" : "Set up my Buying Plan"}
        </button>
      </form>

      <button
        type="button"
        onClick={onSkip}
        className="block w-full text-center text-sm text-[var(--ink-muted)] underline hover:text-[var(--ink-soft)] cursor-pointer"
      >
        Skip for now
      </button>
    </div>
  );
}

interface TeaserProps {
  onSkip: () => void;
}

function BuyerTeaserCard({ onSkip }: TeaserProps) {
  return (
    <div className="card p-6 space-y-4">
      <div>
        <p className="text-sm font-semibold text-[var(--ink)] mb-1">Buying Plan</p>
        <p className="text-sm text-[var(--ink-soft)]">
          Apply optimal stopping theory to your home search. Set a buy-by date and viewing pace —
          HomeBidder tells you exactly when to stop exploring and start committing.
        </p>
      </div>
      <div className="rounded-lg border border-[var(--line)] bg-[var(--bg-soft,#f9f9f9)] p-4">
        <p className="text-sm font-semibold text-[var(--ink)] mb-1">Investor or Agent plan required</p>
        <p className="text-sm text-[var(--ink-soft)] mb-3">
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

      <button
        type="button"
        onClick={onSkip}
        className="block w-full text-center text-sm text-[var(--ink-muted)] underline hover:text-[var(--ink-soft)] cursor-pointer"
      >
        Skip for now
      </button>
    </div>
  );
}
