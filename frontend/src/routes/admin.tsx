import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/admin")({
  component: AdminPage,
});

const PAGE_SIZE = 25;

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
  user_email: string | null;
  offer_low: number | null;
  offer_high: number | null;
  offer_recommended: number | null;
  risk_level: string | null;
  investment_rating: string | null;
  created_at: string | null;
}

interface PagedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

function Pagination({
  page,
  pages,
  loading,
  onPage,
}: {
  page: number;
  pages: number;
  loading: boolean;
  onPage: (p: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <div className="flex items-center gap-3 mt-3 text-sm">
      <button
        onClick={() => onPage(page - 1)}
        disabled={page <= 1 || loading}
        className="px-3 py-1 rounded-lg border border-(--mist) disabled:opacity-40 hover:bg-(--cream) transition-colors"
      >
        ← Prev
      </button>
      <span className="text-(--slate)">
        Page {page} of {pages}
      </span>
      <button
        onClick={() => onPage(page + 1)}
        disabled={page >= pages || loading}
        className="px-3 py-1 rounded-lg border border-(--mist) disabled:opacity-40 hover:bg-(--cream) transition-colors"
      >
        Next →
      </button>
    </div>
  );
}

export function AdminPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);

  // Stored after first successful auth to re-use on page navigation
  const [authHeader, setAuthHeader] = useState<string | null>(null);

  const [usersData, setUsersData] = useState<PagedResult<AdminUser> | null>(null);
  const [analysesData, setAnalysesData] = useState<PagedResult<AdminAnalysis> | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [analysesLoading, setAnalysesLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError(null);
    setLoginLoading(true);
    const header = `Basic ${btoa(`${username}:${password}`)}`;
    try {
      const [usersResp, analysesResp] = await Promise.all([
        fetch(`${apiBase}/api/admin/users?page=1&page_size=${PAGE_SIZE}`, {
          headers: { Authorization: header },
        }),
        fetch(`${apiBase}/api/admin/analyses?page=1&page_size=${PAGE_SIZE}`, {
          headers: { Authorization: header },
        }),
      ]);
      if (!usersResp.ok) {
        const body = await usersResp.json().catch(() => ({}));
        setLoginError(body.detail ?? "Incorrect username or password");
        return;
      }
      setAuthHeader(header);
      setUsersData(await usersResp.json());
      setAnalysesData(await analysesResp.json());
    } catch {
      setLoginError("Network error. Please try again.");
    } finally {
      setLoginLoading(false);
    }
  }

  async function goUsersPage(page: number) {
    if (!authHeader) return;
    setUsersLoading(true);
    try {
      const resp = await fetch(
        `${apiBase}/api/admin/users?page=${page}&page_size=${PAGE_SIZE}`,
        { headers: { Authorization: authHeader } }
      );
      if (resp.ok) setUsersData(await resp.json());
    } finally {
      setUsersLoading(false);
    }
  }

  async function goAnalysesPage(page: number) {
    if (!authHeader) return;
    setAnalysesLoading(true);
    try {
      const resp = await fetch(
        `${apiBase}/api/admin/analyses?page=${page}&page_size=${PAGE_SIZE}`,
        { headers: { Authorization: authHeader } }
      );
      if (resp.ok) setAnalysesData(await resp.json());
    } finally {
      setAnalysesLoading(false);
    }
  }

  const fmt$ = (n: number | null) =>
    n != null ? `$${(n / 1000).toFixed(0)}k` : "—";

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString() : "—";

  // ── Login form ──────────────────────────────────────────────────────────
  if (usersData === null) {
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
            {loginError && <p className="text-red-600 text-sm">{loginError}</p>}
            <button
              type="submit"
              disabled={loginLoading}
              className="w-full bg-(--coral) text-white font-medium rounded-lg py-2 text-sm disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {loginLoading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </main>
    );
  }

  // ── Admin dashboard ──────────────────────────────────────────────────────
  const users = usersData.items;
  const analyses = analysesData?.items ?? [];

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-10">
      <h1 className="text-2xl font-semibold text-(--ink)">Admin Portal</h1>

      {/* ── Users table ── */}
      <section>
        <h2 className="text-lg font-medium text-(--ink) mb-3">
          Users ({usersData.total})
        </h2>
        <div className={`overflow-x-auto rounded-xl border border-(--mist) ${usersLoading ? "opacity-60" : ""}`}>
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
        <Pagination
          page={usersData.page}
          pages={usersData.pages}
          loading={usersLoading}
          onPage={goUsersPage}
        />
      </section>

      {/* ── Analyses table ── */}
      <section>
        <h2 className="text-lg font-medium text-(--ink) mb-3">
          Analyses ({analysesData?.total ?? 0})
        </h2>
        <div className={`overflow-x-auto rounded-xl border border-(--mist) ${analysesLoading ? "opacity-60" : ""}`}>
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
              {analyses.map((a) => (
                <tr key={a.id} className="bg-white">
                  <td className="px-4 py-2 font-mono text-xs">{a.id}</td>
                  <td className="px-4 py-2">{a.address ?? "—"}</td>
                  <td className="px-4 py-2">
                    {a.user_email ?? <span className="text-amber-600">anon</span>}
                  </td>
                  <td className="px-4 py-2">{fmt$(a.offer_low)}</td>
                  <td className="px-4 py-2 font-medium">{fmt$(a.offer_recommended)}</td>
                  <td className="px-4 py-2">{fmt$(a.offer_high)}</td>
                  <td className="px-4 py-2">{a.risk_level ?? "—"}</td>
                  <td className="px-4 py-2">{a.investment_rating ?? "—"}</td>
                  <td className="px-4 py-2 text-(--slate)">{fmtDate(a.created_at)}</td>
                </tr>
              ))}
              {analyses.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-4 text-center text-(--slate)">
                    No analyses yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {analysesData && (
          <Pagination
            page={analysesData.page}
            pages={analysesData.pages}
            loading={analysesLoading}
            onPage={goAnalysesPage}
          />
        )}
      </section>
    </main>
  );
}
