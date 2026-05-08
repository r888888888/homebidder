import { Link } from "@tanstack/react-router";

export function AffordabilityCalculatorTeaserCard() {
  return (
    <div className="card overflow-hidden fade-up">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-6 py-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Affordability Calculator
        </p>
      </div>

      <div className="px-6 py-5">
        <div className="rounded-xl border border-[var(--line)] bg-[var(--bg)] px-4 py-4">
          <div className="flex items-center gap-2 mb-2">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-[var(--ink-muted)]"
              aria-hidden="true"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <p className="text-sm font-semibold text-[var(--ink)]">
              Unlock Affordability Calculator
            </p>
          </div>
          <p className="text-xs text-[var(--ink-soft)] mb-3">
            Find out how much you can borrow against your income and debts. Personalized DTI-based max purchase price and affordability gap for this property and every future analysis.
          </p>
          <Link
            to="/pricing"
            className="inline-flex items-center rounded-lg bg-[var(--coral)] px-3 py-1.5 text-xs font-semibold text-white no-underline hover:opacity-90"
          >
            Upgrade to Investor
          </Link>
        </div>
      </div>
    </div>
  );
}
