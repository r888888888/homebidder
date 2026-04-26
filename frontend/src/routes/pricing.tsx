import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "../lib/AuthContext";
import { authHeaders } from "../lib/auth";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/pricing")({ component: PricingPage });

const INVESTOR_PRICE_ID = import.meta.env.VITE_STRIPE_INVESTOR_PRICE_ID ?? "";
const AGENT_PRICE_ID = import.meta.env.VITE_STRIPE_AGENT_PRICE_ID ?? "";

interface Plan {
  tier: "buyer" | "investor" | "agent";
  name: string;
  price: string;
  analyses: string;
  priceId: string | null;
  featured: boolean;
}

const PLANS: Plan[] = [
  {
    tier: "buyer",
    name: "Buyer",
    price: "Free",
    analyses: "5 analyses / month",
    priceId: null,
    featured: false,
  },
  {
    tier: "investor",
    name: "Investor",
    price: "$10 / month",
    analyses: "30 analyses / month",
    priceId: INVESTOR_PRICE_ID,
    featured: true,
  },
  {
    tier: "agent",
    name: "Agent",
    price: "$30 / month",
    analyses: "100 analyses / month",
    priceId: AGENT_PRICE_ID,
    featured: false,
  },
];

export default function PricingPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpgrade(plan: Plan) {
    if (!user) {
      navigate({ to: "/login" });
      return;
    }
    if (!plan.priceId) return;

    setError(null);
    setUpgrading(plan.tier);
    try {
      const resp = await fetch(`${apiBase}/api/payments/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ price_id: plan.priceId }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to start checkout");
      }
      const data = await resp.json();
      window.location.href = data.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setUpgrading(null);
    }
  }

  const currentTier = user?.subscription_tier ?? null;

  return (
    <main className="page-wrap py-10">
      <div className="space-y-8">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-[var(--ink)]">Pricing</h1>
          <p className="text-[var(--ink-soft)]">
            Analyze SF Bay Area properties with AI-powered offer guidance.
          </p>
        </div>

        {/* Anonymous usage callout */}
        <div className="rounded-lg border border-[var(--line)] bg-[var(--bg-subtle,#f8f8f6)] px-4 py-3 text-sm text-[var(--ink-soft)]">
          No account? Get{" "}
          <span className="font-semibold text-[var(--ink)]">3 free analyses per month</span>{" "}
          — sign up for more.
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        {/* Plan cards */}
        <div className="grid gap-6 sm:grid-cols-3">
          {PLANS.map((plan) => {
            const isCurrent = currentTier === plan.tier;
            const isUpgradeable = plan.priceId !== null && !isCurrent;

            return (
              <div
                key={plan.tier}
                className={[
                  "card flex flex-col gap-4 p-6",
                  plan.featured
                    ? "border-[var(--coral)] ring-1 ring-[var(--coral)]"
                    : "",
                ].join(" ")}
              >
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-xl font-bold text-[var(--ink)]">{plan.name}</h2>
                  {isCurrent && (
                    <span className="shrink-0 rounded-full bg-[var(--coral)] px-2.5 py-0.5 text-xs font-semibold text-white">
                      Current plan
                    </span>
                  )}
                  {plan.featured && !isCurrent && (
                    <span className="shrink-0 rounded-full bg-[var(--coral)] px-2.5 py-0.5 text-xs font-semibold text-white">
                      Popular
                    </span>
                  )}
                </div>

                <div>
                  <p className="text-2xl font-bold text-[var(--ink)]">{plan.price}</p>
                  <p className="text-sm text-[var(--ink-soft)]">{plan.analyses}</p>
                </div>

                <ul className="flex-1 space-y-1.5 text-sm text-[var(--ink-soft)]">
                  <li>All analysis features</li>
                  {plan.tier !== "buyer" || user ? (
                    <li>Analysis history &amp; permalinks</li>
                  ) : null}
                </ul>

                {isUpgradeable && !isLoading && (
                  <button
                    type="button"
                    onClick={() => handleUpgrade(plan)}
                    disabled={upgrading === plan.tier}
                    className="rounded-lg bg-[var(--coral)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--coral-hover)] disabled:opacity-50"
                  >
                    {upgrading === plan.tier ? "Redirecting…" : "Upgrade"}
                  </button>
                )}

                {plan.tier === "buyer" && !user && !isLoading && (
                  <a
                    href="/register"
                    className="block rounded-lg border border-[var(--line)] px-4 py-2 text-center text-sm font-semibold text-[var(--ink)] hover:bg-[var(--bg)]"
                  >
                    Sign up
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
