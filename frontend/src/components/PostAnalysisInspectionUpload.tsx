import { useState, useRef } from "react";
import type { ChangeEvent } from "react";
import type { InspectionFindings } from "./InspectionReportCard";
import type { FixerAnalysisData } from "./FixerAnalysisCard";
import { apiBase } from "../lib/api";
import { authHeaders } from "../lib/auth";

interface Props {
  analysisId: number;
  sessionId?: string;
  onSuccess: (findings: InspectionFindings) => void;
  onRenovationUpdate?: (data: FixerAnalysisData) => void;
}

type UploadStatus = "idle" | "uploading" | "done" | "error";

export function PostAnalysisInspectionUpload({ analysisId, sessionId, onSuccess, onRenovationUpdate }: Props) {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [findings, setFindings] = useState<InspectionFindings | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus("uploading");
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);

    const headers: Record<string, string> = { ...authHeaders() };
    if (sessionId) headers["X-Session-ID"] = sessionId;

    try {
      const resp = await fetch(
        `${apiBase}/api/analyses/${analysisId}/inspection-report`,
        { method: "POST", body: formData, headers }
      );

      if (!resp.ok) {
        setUploadStatus("error");
        setUploadError("Could not parse the inspection report. Please check the file and try again.");
        return;
      }

      const body = await resp.json() as { findings: InspectionFindings; renovation_data: FixerAnalysisData | null };
      setFindings(body.findings);
      setUploadStatus("done");
      onSuccess(body.findings);
      if (body.renovation_data && onRenovationUpdate) {
        onRenovationUpdate(body.renovation_data);
      }
    } catch {
      setUploadStatus("error");
      setUploadError("Upload failed. Please try again.");
    }
  }

  if (uploadStatus === "done" && findings) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M20 6 9 17l-5-5" />
        </svg>
        <span>Report uploaded</span>
        {findings.systems.length > 0 && (
          <span className="text-blue-600">
            &middot; {findings.systems.filter(s => s.status !== "serviceable").length} issue(s) found
          </span>
        )}
      </div>
    );
  }

  if (uploadStatus === "uploading") {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-dashed border-[var(--card-border)] bg-gray-50 px-4 py-3 text-sm text-[var(--ink-muted)]">
        <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
        <span>Processing…</span>
      </div>
    );
  }

  return (
    <div>
      <label
        htmlFor={`post-inspection-report-${analysisId}`}
        className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-[var(--card-border)] bg-gray-50 px-4 py-4 text-center hover:bg-gray-100"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-1.5 text-[var(--ink-muted)]" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6M12 18v-6M9 15l3-3 3 3" />
        </svg>
        <span className="text-xs text-[var(--ink-muted)]">Upload PDF (max 10 MB)</span>
      </label>
      <input
        id={`post-inspection-report-${analysisId}`}
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        className="sr-only"
        aria-label="Upload inspection report"
      />
      {uploadStatus === "error" && uploadError && (
        <p className="mt-1.5 text-xs text-red-600">{uploadError}</p>
      )}
    </div>
  );
}
