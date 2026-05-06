import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../lib/AuthContext";
import { authHeaders, clearToken } from "../lib/auth";
import { apiBase } from "../lib/api";

interface RateLimitStatus {
  used: number;
  limit: number;
  remaining: number;
  tier: string;
  window: string;
  is_grandfathered: boolean;
}

export const Route = createFileRoute("/profile")({ component: ProfilePage });

// ── Tier metadata ──────────────────────────────────────────────────────────
const TIER_META: Record<
  string,
  {
    label: string;
    tagline: string;
    headerBg: string;
    headerTextColor: string;
    headerSoftColor: string;
    badgeBg: string;
    badgeText: string;
    features: string[];
  }
> = {
  buyer: {
    label: "Buyer",
    tagline: "For the serious home shopper",
    headerBg: "var(--bg)",
    headerTextColor: "var(--ink)",
    headerSoftColor: "var(--ink-soft)",
    badgeBg: "var(--line)",
    badgeText: "var(--ink-soft)",
    features: [
      "AI-powered offer recommendation",
      "Fair value estimate & confidence interval",
      "Fire, flood & seismic risk assessment",
      "School ratings & transit proximity",
      "Renovation cost estimate",
    ],
  },
  investor: {
    label: "Investor",
    tagline: "For investors who run the numbers",
    headerBg: "linear-gradient(140deg, var(--coral) 0%, #e06e3f 100%)",
    headerTextColor: "white",
    headerSoftColor: "rgba(255,255,255,0.75)",
    badgeBg: "var(--coral)",
    badgeText: "white",
    features: [
      "Everything in Buyer",
      "Investment projections (10/20/30yr)",
      "Comparable sales table",
      "RentCast rent estimates",
      "Analysis history — 6 months",
    ],
  },
  agent: {
    label: "Agent",
    tagline: "For agents who close deals",
    headerBg: "linear-gradient(140deg, var(--navy) 0%, var(--navy-mid) 100%)",
    headerTextColor: "white",
    headerSoftColor: "rgba(255,255,255,0.6)",
    badgeBg: "var(--navy)",
    badgeText: "white",
    features: [
      "Everything in Investor",
      "PDF export for clients",
      "Unlimited analysis history",
      "100 analyses / month",
    ],
  },
};

// ── Small icon components ──────────────────────────────────────────────────

function CheckIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 15 15"
      fill="none"
      aria-hidden="true"
      style={{ color: "var(--coral)" }}
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

function ShieldIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M10 2l7 3v5c0 4-3 7.5-7 8.5C6 17.5 3 14 3 10V5l7-3z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ProfilePage() {
  const { user, isLoading, logout } = useAuth();
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSubmitting, setPwSubmitting] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const [rateLimitStatus, setRateLimitStatus] = useState<RateLimitStatus | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingError, setBillingError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !user) {
      navigate({ to: "/login" });
    }
  }, [isLoading, user, navigate]);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const resp = await fetch(`${apiBase}/api/rate-limit/status`, {
          headers: authHeaders(),
        });
        if (resp.ok) {
          setRateLimitStatus(await resp.json());
        }
      } catch {
        // non-critical — leave null
      }
    })();
  }, [user]);

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(false);
    setPwSubmitting(true);
    try {
      const resp = await fetch(`${apiBase}/api/users/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ password: newPassword }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to update password");
      }
      setNewPassword("");
      setPwSuccess(true);
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to update password");
    } finally {
      setPwSubmitting(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleteError(null);
    setDeleteSubmitting(true);
    try {
      const resp = await fetch(`${apiBase}/api/users/me`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!resp.ok) {
        throw new Error("Failed to delete account");
      }
      clearToken();
      logout();
      navigate({ to: "/" });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete account");
      setDeleteSubmitting(false);
    }
  }

  async function handleManageBilling() {
    setBillingError(null);
    setBillingLoading(true);
    try {
      const resp = await fetch(`${apiBase}/api/payments/customer-portal`, {
        headers: authHeaders(),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to open billing portal");
      }
      const data = await resp.json();
      window.location.href = data.url;
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : "Something went wrong");
      setBillingLoading(false);
    }
  }

  async function handleUpgrade(priceId: string) {
    try {
      const resp = await fetch(`${apiBase}/api/payments/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ price_id: priceId }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to start checkout");
      }
      const data = await resp.json();
      window.location.href = data.url;
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  if (isLoading || !user) return null;

  const tier = user.subscription_tier ?? "buyer";
  const isInvestorPlus =
    user.is_superuser ||
    tier === "investor" ||
    tier === "agent";

  function handleSetupBuyingPlan() {
    const key = `homebidder_onboarding_done_${user!.id}`;
    localStorage.removeItem(key);
    navigate({ to: "/welcome" });
  }
  const meta = TIER_META[tier] ?? TIER_META.buyer;
  const initials = (user.email ?? "?")
    .split("@")[0]
    .slice(0, 2)
    .toUpperCase();

  const usagePct =
    rateLimitStatus && rateLimitStatus.limit > 0
      ? Math.min(100, Math.round((rateLimitStatus.used / rateLimitStatus.limit) * 100))
      : 0;

  return (
    <main className="page-wrap py-12">
      {/* ── Page header ──────────────────────────────────────────── */}
      <div className="mb-10 fade-up">
        <p
          className="mb-2 text-xs font-semibold uppercase tracking-[0.18em]"
          style={{ color: "var(--coral)" }}
        >
          Account
        </p>
        <h1 className="display-title text-[2rem] font-bold leading-[1.1] tracking-[-0.02em] text-[var(--ink)]">
          Your profile
        </h1>
      </div>

      <div className="space-y-5">
        {/* ── Top row: Account info + Subscription ─────────────────── */}
        <div className="fade-up stagger-1 grid gap-5 sm:grid-cols-[1fr_1.5fr]">

          {/* Account info card */}
          <div className="card overflow-hidden">
            <div
              className="px-6 py-5"
              style={{ background: "linear-gradient(140deg, var(--navy) 0%, var(--navy-mid) 100%)" }}
            >
              {/* Avatar */}
              <div
                className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl text-xl font-bold text-white"
                style={{ background: "rgba(255,255,255,0.15)", letterSpacing: "0.04em" }}
                aria-hidden="true"
              >
                {initials}
              </div>
              <p className="text-[0.8rem] font-medium" style={{ color: "rgba(255,255,255,0.55)" }}>
                Signed in as
              </p>
              <p className="mt-0.5 truncate text-sm font-semibold text-white">{user.email}</p>
            </div>

            <div className="px-6 py-4">
              <div className="flex items-center gap-2">
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                  style={{ background: meta.badgeBg, color: meta.badgeText }}
                >
                  {meta.label}
                </span>
                {user.is_grandfathered && (
                  <span className="text-xs text-[var(--ink-muted)]">(grandfathered)</span>
                )}
              </div>
            </div>
          </div>

          {/* Subscription card */}
          <div className="card overflow-hidden">
            {/* Colored header band */}
            <div
              className="px-6 pb-4 pt-5"
              style={{ background: meta.headerBg }}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p
                    className="text-[0.72rem] font-semibold uppercase tracking-[0.14em]"
                    style={{ color: meta.headerSoftColor }}
                  >
                    Current plan
                  </p>
                  <p
                    className="display-title mt-0.5 text-[1.5rem] font-bold leading-none"
                    style={{ color: meta.headerTextColor }}
                  >
                    {meta.label}
                  </p>
                  <p className="mt-1 text-[0.8rem]" style={{ color: meta.headerSoftColor }}>
                    {meta.tagline}
                  </p>
                </div>
                <Link
                  to="/pricing"
                  className="shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-opacity hover:opacity-80"
                  style={
                    tier === "buyer"
                      ? { borderColor: "var(--card-border)", color: "var(--ink-soft)", background: "white" }
                      : { borderColor: "rgba(255,255,255,0.35)", color: "white", background: "rgba(255,255,255,0.15)" }
                  }
                >
                  View plans
                </Link>
              </div>
            </div>

            <div className="px-6 py-5 space-y-5">
              {/* Usage meter */}
              {rateLimitStatus && (
                <div>
                  <div className="mb-1.5 flex items-center justify-between text-xs text-[var(--ink-soft)]">
                    <span>Analyses this month</span>
                    <span className="font-semibold text-[var(--ink)]">
                      {rateLimitStatus.used} of {rateLimitStatus.limit}
                    </span>
                  </div>
                  <div
                    className="h-1.5 w-full overflow-hidden rounded-full"
                    style={{ background: "var(--line)" }}
                    role="progressbar"
                    aria-valuenow={rateLimitStatus.used}
                    aria-valuemax={rateLimitStatus.limit}
                    aria-label="Monthly analysis usage"
                  >
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${usagePct}%`,
                        background:
                          usagePct >= 90
                            ? "var(--coral)"
                            : usagePct >= 70
                            ? "var(--amber)"
                            : "var(--green)",
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Features */}
              <ul className="space-y-1.5">
                {meta.features.map((feat, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
                    <span className="shrink-0">
                      <CheckIcon />
                    </span>
                    {feat}
                  </li>
                ))}
              </ul>

              {/* Billing error */}
              {billingError && (
                <p role="alert" className="text-sm text-red-600">{billingError}</p>
              )}

              {/* CTA buttons */}
              <div className="flex flex-wrap gap-2 pt-1">
                {tier === "buyer" && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleUpgrade(import.meta.env.VITE_STRIPE_INVESTOR_PRICE_ID ?? "")}
                      className="cursor-pointer rounded-lg bg-[var(--coral)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
                    >
                      Upgrade to Investor
                    </button>
                    <button
                      type="button"
                      onClick={() => handleUpgrade(import.meta.env.VITE_STRIPE_AGENT_PRICE_ID ?? "")}
                      className="cursor-pointer rounded-lg border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--ink-soft)] hover:text-[var(--ink)]"
                    >
                      Upgrade to Agent
                    </button>
                  </>
                )}
                {tier === "investor" && (
                  <button
                    type="button"
                    onClick={() => handleUpgrade(import.meta.env.VITE_STRIPE_AGENT_PRICE_ID ?? "")}
                    className="cursor-pointer rounded-lg bg-[var(--coral)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
                  >
                    Upgrade to Agent
                  </button>
                )}
                {tier !== "buyer" && (
                  <button
                    type="button"
                    onClick={handleManageBilling}
                    disabled={billingLoading}
                    className="cursor-pointer rounded-lg border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--ink-soft)] hover:text-[var(--ink)] disabled:opacity-50"
                  >
                    {billingLoading ? "Loading…" : "Manage billing"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── Security card ─────────────────────────────────────────── */}
        <div className="card fade-up stagger-2 p-6">
          <div className="mb-5 flex items-center gap-2.5">
            <span className="text-[var(--ink-soft)]">
              <ShieldIcon />
            </span>
            <h2 className="text-base font-semibold text-[var(--ink)]">Security</h2>
          </div>

          {pwSuccess && (
            <p className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700">
              Password updated successfully.
            </p>
          )}
          {pwError && (
            <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-600">
              {pwError}
            </p>
          )}

          <form onSubmit={handleChangePassword} className="max-w-sm space-y-4">
            <div>
              <label
                htmlFor="new-password"
                className="mb-1.5 block text-sm font-medium text-[var(--ink)]"
              >
                New password
              </label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-lg border border-[var(--line)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--ink)] outline-none focus:ring-2 focus:ring-[var(--navy)]"
                placeholder="At least 8 characters"
              />
            </div>
            <button
              type="submit"
              disabled={pwSubmitting}
              className="cursor-pointer rounded-lg bg-[var(--navy)] px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {pwSubmitting ? "Updating…" : "Update password"}
            </button>
          </form>
        </div>

        {/* ── Buying Plan card (investor/agent only) ───────────────── */}
        {isInvestorPlus && (
          <div className="card fade-up stagger-3 p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-[var(--ink)] mb-1">Buying Plan</h2>
                <p className="text-sm text-[var(--ink-soft)]">
                  Use the secretary-problem algorithm to decide when to stop exploring and commit.
                  Set a buy-by date and viewing pace to get your optimal explore threshold.
                </p>
              </div>
              <button
                type="button"
                onClick={handleSetupBuyingPlan}
                className="shrink-0 cursor-pointer rounded-lg bg-[var(--coral)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
              >
                Set up Buying Plan
              </button>
            </div>
          </div>
        )}

        {/* ── Danger zone ───────────────────────────────────────────── */}
        <div className="card fade-up stagger-3 overflow-hidden">
          <div className="border-b border-red-100 bg-red-50 px-6 py-4">
            <h2 className="text-sm font-semibold text-red-700">Danger zone</h2>
          </div>
          <div className="px-6 py-5">
            <p className="mb-4 text-sm text-[var(--ink-soft)]">
              Deleting your account is permanent. Your saved analyses will be kept but become
              anonymous.
            </p>

            {deleteError && (
              <p role="alert" className="mb-4 text-sm text-red-700">{deleteError}</p>
            )}

            {!showDeleteConfirm ? (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                className="cursor-pointer rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
              >
                Delete account
              </button>
            ) : (
              <div className="space-y-3">
                <p className="text-sm font-semibold text-red-700">
                  Are you sure? This cannot be undone.
                </p>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleDeleteAccount}
                    disabled={deleteSubmitting}
                    className="cursor-pointer rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                  >
                    {deleteSubmitting ? "Deleting…" : "Confirm delete"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(false)}
                    className="cursor-pointer rounded-lg border border-[var(--line)] px-4 py-2 text-sm text-[var(--ink-soft)] hover:text-[var(--ink)]"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
