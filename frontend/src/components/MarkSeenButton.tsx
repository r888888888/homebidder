import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import { useToast } from "./Toast";
import { apiBase, apiClient } from "../lib/api";
import { authHeaders } from "../lib/auth";
import { useMutation } from "../hooks/useMutation";

type BiddingIntent = "yes" | "no";

interface SeenEntry {
  id: number;
  analysis_id: number | null;
  quality: string;
  location: string;
  composite_score: number;
  bidding_intent: BiddingIntent | null;
  seen_at: string;
  notes: string | null;
}

interface Props {
  analysisId: number;
  address: string;
  onSeenEntry?: (intent: BiddingIntent | null) => void;
  onChanged?: () => void;
}

export function MarkSeenButton({ analysisId, address, onSeenEntry, onChanged }: Props) {
  const { user } = useAuth();
  const toast = useToast();
  const [seenEntry, setSeenEntry] = useState<SeenEntry | null>(null);
  const [loadingState, setLoadingState] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [biddingIntent, setBiddingIntent] = useState<BiddingIntent | "">("");
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
        onSeenEntry?.(entry?.bidding_intent ?? null);
      })
      .catch(() => {})
      .finally(() => setLoadingState(false));
  }, [analysisId, user]);

  const { mutate: submitMutation, loading: submitting } = useMutation(
    (formData: { biddingIntent: BiddingIntent; notes: string | null }) =>
      apiClient.markSeen(analysisId, formData.biddingIntent, formData.notes),
    (result) => {
      setSeenEntry(result);
      onSeenEntry?.(result.bidding_intent);
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
    if (biddingIntent === "") {
      toast.error("Please choose Yes or No.");
      return;
    }
    try {
      await submitMutation({ biddingIntent, notes: notes.trim() || null });
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
    setBiddingIntent("");
    setNotes("");
    setModalOpen(true);
  }

  const intentLabel =
    seenEntry?.bidding_intent === "yes"
      ? "Would bid"
      : seenEntry?.bidding_intent === "no"
        ? "Skip"
        : null;

  return (
    <>
      {seenEntry ? (
        <button
          type="button"
          aria-label="Seen"
          onClick={handleUnmark}
          title={
            intentLabel
              ? `Seen — ${intentLabel}\nClick to unmark`
              : "Seen\nClick to unmark"
          }
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-white px-3 py-1.5 text-xs font-semibold text-emerald-600 shadow-sm hover:bg-[var(--bg)] transition-colors"
        >
          <Eye size={12} />
          Seen
          {intentLabel && (
            <span className="ml-0.5 text-[var(--ink-muted)] font-normal">
              ({intentLabel})
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
          aria-label="Mark this property as seen"
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
              <fieldset>
                <legend className="mb-1 block text-xs font-semibold text-[var(--ink)]">
                  Would you make an offer on this property?
                </legend>
                <p className="mb-2 text-xs text-[var(--ink-muted)]">
                  Your overall judgment — would you actually bid?
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <label
                    className={[
                      "cursor-pointer rounded-lg border px-3 py-2 text-center text-sm font-semibold transition-colors",
                      biddingIntent === "yes"
                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                        : "border-[var(--line)] bg-white text-[var(--ink-muted)] hover:bg-[var(--bg)]",
                    ].join(" ")}
                  >
                    <input
                      type="radio"
                      name="bidding-intent"
                      value="yes"
                      checked={biddingIntent === "yes"}
                      onChange={() => setBiddingIntent("yes")}
                      className="sr-only"
                    />
                    Yes — I'd bid
                  </label>
                  <label
                    className={[
                      "cursor-pointer rounded-lg border px-3 py-2 text-center text-sm font-semibold transition-colors",
                      biddingIntent === "no"
                        ? "border-[var(--ink)] bg-[var(--bg)] text-[var(--ink)]"
                        : "border-[var(--line)] bg-white text-[var(--ink-muted)] hover:bg-[var(--bg)]",
                    ].join(" ")}
                  >
                    <input
                      type="radio"
                      name="bidding-intent"
                      value="no"
                      checked={biddingIntent === "no"}
                      onChange={() => setBiddingIntent("no")}
                      className="sr-only"
                    />
                    No — skip
                  </label>
                </div>
              </fieldset>

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
