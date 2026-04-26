import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../../../lib/AuthContext";

export const Route = createFileRoute("/auth/callback/apple")({ component: AppleCallbackPage });

export default function AppleCallbackPage() {
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const search = useSearch({ from: "/auth/callback/apple" }) as {
    access_token?: string;
    error?: string;
  };
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const { access_token, error: errorParam } = search;

    if (errorParam) {
      setError(decodeURIComponent(errorParam.replace(/\+/g, " ")));
      return;
    }

    if (!access_token) return;

    (async () => {
      try {
        await loginWithToken(access_token);
        navigate({ to: "/" });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Apple sign-in failed");
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
