import { Link } from '@tanstack/react-router'

export default function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--line)] bg-[var(--header-bg)] px-4 backdrop-blur-lg">
      <nav className="page-wrap flex items-center gap-x-3 py-3 sm:py-4">
        <Link to="/" className="flex items-center gap-2 no-underline">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
            <path
              d="M14 3L2 13h3v11h7v-7h4v7h7V13h3L14 3z"
              fill="var(--navy)"
              stroke="var(--navy)"
              strokeWidth="1"
              strokeLinejoin="round"
            />
            <circle cx="14" cy="16" r="2.5" fill="var(--coral)" />
          </svg>
          <span className="text-base font-semibold tracking-tight text-[var(--ink)]">
            HomeBidder
          </span>
        </Link>
      </nav>
    </header>
  )
}
