import { useState, useRef } from "react";
import type { FormEvent, ChangeEvent } from "react";
import type { InspectionFindings } from "./InspectionReportCard";

interface Props {
  onSubmit: (address: string, buyerContext: string, inspectionFindings: InspectionFindings | null) => void;
  isRunning: boolean;
  rateLimitReached?: boolean;
}

type UploadStatus = "idle" | "uploading" | "done" | "error";

export function AnalysisForm({ onSubmit, isRunning, rateLimitReached = false }: Props) {
  const [address, setAddress] = useState("");
  const [buyerContext, setBuyerContext] = useState("");
  const [inspectionFindings, setInspectionFindings] = useState<InspectionFindings | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!address.trim() || isRunning || rateLimitReached) return;
    onSubmit(address.trim(), buyerContext.trim(), inspectionFindings);
  }

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus("uploading");
    setUploadError(null);
    setInspectionFindings(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const apiBase = import.meta.env.VITE_API_BASE ?? "";
      const resp = await fetch(`${apiBase}/api/upload/inspection-report`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        setUploadStatus("error");
        setUploadError("Could not parse the inspection report. Please check the file and try again.");
        return;
      }

      const findings = (await resp.json()) as InspectionFindings;
      setInspectionFindings(findings);
      setUploadStatus("done");
    } catch {
      setUploadStatus("error");
      setUploadError("Upload failed. Please try again.");
    }
  }

  function handleRemove() {
    setInspectionFindings(null);
    setUploadStatus("idle");
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="address"
          className="mb-1.5 block text-sm font-semibold text-[var(--ink)]"
        >
          Property address
        </label>
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-[var(--ink-muted)]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20 10c0 6-8 13-8 13S4 16 4 10a8 8 0 0 1 16 0Z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          </span>
          <input
            id="address"
            type="text"
            required
            placeholder="450 Sanchez St, San Francisco, CA 94114"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            disabled={isRunning}
            autoComplete="off"
            data-1p-ignore
            className="w-full rounded-xl border border-[var(--card-border)] bg-white py-3 pl-10 pr-4 text-sm shadow-sm placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
          />
        </div>
      </div>

      <div>
        <label
          htmlFor="buyer-context"
          className="mb-1.5 block text-sm font-semibold text-[var(--ink)]"
        >
          Buyer notes{" "}
          <span className="font-normal text-[var(--ink-muted)]">(optional)</span>
        </label>
        <textarea
          id="buyer-context"
          rows={2}
          placeholder="e.g. multiple offers expected, need to close in 30 days, flexible on repairs"
          value={buyerContext}
          onChange={(e) => setBuyerContext(e.target.value)}
          disabled={isRunning}
          className="w-full resize-none rounded-xl border border-[var(--card-border)] bg-white px-4 py-3 text-sm shadow-sm placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--coral)] disabled:opacity-50"
        />
      </div>

      {/* Inspection report upload */}
      <div>
        <label
          htmlFor="inspection-report"
          className="mb-1.5 block text-sm font-semibold text-[var(--ink)]"
        >
          Inspection report{" "}
          <span className="font-normal text-[var(--ink-muted)]">(optional)</span>
        </label>

        {uploadStatus === "done" && inspectionFindings ? (
          <div className="flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-blue-800">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M20 6 9 17l-5-5" />
              </svg>
              <span>Report uploaded</span>
              {inspectionFindings.systems.length > 0 && (
                <span className="text-blue-600">
                  &middot; {inspectionFindings.systems.filter(s => s.status !== "serviceable").length} issue(s) found
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleRemove}
              aria-label="Remove inspection report"
              className="ml-3 rounded-lg p-1 text-blue-600 hover:bg-blue-100 cursor-pointer"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
              <span className="sr-only">Remove</span>
            </button>
          </div>
        ) : uploadStatus === "uploading" ? (
          <div className="flex items-center gap-2 rounded-xl border border-dashed border-[var(--card-border)] bg-gray-50 px-4 py-3 text-sm text-[var(--ink-muted)]">
            <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            <span>Processing…</span>
          </div>
        ) : (
          <>
            <label
              htmlFor="inspection-report"
              className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-[var(--card-border)] bg-gray-50 px-4 py-4 text-center hover:bg-gray-100"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-1.5 text-[var(--ink-muted)]" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6M12 18v-6M9 15l3-3 3 3" />
              </svg>
              <span className="text-xs text-[var(--ink-muted)]">
                Upload PDF (max 10 MB)
              </span>
            </label>
            <input
              id="inspection-report"
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              disabled={isRunning}
              className="sr-only"
              aria-label="Inspection report"
            />
            {uploadStatus === "error" && uploadError && (
              <p className="mt-1.5 text-xs text-red-600">{uploadError}</p>
            )}
          </>
        )}
      </div>

      <button
        type="submit"
        disabled={isRunning || !address.trim() || rateLimitReached}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--coral)] px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[var(--coral-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {rateLimitReached ? (
          "Monthly limit reached"
        ) : isRunning ? (
          <>
            <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            Analyzing&hellip;
          </>
        ) : (
          <>
            Analyze listing
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </>
        )}
      </button>
    </form>
  );
}
