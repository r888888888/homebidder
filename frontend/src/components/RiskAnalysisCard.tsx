export interface RiskFactor {
  name: string;
  level: "low" | "moderate" | "high" | "n/a";
  description: string;
}

export interface RiskData {
  overall_risk: "Low" | "Moderate" | "High" | "Very High";
  score: number;
  factors: RiskFactor[];
  ces_census_tract?: string | null;
}

const CES_FACTOR_NAMES = new Set([
  "highway_proximity",
  "air_quality",
  "environmental_contamination",
]);

// Human-readable labels for each factor key
const FACTOR_LABELS: Record<string, string> = {
  alquist_priolo_fault_zone: "Fault Zone (Alquist-Priolo)",
  flood_zone: "Flood Zone (FEMA)",
  fire_hazard_zone: "Fire Hazard Zone (CalFire)",
  liquefaction_risk: "Liquefaction Risk",
  home_age: "Home Age",
  days_on_market: "Days on Market",
  hpi_trend: "Home Price Trend (FHFA HPI)",
  highway_proximity: "Highway Proximity (CalEnviroScreen)",
  air_quality: "Air Quality / PM2.5 (CalEnviroScreen)",
  environmental_contamination: "Environmental Contamination (CalEnviroScreen)",
};

const OVERALL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  Low:       { bg: "bg-emerald-50",  text: "text-emerald-700",  border: "border-emerald-200" },
  Moderate:  { bg: "bg-amber-50",    text: "text-amber-700",    border: "border-amber-200"   },
  High:      { bg: "bg-orange-50",   text: "text-orange-700",   border: "border-orange-200"  },
  "Very High": { bg: "bg-red-50",    text: "text-[var(--coral)]", border: "border-red-200"   },
};

const FACTOR_LEVEL_STYLES: Record<string, string> = {
  low:      "bg-emerald-50 text-emerald-700",
  moderate: "bg-amber-50 text-amber-700",
  high:     "bg-red-50 text-[var(--coral)]",
  "n/a":    "bg-[var(--bg)] text-[var(--ink-muted)]",
};

const CES_MAP_BASE_URL =
  "https://oehha.maps.arcgis.com/apps/webappviewer/index.html?id=d4c4071cf25042aea60799a8b144ad8a&find=";

interface Props {
  risk: RiskData;
}

export function RiskAnalysisCard({ risk }: Props) {
  const overall = OVERALL_STYLES[risk.overall_risk] ?? OVERALL_STYLES["Moderate"];

  // Separate active risk factors from n/a ones so n/a sits at the bottom
  const active = risk.factors.filter((f) => f.level !== "n/a");
  const inactive = risk.factors.filter((f) => f.level === "n/a");
  const ordered = [...active, ...inactive];

  return (
    <div className="card overflow-hidden fade-up">
      {/* Header */}
      <div className="border-b border-[var(--line)] px-6 py-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Risk Assessment
        </p>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold ${overall.bg} ${overall.text} ${overall.border}`}
            data-level={risk.overall_risk}
          >
            {risk.overall_risk}
          </span>
          <span className="text-xs text-[var(--ink-muted)]">
            Overall Risk
          </span>
        </div>
      </div>

      {/* Factor list */}
      <div className="divide-y divide-[var(--line)]">
        {ordered.map((factor) => {
          const label = FACTOR_LABELS[factor.name] ?? factor.name;
          const levelStyle = FACTOR_LEVEL_STYLES[factor.level] ?? FACTOR_LEVEL_STYLES["n/a"];
          const cesLink =
            CES_FACTOR_NAMES.has(factor.name) && risk.ces_census_tract
              ? `${CES_MAP_BASE_URL}${risk.ces_census_tract}`
              : null;

          return (
            <div key={factor.name} className="flex items-start gap-4 px-6 py-4">
              <div className="mt-0.5 w-28 shrink-0">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${levelStyle}`}
                  data-level={factor.level}
                >
                  {factor.level === "n/a" ? "N/A" : factor.level.charAt(0).toUpperCase() + factor.level.slice(1)}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--ink)]">
                  {label}
                  {cesLink && (
                    <a
                      href={cesLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 text-xs font-normal text-[var(--ink-muted)] hover:underline"
                    >
                      CalEnviroScreen ↗
                    </a>
                  )}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-[var(--ink-soft)]">
                  {factor.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
