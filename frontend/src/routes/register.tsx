import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useAuth } from "../lib/AuthContext";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/register")({ component: RegisterPage });

export default function RegisterPage() {
  const { register } = useAuth();
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
      await register(email, password);
      navigate({ to: "/" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page-wrap flex flex-col items-center py-16">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-2xl font-bold text-[var(--ink)]">Create account</h1>

        {error && (
          <div role="alert" className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-[var(--ink)] mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-[var(--line)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus:ring-2 focus:ring-[var(--navy)]"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-[var(--ink)] mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-[var(--line)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus:ring-2 focus:ring-[var(--navy)]"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-[var(--navy)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <div className="relative my-2 flex items-center">
          <div className="flex-grow border-t border-[var(--line)]" />
          <span className="mx-3 text-xs text-[var(--ink-muted)]">or</span>
          <div className="flex-grow border-t border-[var(--line)]" />
        </div>

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
          className="flex w-full items-center justify-center gap-2 rounded border border-[var(--line)] bg-[var(--bg)] px-4 py-2 text-sm font-medium text-[var(--ink)] hover:bg-[var(--bg-soft)]"
        >
          Continue with Google
        </button>

        <p className="text-sm text-[var(--ink-soft)]">
          Already have an account?{" "}
          <Link to="/login" className="text-[var(--navy)] underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
