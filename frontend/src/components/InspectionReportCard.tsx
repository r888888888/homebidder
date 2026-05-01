export interface InspectionSystem {
  name: string;
  status: "serviceable" | "deficient" | "safety_hazard";
  severity: "low" | "moderate" | "high";
  findings: string;
  renovation_category: string;
}

export interface InspectionFindings {
  property_address: string;
  inspector: string;
  inspection_date: string;
  systems: InspectionSystem[];
  summary: string;
}

interface Props {
  data: InspectionFindings;
}

function SeverityBadge({ status, severity }: { status: InspectionSystem["status"]; severity: InspectionSystem["severity"] }) {
  if (status === "serviceable") {
    return (
      <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">
        Serviceable
      </span>
    );
  }
  if (severity === "high" || status === "safety_hazard") {
    return (
      <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">
        High
      </span>
    );
  }
  if (severity === "moderate") {
    return (
      <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800">
        Moderate
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700">
      Low
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso + "T12:00:00").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function InspectionReportCard({ data }: Props) {
  const deficientCount = data.systems.filter(
    (s) => s.status !== "serviceable"
  ).length;

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gray-50">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">
            Inspection Report
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {data.inspector} &middot; {formatDate(data.inspection_date)}
          </p>
        </div>
        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
          {deficientCount === 0
            ? "No deficiencies"
            : `${deficientCount} ${deficientCount === 1 ? "deficiency" : "deficiencies"}`}
        </span>
      </div>

      {/* Systems list */}
      <ul className="divide-y divide-gray-100">
        {data.systems.map((system, i) => (
          <li key={i} className="px-5 py-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-medium text-gray-800 leading-snug">
                {system.name}
              </span>
              <SeverityBadge status={system.status} severity={system.severity} />
            </div>
            {system.findings && system.status !== "serviceable" && (
              <p className="mt-1 text-xs text-gray-600 leading-relaxed">
                {system.findings}
              </p>
            )}
          </li>
        ))}
      </ul>

      {/* Summary */}
      {data.summary && (
        <div className="px-5 py-3 bg-gray-50 border-t border-gray-100">
          <p className="text-xs text-gray-600">{data.summary}</p>
        </div>
      )}
    </div>
  );
}
