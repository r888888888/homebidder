import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useAuth } from "../lib/AuthContext";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/login")({ component: LoginPage });

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate({ to: "/" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page-wrap flex flex-col items-center py-16">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-2xl font-bold text-[var(--ink)]">Sign in</h1>

        {error && (
          <div role="alert" className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-[var(--ink)]">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-[var(--card-border)] bg-white px-4 py-3 text-sm text-[var(--ink)] shadow-sm placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-semibold text-[var(--ink)]">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-[var(--card-border)] bg-white px-4 py-3 text-sm text-[var(--ink)] shadow-sm placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-[var(--navy)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="relative my-2 flex items-center">
          <div className="flex-grow border-t border-[var(--line)]" />
          <span className="mx-3 text-xs text-[var(--ink-muted)]">or</span>
          <div className="flex-grow border-t border-[var(--line)]" />
        </div>

        <div className="space-y-3">
          <button
            type="button"
            onClick={async () => {
              try {
                const resp = await fetch(`${apiBase}/api/auth/google/authorize`);
                const data = await resp.json();
                window.location.href = data.authorization_url;
              } catch {
                /* ignore */
              }
            }}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-[var(--card-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--ink)] shadow-sm hover:bg-gray-50 active:scale-[0.98] transition-transform cursor-pointer"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" aria-hidden="true">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <button
            type="button"
            onClick={async () => {
              try {
                const resp = await fetch(`${apiBase}/api/auth/apple/authorize`);
                const data = await resp.json();
                window.location.href = data.authorization_url;
              } catch {
                /* ignore */
              }
            }}
            className="flex w-full items-center justify-center gap-3 rounded-xl bg-black px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-gray-900 active:scale-[0.98] transition-transform cursor-pointer"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" aria-hidden="true" fill="currentColor">
              <path d="M16.52 0c.28 1.94-.56 3.85-1.74 5.23-1.19 1.4-3.07 2.48-4.93 2.34-.33-1.88.6-3.84 1.73-5.1C12.78 1.14 14.74.1 16.52 0zM21.9 17.3c-.72 1.57-1.07 2.27-2 3.63-1.3 1.88-3.13 4.22-5.4 4.24-2.02.02-2.54-1.3-5.28-1.28-2.74.02-3.32 1.31-5.35 1.29-2.27-.03-4-2.13-5.3-4.01C-4.3 16.16-.8 8.72 2.67 5.9c2.42-2 5.9-2.3 7.87-.47.9-.47 3.37-1.84 4.68-1.74 1.26.09 3.36 1.05 4.55 3.42-3.65 2.01-3.06 7.26.13 9.19z"/>
            </svg>
            Continue with Apple
          </button>
        </div>

        <p className="text-sm text-[var(--ink-soft)]">
          Don't have an account?{" "}
          <Link to="/register" className="text-[var(--navy)] underline">
            Create an account
          </Link>
        </p>
      </div>
    </main>
  );
}
