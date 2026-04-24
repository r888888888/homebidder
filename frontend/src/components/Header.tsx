import { Link, useMatchRoute } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../lib/AuthContext'

function getInitials(displayName: string | null | undefined, email: string): string {
  if (displayName) {
    const parts = displayName.trim().split(/\s+/)
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return parts[0][0].toUpperCase()
  }
  return email[0].toUpperCase()
}

export default function Header() {
  const { user, isLoading, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const matchRoute = useMatchRoute()

  const isOnHistory = !!matchRoute({ to: '/history', fuzzy: false })

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  // Deepen header shadow on scroll
  useEffect(() => {
    function onScroll() { setScrolled(window.scrollY > 8) }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={[
        'sticky top-0 z-50 border-b border-[var(--line)] bg-[var(--header-bg)] px-4 backdrop-blur-lg',
        scrolled ? 'shadow-[0_4px_24px_rgba(15,32,53,0.10)]' : '',
      ].join(' ')}
    >
      <nav className="page-wrap flex items-center gap-x-3 py-3 sm:py-4">
        {/* Logo */}
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

        {/* Right-side nav */}
        <div className="ml-auto flex items-center gap-x-3">
          {/* History — only shown when logged in */}
          {!isLoading && user && (
            <Link
              to="/history"
              className={[
                'text-sm no-underline transition-colors',
                isOnHistory
                  ? 'font-semibold text-[var(--ink)]'
                  : 'text-[var(--ink-soft)] hover:text-[var(--ink)]',
              ].join(' ')}
            >
              <span
                className={[
                  'relative pb-0.5',
                  isOnHistory
                    ? 'after:absolute after:inset-x-0 after:-bottom-0.5 after:h-[2px] after:rounded-full after:bg-[var(--coral)]'
                    : '',
                ].join(' ')}
              >
                History
              </span>
            </Link>
          )}

          {/* Auth controls */}
          {!isLoading && (
            user ? (
              // User avatar + dropdown
              <div ref={menuRef} className="relative">
                <button
                  type="button"
                  aria-label="Account menu"
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen((v) => !v)}
                  className={[
                    'flex h-8 w-8 items-center justify-center rounded-full bg-[var(--navy)] text-xs font-bold text-white',
                    menuOpen ? 'opacity-80' : 'hover:opacity-90',
                  ].join(' ')}
                >
                  {getInitials(user.display_name, user.email)}
                </button>

                {menuOpen && (
                  <div className="card scale-in absolute right-0 top-10 z-10 min-w-[172px] overflow-hidden py-1">
                    {/* Account info header */}
                    <div className="border-b border-[var(--line)] px-4 py-2.5">
                      <p className="truncate text-xs font-semibold text-[var(--ink)]">
                        {user.display_name ?? user.email.split('@')[0]}
                      </p>
                      <p className="truncate text-[11px] text-[var(--ink-muted)]">
                        {user.email}
                      </p>
                    </div>
                    <Link
                      to="/profile"
                      className="block px-4 py-2 text-sm text-[var(--ink-soft)] no-underline hover:bg-[var(--bg)] hover:text-[var(--ink)]"
                      onClick={() => setMenuOpen(false)}
                    >
                      Profile &amp; settings
                    </Link>
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); logout() }}
                      className="w-full px-4 py-2 text-left text-sm text-[var(--ink-soft)] hover:bg-[var(--bg)] hover:text-[var(--ink)]"
                    >
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-sm text-[var(--ink-soft)] no-underline hover:text-[var(--ink)]"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="rounded-lg bg-[var(--coral)] px-3 py-1.5 text-sm font-semibold text-white no-underline hover:bg-[var(--coral-hover)]"
                >
                  Sign up
                </Link>
              </>
            )
          )}
        </div>
      </nav>
    </header>
  )
}
