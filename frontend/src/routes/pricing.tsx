import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "../lib/AuthContext";
import { authHeaders } from "../lib/auth";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/pricing")({ component: PricingPage });

const INVESTOR_PRICE_ID = import.meta.env.VITE_STRIPE_INVESTOR_PRICE_ID ?? "";
const AGENT_PRICE_ID = import.meta.env.VITE_STRIPE_AGENT_PRICE_ID ?? "";

interface Feature {
  text: string;
  highlight?: boolean;
}

interface Plan {
  tier: "buyer" | "investor" | "agent";
  name: string;
  price: string;
  priceSuffix: string;
  analyses: string;
  tagline: string;
  priceId: string | null;
  featured: boolean;
  features: Feature[];
  lockedFeatures?: string[];
}

const PLANS: Plan[] = [
  {
    tier: "buyer",
    name: "Buyer",
    price: "Free",
    priceSuffix: "forever",
    analyses: "5 analyses / month",
    tagline: "For the serious home shopper",
    priceId: null,
    featured: false,
    features: [
      { text: "AI-powered offer recommendation" },
      { text: "Fair value estimate & confidence interval" },
      { text: "Fire, flood & seismic risk assessment" },
      { text: "School ratings & transit proximity" },
      { text: "Renovation cost estimate" },
      { text: "5 analyses / month" },
    ],
    lockedFeatures: ["Investment projections", "Comparable sales table", "PDF export"],
  },
  {
    tier: "investor",
    name: "Investor",
    price: "$10",
    priceSuffix: "/ month",
    analyses: "30 analyses / month",
    tagline: "For investors who run the numbers",
    priceId: INVESTOR_PRICE_ID,
    featured: true,
    features: [
      { text: "Everything in Buyer" },
      { text: "Investment projections (10/20/30yr)", highlight: true },
      { text: "Comparable sales table", highlight: true },
      { text: "RentCast rent estimates", highlight: true },
      { text: "Analysis history — 6 months", highlight: true },
      { text: "30 analyses / month", highlight: true },
    ],
    lockedFeatures: ["PDF export for clients"],
  },
  {
    tier: "agent",
    name: "Agent",
    price: "$30",
    priceSuffix: "/ month",
    analyses: "100 analyses / month",
    tagline: "For agents who close deals",
    priceId: AGENT_PRICE_ID,
    featured: false,
    features: [
      { text: "Everything in Investor" },
      { text: "PDF export for clients", highlight: true },
      { text: "Unlimited analysis history", highlight: true },
      { text: "100 analyses / month", highlight: true },
    ],
  },
];

function CheckIcon({ coral }: { coral?: boolean }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 15 15"
      fill="none"
      aria-hidden="true"
      style={{ color: coral ? "var(--coral)" : "var(--green, #059669)" }}
    >
      <path
        d="M2.5 7.5l3.5 3.5 6.5-7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <rect x="2" y="6" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4.5 6V5a2.5 2.5 0 015 0v1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

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
    <main className="page-wrap py-16">
      {/* ── Page header ─────────────────────────────────────────── */}
      <div className="mb-12 text-center fade-up">
        <p
          className="mb-3 text-xs font-semibold uppercase tracking-[0.18em]"
          style={{ color: "var(--coral)" }}
        >
          Pricing
        </p>
        <h1
          className="display-title text-[2.75rem] font-bold leading-[1.08] tracking-[-0.03em] text-[var(--ink)] sm:text-5xl"
        >
          Know before you bid.
        </h1>
        <p className="mx-auto mt-4 max-w-sm text-[1.05rem] leading-relaxed text-[var(--ink-soft)]">
          AI analysis for SF Bay Area properties — from first look to offer letter.
        </p>
      </div>

      {/* ── Anonymous callout ────────────────────────────────────── */}
      <div className="fade-up stagger-1 mb-12 flex justify-center">
        <div
          className="inline-flex items-center gap-3 rounded-full border border-[var(--line)] bg-white px-5 py-2.5 text-sm shadow-sm"
        >
          <span
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-white text-[10px] font-bold"
            style={{ background: "var(--coral)" }}
            aria-hidden="true"
          >
            i
          </span>
          <span className="text-[var(--ink-soft)]">
            No account?{" "}
            <span className="font-semibold text-[var(--ink)]">3 free analyses per month</span>{" "}
            — sign up for more.
          </span>
        </div>
      </div>

      {/* ── Error ───────────────────────────────────────────────── */}
      {error && (
        <div
          role="alert"
          className="fade-up mx-auto mb-10 max-w-md rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-center text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {/* ── Plan cards ──────────────────────────────────────────── */}
      <div className="fade-up stagger-2 grid gap-5 sm:grid-cols-3 sm:items-start">
        {PLANS.map((plan) => {
          const isCurrent = currentTier === plan.tier;
          const isUpgradeable = plan.priceId !== null && !isCurrent;

          /* Per-tier color identities */
          const headerBg =
            plan.featured
              ? "linear-gradient(140deg, var(--coral) 0%, #e06e3f 100%)"
              : plan.tier === "agent"
              ? "linear-gradient(140deg, var(--navy) 0%, var(--navy-mid) 100%)"
              : "var(--bg)";

          const headerTextColor =
            plan.featured || plan.tier === "agent" ? "white" : "var(--ink)";
          const headerSoftColor =
            plan.featured
              ? "rgba(255,255,255,0.75)"
              : plan.tier === "agent"
              ? "rgba(255,255,255,0.6)"
              : "var(--ink-soft)";

          const ctaBg =
            plan.tier === "agent" ? "var(--navy)" : "var(--coral)";

          return (
            <div
              key={plan.tier}
              className={[
                "card flex flex-col overflow-hidden",
                plan.featured ? "sm:-mt-5 sm:mb-5" : "",
              ].join(" ")}
              style={
                plan.featured
                  ? {
                      borderColor: "var(--coral)",
                      boxShadow:
                        "0 12px 48px rgba(221, 95, 59, 0.20), 0 2px 8px rgba(15, 32, 53, 0.08)",
                    }
                  : undefined
              }
            >
              {/* Header band */}
              <div
                className="px-6 pb-5 pt-6"
                style={{ background: headerBg }}
              >
                <div className="mb-3 flex items-center justify-between gap-2">
                  <h2
                    className="display-title text-[1.6rem] font-bold leading-none"
                    style={{ color: headerTextColor }}
                  >
                    {plan.name}
                  </h2>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {isCurrent && (
                      <span
                        className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
                        style={
                          plan.featured || plan.tier === "agent"
                            ? { background: "rgba(255,255,255,0.22)", color: "white" }
                            : { background: "var(--coral)", color: "white" }
                        }
                      >
                        Current plan
                      </span>
                    )}
                    {plan.featured && !isCurrent && (
                      <span
                        className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
                        style={{ background: "rgba(255,255,255,0.22)", color: "white" }}
                      >
                        Popular
                      </span>
                    )}
                  </div>
                </div>

                <p className="mb-4 text-[0.8rem]" style={{ color: headerSoftColor }}>
                  {plan.tagline}
                </p>

                <div className="flex items-baseline gap-1.5">
                  <span
                    className="text-[2rem] font-bold leading-none"
                    style={{ color: headerTextColor }}
                  >
                    {plan.price}
                  </span>
                  <span className="text-sm" style={{ color: headerSoftColor }}>
                    {plan.priceSuffix}
                  </span>
                </div>
              </div>

              {/* Feature list */}
              <div className="flex flex-1 flex-col gap-5 p-6">
                <ul className="space-y-2.5">
                  {plan.features.map((feat, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm">
                      <span className="mt-px shrink-0">
                        <CheckIcon coral={feat.highlight} />
                      </span>
                      <span
                        className={
                          feat.highlight
                            ? "font-medium text-[var(--ink)]"
                            : "text-[var(--ink-soft)]"
                        }
                      >
                        {feat.text}
                      </span>
                    </li>
                  ))}
                </ul>

                {plan.lockedFeatures && plan.lockedFeatures.length > 0 && (
                  <ul className="space-y-2 border-t border-[var(--line)] pt-4 opacity-35">
                    {plan.lockedFeatures.map((feat, i) => (
                      <li key={i} className="flex items-center gap-2.5 text-sm text-[var(--ink-soft)]">
                        <span className="shrink-0">
                          <LockIcon />
                        </span>
                        {feat}
                      </li>
                    ))}
                  </ul>
                )}

                {/* CTA */}
                <div className="mt-auto pt-2">
                  {isUpgradeable && !isLoading && (
                    <button
                      type="button"
                      onClick={() => handleUpgrade(plan)}
                      disabled={upgrading === plan.tier}
                      className="w-full rounded-xl py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-50"
                      style={{ background: ctaBg }}
                    >
                      {upgrading === plan.tier ? "Redirecting…" : "Upgrade"}
                    </button>
                  )}

                  {plan.tier === "buyer" && !user && !isLoading && (
                    <a
                      href="/register"
                      className="block w-full rounded-xl border border-[var(--line)] py-2.5 text-center text-sm font-semibold text-[var(--ink)] transition-colors hover:bg-[var(--bg)]"
                    >
                      Sign up
                    </a>
                  )}

                  {isCurrent && (
                    <p className="py-1.5 text-center text-sm text-[var(--ink-soft)]">
                      You're on this plan
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Trust strip ─────────────────────────────────────────── */}
      <div className="fade-up stagger-3 mt-14 flex flex-col items-center gap-2 text-center">
        <p className="text-xs text-[var(--ink-soft)] opacity-60">
          Secure payments via Stripe &nbsp;·&nbsp; Cancel anytime &nbsp;·&nbsp; No hidden fees
        </p>
      </div>
    </main>
  );
}
