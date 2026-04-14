import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../../../lib/AuthContext";
import { apiBase } from "../../../lib/api";

export const Route = createFileRoute("/auth/callback/google")({ component: GoogleCallbackPage });

export default function GoogleCallbackPage() {
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const search = useSearch({ from: "/auth/callback/google" }) as {
    code?: string;
    state?: string;
  };
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const { code, state } = search;
    if (!code) return;

    (async () => {
      try {
        const params = new URLSearchParams({ code, ...(state ? { state } : {}) });
        const resp = await fetch(
          `${apiBase}/api/auth/google/callback?${params.toString()}`
        );
        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}));
          throw new Error(body.detail ?? "Google sign-in failed");
        }
        const data = await resp.json();
        await loginWithToken(data.access_token);
        navigate({ to: "/" });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Google sign-in failed");
      }
    })();
  }, [search, navigate, loginWithToken]);

  if (error) {
    return (
      <main className="page-wrap flex flex-col items-center py-16">
        <div role="alert" className="rounded border border-red-300 bg-red-50 px-6 py-4 text-sm text-red-700 max-w-sm w-full">
          {error}
        </div>
      </main>
    );
  }

  return (
    <main className="page-wrap flex flex-col items-center py-16">
      <p className="text-[var(--ink-soft)]">Signing you in…</p>
    </main>
  );
}
