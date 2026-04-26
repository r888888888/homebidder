import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { apiBase } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import { authHeaders } from "../lib/auth";

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
  const { user, isLoading } = useAuth();

  const [usersData, setUsersData] = useState<PagedResult<AdminUser> | null>(null);
  const [analysesData, setAnalysesData] = useState<PagedResult<AdminAnalysis> | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [analysesLoading, setAnalysesLoading] = useState(false);

  // Load data automatically once we know the user is a superuser.
  useEffect(() => {
    if (!user?.is_superuser) return;
    async function load() {
      setUsersLoading(true);
      setAnalysesLoading(true);
      try {
        const [usersResp, analysesResp] = await Promise.all([
          fetch(`${apiBase}/api/admin/users?page=1&page_size=${PAGE_SIZE}`, {
            headers: authHeaders(),
          }),
          fetch(`${apiBase}/api/admin/analyses?page=1&page_size=${PAGE_SIZE}`, {
            headers: authHeaders(),
          }),
        ]);
        if (usersResp.ok) setUsersData(await usersResp.json());
        if (analysesResp.ok) setAnalysesData(await analysesResp.json());
      } finally {
        setUsersLoading(false);
        setAnalysesLoading(false);
      }
    }
    load();
  }, [user]);

  async function goUsersPage(page: number) {
    setUsersLoading(true);
    try {
      const resp = await fetch(
        `${apiBase}/api/admin/users?page=${page}&page_size=${PAGE_SIZE}`,
        { headers: authHeaders() }
      );
      if (resp.ok) setUsersData(await resp.json());
    } finally {
      setUsersLoading(false);
    }
  }

  async function goAnalysesPage(page: number) {
    setAnalysesLoading(true);
    try {
      const resp = await fetch(
        `${apiBase}/api/admin/analyses?page=${page}&page_size=${PAGE_SIZE}`,
        { headers: authHeaders() }
      );
      if (resp.ok) setAnalysesData(await resp.json());
    } finally {
      setAnalysesLoading(false);
    }
  }

  const fmt$ = (n: number | null) => {
    if (n == null) return "—";
    if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
    return `$${(n / 1000).toFixed(0)}k`;
  };

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString() : "—";

  // ── Auth check ───────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-(--cream)">
        <p className="text-(--slate)">Loading…</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-(--cream) px-4">
        <div className="bg-white rounded-2xl shadow-md p-8 w-full max-w-sm text-center">
          <h1 className="text-xl font-semibold text-(--ink) mb-3">Admin Portal</h1>
          <p className="text-(--slate) text-sm">Please log in to access the admin portal.</p>
        </div>
      </main>
    );
  }

  if (!user.is_superuser) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-(--cream) px-4">
        <div className="bg-white rounded-2xl shadow-md p-8 w-full max-w-sm text-center">
          <h1 className="text-xl font-semibold text-(--ink) mb-3">Admin Portal</h1>
          <p className="text-red-600 text-sm">Access denied. Superuser account required.</p>
        </div>
      </main>
    );
  }

  // ── Admin dashboard ──────────────────────────────────────────────────────
  const users = usersData?.items ?? [];
  const analyses = analysesData?.items ?? [];

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-10">
      <h1 className="text-2xl font-semibold text-(--ink)">Admin Portal</h1>

      {/* ── Users table ── */}
      <section>
        <h2 className="text-lg font-medium text-(--ink) mb-3">
          Users ({usersData?.total ?? 0})
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
        {usersData && (
          <Pagination
            page={usersData.page}
            pages={usersData.pages}
            loading={usersLoading}
            onPage={goUsersPage}
          />
        )}
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
                <th className="px-4 py-2 font-medium">Recommended</th>
                <th className="px-4 py-2 font-medium">Risk</th>
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
                  <td className="px-4 py-2 font-medium">{fmt$(a.offer_recommended)}</td>
                  <td className="px-4 py-2">{a.risk_level ?? "—"}</td>
                  <td className="px-4 py-2 text-(--slate)">{fmtDate(a.created_at)}</td>
                </tr>
              ))}
              {analyses.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-4 text-center text-(--slate)">
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
