import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import { useToast } from "./Toast";
import { apiBase, apiClient } from "../lib/api";
import { authHeaders } from "../lib/auth";
import { useMutation } from "../hooks/useMutation";

const QUALITY_OPTIONS = [
  { value: "terrible", label: "Terrible" },
  { value: "bad", label: "Bad" },
  { value: "neutral", label: "Neutral" },
  { value: "good", label: "Good" },
  { value: "excellent", label: "Excellent" },
];

const LOCATION_OPTIONS = [
  { value: "bad", label: "Bad" },
  { value: "neutral", label: "Neutral" },
  { value: "good", label: "Good" },
];

interface SeenEntry {
  id: number;
  analysis_id: number | null;
  quality: string;
  location: string;
  composite_score: number;
  seen_at: string;
  notes: string | null;
}

interface Props {
  analysisId: number;
  address: string;
  onSeenEntry?: (compositeScore: number | null) => void;
  onChanged?: () => void;
}

export function MarkSeenButton({ analysisId, address, onSeenEntry, onChanged }: Props) {
  const { user } = useAuth();
  const toast = useToast();
  const [seenEntry, setSeenEntry] = useState<SeenEntry | null>(null);
  const [loadingState, setLoadingState] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [quality, setQuality] = useState("neutral");
  const [location, setLocation] = useState("neutral");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!user) {
      setLoadingState(false);
      return;
    }
    fetch(`${apiBase}/api/seen-properties?analysis_id=${analysisId}`, {
      headers: authHeaders(),
    })
      .then((r) => r.json())
      .then((data) => {
        const rows: SeenEntry[] = data.seen_properties ?? [];
        const entry = rows.length > 0 ? rows[0] : null;
        setSeenEntry(entry);
        onSeenEntry?.(entry?.composite_score ?? null);
      })
      .catch(() => {})
      .finally(() => setLoadingState(false));
  }, [analysisId, user]);

  const { mutate: submitMutation, loading: submitting } = useMutation(
    (formData: { quality: string; location: string; notes: string | null }) =>
      apiClient.markSeen(analysisId, formData.quality, formData.location, formData.notes),
    (result) => {
      setSeenEntry(result);
      onSeenEntry?.(result.composite_score);
      onChanged?.();
      setModalOpen(false);
      toast.success("Property marked as seen.");
    }
  );

  const { mutate: unmarkMutation } = useMutation(
    (_: null) => {
      if (!seenEntry) return Promise.reject(new Error("No seen entry to unmark"));
      return apiClient.unmarkSeen(seenEntry.id);
    },
    () => {
      setSeenEntry(null);
      onSeenEntry?.(null);
      onChanged?.();
      toast.success("Removed seen mark.");
    }
  );

  if (!user || loadingState) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await submitMutation({ quality, location, notes: notes.trim() || null });
    } catch (err) {
      if ((err as Error).message === "ALREADY_SEEN") {
        toast.error("Already marked as seen.");
      } else {
        toast.error("Failed to mark as seen.");
      }
    }
  }

  async function handleUnmark() {
    try {
      await unmarkMutation(null);
    } catch {
      toast.error("Failed to remove seen mark.");
    }
  }

  function openModal() {
    setQuality("neutral");
    setLocation("neutral");
    setNotes("");
    setModalOpen(true);
  }

  const scoreLabel =
    seenEntry
      ? `${seenEntry.quality} / ${seenEntry.location}`
      : null;

  return (
    <>
      {seenEntry ? (
        <button
          type="button"
          aria-label="Seen"
          onClick={handleUnmark}
          title={`Seen — Quality: ${seenEntry.quality}, Location: ${seenEntry.location}\nClick to unmark`}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-emerald-600 shadow-sm hover:bg-[var(--bg)] transition-colors"
        >
          <Eye size={12} />
          Seen
          {scoreLabel && (
            <span className="ml-0.5 text-[var(--ink-muted)] font-normal">
              ({scoreLabel})
            </span>
          )}
        </button>
      ) : (
        <button
          type="button"
          aria-label="Mark Seen"
          onClick={openModal}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--ink-muted)] shadow-sm hover:bg-[var(--bg)] transition-colors"
        >
          <EyeOff size={12} />
          Mark Seen
        </button>
      )}

      {modalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Rate this property"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModalOpen(false);
          }}
        >
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="mb-1 text-base font-bold text-[var(--ink)]">
              Mark as Seen
            </h2>
            <p className="mb-4 text-xs text-[var(--ink-muted)] leading-snug">
              {address}
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="quality-select"
                  className="mb-1 block text-xs font-semibold text-[var(--ink)]"
                >
                  Quality
                </label>
                <p className="mb-1.5 text-xs text-[var(--ink-muted)]">
                  Roof, foundation, fixtures, water damage, build quality…
                </p>
                <select
                  id="quality-select"
                  value={quality}
                  onChange={(e) => setQuality(e.target.value)}
                  className="w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--navy)]"
                >
                  {QUALITY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="location-select"
                  className="mb-1 block text-xs font-semibold text-[var(--ink)]"
                >
                  Location
                </label>
                <p className="mb-1.5 text-xs text-[var(--ink-muted)]">
                  Walkability, transit, noise, hills, surroundings…
                </p>
                <select
                  id="location-select"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--navy)]"
                >
                  {LOCATION_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="notes-input"
                  className="mb-1 block text-xs font-semibold text-[var(--ink)]"
                >
                  Notes{" "}
                  <span className="font-normal text-[var(--ink-muted)]">(optional)</span>
                </label>
                <input
                  id="notes-input"
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. loved the yard"
                  maxLength={500}
                  className="w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--navy)]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="cursor-pointer rounded-lg border border-[var(--line)] px-4 py-1.5 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--bg)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="cursor-pointer rounded-lg bg-[var(--navy)] px-4 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
                >
                  {submitting ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
