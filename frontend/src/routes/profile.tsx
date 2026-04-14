import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../lib/AuthContext";
import { authHeaders, clearToken } from "../lib/auth";
import { apiBase } from "../lib/api";

export const Route = createFileRoute("/profile")({ component: ProfilePage });

export default function ProfilePage() {
  const { user, isLoading, logout } = useAuth();
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSubmitting, setPwSubmitting] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  // Redirect to login if not authenticated once loading is done.
  useEffect(() => {
    if (!isLoading && !user) {
      navigate({ to: "/login" });
    }
  }, [isLoading, user, navigate]);

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(false);
    setPwSubmitting(true);
    try {
      const resp = await fetch(`${apiBase}/api/users/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ password: newPassword }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to update password");
      }
      setNewPassword("");
      setPwSuccess(true);
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to update password");
    } finally {
      setPwSubmitting(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleteError(null);
    setDeleteSubmitting(true);
    try {
      const resp = await fetch(`${apiBase}/api/users/me`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!resp.ok) {
        throw new Error("Failed to delete account");
      }
      clearToken();
      logout();
      navigate({ to: "/" });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete account");
      setDeleteSubmitting(false);
    }
  }

  if (isLoading || !user) return null;

  return (
    <main className="page-wrap py-10">
      <div className="max-w-lg space-y-10">
        <h1 className="text-2xl font-bold text-[var(--ink)]">Profile</h1>

        {/* Account info */}
        <section className="space-y-2">
          <h2 className="text-base font-semibold text-[var(--ink)]">Account</h2>
          <p className="text-sm text-[var(--ink-soft)]">{user.email}</p>
        </section>

        {/* Change password */}
        <section className="space-y-4">
          <h2 className="text-base font-semibold text-[var(--ink)]">Change password</h2>

          {pwSuccess && (
            <p className="text-sm text-green-700">Password updated successfully.</p>
          )}
          {pwError && (
            <p role="alert" className="text-sm text-red-600">{pwError}</p>
          )}

          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium text-[var(--ink)] mb-1">
                New password
              </label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded border border-[var(--line)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus:ring-2 focus:ring-[var(--navy)]"
              />
            </div>
            <button
              type="submit"
              disabled={pwSubmitting}
              className="rounded bg-[var(--navy)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {pwSubmitting ? "Updating…" : "Update password"}
            </button>
          </form>
        </section>

        {/* Danger zone */}
        <section className="space-y-4 rounded border border-red-200 bg-red-50 p-4">
          <h2 className="text-base font-semibold text-red-700">Danger zone</h2>
          <p className="text-sm text-red-600">
            Deleting your account is permanent. Your saved analyses will be kept but become anonymous.
          </p>

          {deleteError && (
            <p role="alert" className="text-sm text-red-700">{deleteError}</p>
          )}

          {!showDeleteConfirm ? (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="rounded border border-red-400 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-100"
            >
              Delete account
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm font-semibold text-red-700">Are you sure? This cannot be undone.</p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleDeleteAccount}
                  disabled={deleteSubmitting}
                  className="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteSubmitting ? "Deleting…" : "Confirm delete"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  className="rounded border border-[var(--line)] px-4 py-2 text-sm text-[var(--ink-soft)] hover:text-[var(--ink)]"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
