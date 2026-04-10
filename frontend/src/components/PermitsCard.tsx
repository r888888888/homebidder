export interface PermitRecord {
  permit_number: string;
  filed_date: string | null;
  issued_date: string | null;
  completed_date: string | null;
  status: string | null;
  permit_type: string | null;
  work_description: string | null;
  estimated_cost: number | null;
  address: string | null;
  unit: string | null;
  source_url: string | null;
  llm_summary?: string | null;
  llm_impact?: "positive" | "negative" | null;
}

export interface PermitsData {
  source: string;
  source_detail?: string | null;
  address: string | null;
  open_permits_count: number;
  recent_permits_5y: number;
  major_permits_10y: number;
  oldest_open_permit_age_days: number | null;
  permit_counts_by_type?: {
    electrical: number;
    plumbing: number;
    building: number;
  };
  complaints_open_count?: number;
  complaints_recent_3y?: number;
  flags: string[];
  permits: PermitRecord[];
  llm_overall_summary?: string | null;
  complaints?: Array<{
    complaint_number: string;
    date_filed: string | null;
    status: string | null;
    division: string | null;
    expired: string | null;
    address: string | null;
    source_url: string | null;
  }>;
}

function flagLabel(flag: string): string {
  if (flag === "open_over_365_days") return "Open permit older than 1 year";
  if (flag === "recent_structural_work")
    return "Major permit activity in last 10 years";
  if (flag === "recent_complaints") return "Recent complaint activity";
  if (flag === "no_recent_permit_history")
    return "No permit activity in last 5 years";
  return flag;
}

function sourceLabel(source: string): string {
  if (source === "dbi") return "Department of Building Inspection (DBI)";
  if (source === "none") return "No source available";
  return source;
}

function titleCase(raw: string | null | undefined): string {
  if (!raw) return "Permit";
  return raw
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function badgeToneForStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").toLowerCase();
  if (
    normalized.includes("complete") ||
    normalized.includes("closed") ||
    normalized.includes("final") ||
    normalized.includes("resolved")
  ) {
    return "border-emerald-300 bg-emerald-50 text-emerald-800";
  }
  if (
    normalized.includes("cancel") ||
    normalized.includes("expired") ||
    normalized.includes("void") ||
    normalized.includes("hold") ||
    normalized.includes("suspend")
  ) {
    return "border-rose-300 bg-rose-50 text-rose-800";
  }
  return "border-amber-300 bg-amber-50 text-amber-800";
}

function badgeToneForImpact(
  impact: "positive" | "negative" | null | undefined,
): string {
  if (impact === "positive")
    return "border-emerald-300 bg-emerald-50 text-emerald-800";
  if (impact === "negative") return "border-rose-300 bg-rose-50 text-rose-800";
  return "border-slate-300 bg-slate-50 text-slate-700";
}

function badgeBaseClass(tone: string): string {
  return `inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide ${tone}`;
}

interface Props {
  permits: PermitsData;
}

export function PermitsCard({ permits }: Props) {
  const topPermits = permits.permits.slice(0, 5);
  const topComplaints = (permits.complaints ?? []).slice(0, 5);

  return (
    <div className="card overflow-hidden fade-up">
      <div className="border-b border-[var(--line)] px-6 py-4">
        <p className="mb-0.5 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Permit History
        </p>
        <p className="text-xs text-[var(--ink-soft)]">
          San Francisco property history from {sourceLabel(permits.source)}
        </p>
        {permits.llm_overall_summary && (
          <p
            data-testid="permits-overall-summary"
            className="mt-2 text-sm text-[var(--ink)]"
          >
            {permits.llm_overall_summary}
          </p>
        )}
      </div>

      <div className="px-6 py-5">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Open Permits
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {permits.open_permits_count}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Permits (5y)
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {permits.recent_permits_5y}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Open Complaints
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {permits.complaints_open_count ?? 0}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Oldest Open
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {permits.oldest_open_permit_age_days != null
                ? `${permits.oldest_open_permit_age_days} days`
                : "—"}
            </dd>
          </div>
        </dl>

        {permits.permit_counts_by_type && (
          <p className="mt-3 text-xs text-[var(--ink-soft)]">
            Electrical {permits.permit_counts_by_type.electrical} · Plumbing{" "}
            {permits.permit_counts_by_type.plumbing} · Building{" "}
            {permits.permit_counts_by_type.building}
          </p>
        )}

        {permits.flags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {permits.flags.map((flag) => (
              <span
                key={flag}
                className="rounded-full border border-[var(--line)] bg-[var(--bg)] px-2.5 py-1 text-xs text-[var(--ink-soft)]"
              >
                {flagLabel(flag)}
              </span>
            ))}
          </div>
        )}
      </div>

      {topPermits.length > 0 && (
        <div className="border-t border-[var(--line)] px-6 py-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Permit Records
          </p>
          <ul className="space-y-3">
            {topPermits.map((permit) => (
              <li
                key={permit.permit_number}
                className="rounded-lg border border-[var(--line)] bg-[var(--bg)] p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--ink)]">
                    {permit.permit_number}
                    <span className="ml-2 text-xs font-normal text-[var(--ink-soft)]">
                      {`Filed ${permit.filed_date ?? "—"}`}
                    </span>
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {permit.llm_impact && (
                      <span
                        className={badgeBaseClass(
                          badgeToneForImpact(permit.llm_impact),
                        )}
                      >
                        {`Impact: ${permit.llm_impact}`}
                      </span>
                    )}
                    <span
                      className={badgeBaseClass(
                        badgeToneForStatus(permit.status),
                      )}
                    >
                      {`Status: ${String(permit.status ?? "unknown").toLowerCase()}`}
                    </span>
                  </div>
                </div>
                {permit.work_description && (
                  <p className="mt-1 text-xs text-[var(--ink-soft)]">
                    {permit.work_description}
                  </p>
                )}
                <p className="mt-1 text-xs text-[var(--ink-soft)]">
                  {permit.llm_summary ??
                    `${titleCase(permit.permit_type)} permit ${permit.permit_number} is ${(permit.status ?? "status unknown").toLowerCase()}.`}
                </p>
                {permit.source_url && (
                  <a
                    href={permit.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-flex text-xs font-semibold text-[var(--navy)] underline"
                  >
                    View permit
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {topComplaints.length > 0 && (
        <div className="border-t border-[var(--line)] px-6 py-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Complaints
          </p>
          <ul className="space-y-3">
            {topComplaints.map((complaint) => (
              <li
                key={complaint.complaint_number}
                className="rounded-lg border border-[var(--line)] bg-[var(--bg)] p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--ink)]">
                    {complaint.complaint_number}
                  </p>
                  <span
                    className={badgeBaseClass(
                      badgeToneForStatus(complaint.status),
                    )}
                  >
                    {`Status: ${String(complaint.status ?? "unknown").toLowerCase()}`}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--ink-soft)]">
                  Filed {complaint.date_filed ?? "—"} · Division{" "}
                  {complaint.division ?? "—"}
                </p>
                <p className="mt-1 text-xs text-[var(--ink-soft)]">
                  {`Complaint ${complaint.complaint_number} is ${(complaint.status ?? "status unknown").toLowerCase()}.`}
                </p>
                {complaint.source_url && (
                  <a
                    href={complaint.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-flex text-xs font-semibold text-[var(--navy)] underline"
                  >
                    View complaint
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
