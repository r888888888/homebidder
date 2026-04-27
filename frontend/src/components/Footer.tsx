import { Link } from '@tanstack/react-router'
import { useAuth } from '../lib/AuthContext'

export default function Footer() {
  const year = new Date().getFullYear()
  const { user } = useAuth()

  return (
    <footer
      className="mt-20 border-t border-[var(--line)] px-4 pb-12 pt-10"
      style={{ background: 'linear-gradient(to bottom, rgba(15,32,53,0.025) 0%, transparent 60%)' }}
    >
      <div className="page-wrap flex flex-col items-center gap-3 text-center">
        {/* Logomark */}
        <div className="flex items-center gap-2 text-[var(--ink-soft)]">
          <svg width="20" height="20" viewBox="0 0 28 28" fill="none" aria-hidden="true">
            <path
              d="M14 3L2 13h3v11h7v-7h4v7h7V13h3L14 3z"
              fill="currentColor"
            />
            <circle cx="14" cy="16" r="2.5" fill="var(--coral)" />
          </svg>
          <span className="text-sm font-semibold tracking-tight">HomeBidder</span>
        </div>

        <p className="m-0 text-xs text-[var(--ink-muted)]">&copy; {year} HomeBidder</p>

        <nav className="flex items-center gap-4">
          <Link
            to="/faq"
            className="text-xs text-[var(--ink-muted)] no-underline hover:text-[var(--ink-soft)]"
          >
            FAQ
          </Link>
          <Link
            to="/changelog"
            className="text-xs text-[var(--ink-muted)] no-underline hover:text-[var(--ink-soft)]"
          >
            Changelog
          </Link>
          {user?.is_superuser && (
            <Link
              to="/admin"
              className="text-xs text-[var(--ink-muted)] no-underline hover:text-[var(--ink-soft)]"
            >
              Admin
            </Link>
          )}
        </nav>

        <p className="m-0 max-w-md text-xs leading-relaxed text-[var(--ink-muted)]">
          For informational purposes only. Not a substitute for professional real estate advice.
          Always consult a licensed agent before making an offer.
        </p>
      </div>
    </footer>
  )
}
