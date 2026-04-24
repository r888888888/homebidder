import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/admin")({
  component: AdminPage,
});

interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
}

interface AdminAnalysis {
  id: number;
  address: string | null;
  user_id: string | null;
  offer_low: number | null;
  offer_high: number | null;
  offer_recommended: number | null;
  risk_level: string | null;
  investment_rating: string | null;
  created_at: string | null;
}

export function AdminPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [analyses, setAnalyses] = useState<AdminAnalysis[] | null>(null);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const authHeader = `Basic ${btoa(`${username}:${password}`)}`;
    try {
      const [usersResp, analysesResp] = await Promise.all([
        fetch(`${apiBase}/api/admin/users`, { headers: { Authorization: authHeader } }),
        fetch(`${apiBase}/api/admin/analyses`, { headers: { Authorization: authHeader } }),
      ]);
      if (!usersResp.ok) {
        const body = await usersResp.json().catch(() => ({}));
        setError(body.detail ?? "Incorrect username or password");
        return;
      }
      setUsers(await usersResp.json());
      setAnalyses(await analysesResp.json());
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const fmt$ = (n: number | null) =>
    n != null ? `$${(n / 1000).toFixed(0)}k` : "—";

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString() : "—";

  if (users === null) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-(--cream) px-4">
        <div className="bg-white rounded-2xl shadow-md p-8 w-full max-w-sm">
          <h1 className="text-xl font-semibold text-(--ink) mb-6">Admin Portal</h1>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label
                htmlFor="admin-username"
                className="block text-sm font-medium text-(--ink) mb-1"
              >
                Username
              </label>
              <input
                id="admin-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full border border-(--mist) rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-(--coral)"
              />
            </div>
            <div>
              <label
                htmlFor="admin-password"
                className="block text-sm font-medium text-(--ink) mb-1"
              >
                Password
              </label>
              <input
                id="admin-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full border border-(--mist) rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-(--coral)"
              />
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-(--coral) text-white font-medium rounded-lg py-2 text-sm disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-10">
      <h1 className="text-2xl font-semibold text-(--ink)">Admin Portal</h1>

      {/* Users table */}
      <section>
        <h2 className="text-lg font-medium text-(--ink) mb-3">
          Users ({users.length})
        </h2>
        <div className="overflow-x-auto rounded-xl border border-(--mist)">
          <table className="w-full text-sm">
            <thead className="bg-(--cream) text-(--ink) text-left">
              <tr>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Display Name</th>
                <th className="px-4 py-2 font-medium">Active</th>
                <th className="px-4 py-2 font-medium">Verified</th>
                <th className="px-4 py-2 font-medium">Superuser</th>
                <th className="px-4 py-2 font-medium">ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-(--mist)">
              {users.map((u) => (
                <tr key={u.id} className="bg-white">
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2 text-(--slate)">{u.display_name ?? "—"}</td>
                  <td className="px-4 py-2">{u.is_active ? "✓" : "✗"}</td>
                  <td className="px-4 py-2">{u.is_verified ? "✓" : "✗"}</td>
                  <td className="px-4 py-2">{u.is_superuser ? "✓" : "✗"}</td>
                  <td className="px-4 py-2 font-mono text-xs text-(--slate)">{u.id}</td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-4 text-center text-(--slate)">
                    No users yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Analyses table */}
      <section>
        <h2 className="text-lg font-medium text-(--ink) mb-3">
          Analyses ({analyses?.length ?? 0})
        </h2>
        <div className="overflow-x-auto rounded-xl border border-(--mist)">
          <table className="w-full text-sm">
            <thead className="bg-(--cream) text-(--ink) text-left">
              <tr>
                <th className="px-4 py-2 font-medium">ID</th>
                <th className="px-4 py-2 font-medium">Address</th>
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Low</th>
                <th className="px-4 py-2 font-medium">Recommended</th>
                <th className="px-4 py-2 font-medium">High</th>
                <th className="px-4 py-2 font-medium">Risk</th>
                <th className="px-4 py-2 font-medium">Rating</th>
                <th className="px-4 py-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-(--mist)">
              {(analyses ?? []).map((a) => (
                <tr key={a.id} className="bg-white">
                  <td className="px-4 py-2 font-mono text-xs">{a.id}</td>
                  <td className="px-4 py-2">{a.address ?? "—"}</td>
                  <td className="px-4 py-2 font-mono text-xs text-(--slate)">
                    {a.user_id ? (
                      a.user_id.slice(0, 8) + "…"
                    ) : (
                      <span className="text-amber-600">anon</span>
                    )}
                  </td>
                  <td className="px-4 py-2">{fmt$(a.offer_low)}</td>
                  <td className="px-4 py-2 font-medium">{fmt$(a.offer_recommended)}</td>
                  <td className="px-4 py-2">{fmt$(a.offer_high)}</td>
                  <td className="px-4 py-2">{a.risk_level ?? "—"}</td>
                  <td className="px-4 py-2">{a.investment_rating ?? "—"}</td>
                  <td className="px-4 py-2 text-(--slate)">{fmtDate(a.created_at)}</td>
                </tr>
              ))}
              {(analyses?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-4 text-center text-(--slate)">
                    No analyses yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
