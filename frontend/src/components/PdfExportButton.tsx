import { PDFDownloadLink } from "@react-pdf/renderer";
import { Link } from "@tanstack/react-router";
import { Download, Lock } from "lucide-react";
import { PdfReport } from "./PdfReport";
import type { AnalysisDetail } from "../routes/analysis_.$id";

function slugAddress(address: string): string {
  return address
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

interface Props {
  analysis: AnalysisDetail;
  isAgent: boolean;
}

export function PdfExportButton({ analysis, isAgent }: Props) {
  if (isAgent) {
    return (
      <PDFDownloadLink
        document={<PdfReport analysis={analysis} />}
        fileName={`homebidder-${slugAddress(analysis.address)}.pdf`}
        className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--card-border)] bg-white px-4 py-2 text-sm font-semibold text-[var(--ink)] shadow-sm hover:bg-[var(--bg)] no-underline"
      >
        {({ loading }) => (
          <>
            <Download size={14} aria-hidden="true" />
            {loading ? "Preparing PDF…" : "Download PDF"}
          </>
        )}
      </PDFDownloadLink>
    );
  }

  return (
    <Link
      to="/pricing"
      className="inline-flex items-center gap-1.5 rounded-xl border border-dashed border-[var(--card-border)] px-4 py-2 text-sm font-semibold text-[var(--ink-muted)] no-underline hover:bg-[var(--bg)]"
    >
      <Lock size={14} aria-hidden="true" />
      PDF Export — Agent plan
    </Link>
  );
}
