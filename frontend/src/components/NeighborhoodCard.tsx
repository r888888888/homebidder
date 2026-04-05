export interface NeighborhoodData {
  median_home_value: number | null;
  housing_units: number | null;
  vacancy_rate: number | null;
  median_year_built: number | null;
}

function fmtUsd(n: number): string {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US");
}

interface Props {
  neighborhood: NeighborhoodData;
  neighborhoodName?: string | null;
}

export function NeighborhoodCard({ neighborhood, neighborhoodName }: Props) {
  return (
    <div className="card overflow-hidden fade-up">
      {/* Header */}
      <div className="border-b border-[var(--line)] px-6 py-4">
        <p className="mb-0.5 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Neighborhood
        </p>
        {neighborhoodName && (
          <p className="text-sm font-medium text-[var(--ink)]">{neighborhoodName}</p>
        )}
      </div>

      {/* Stats grid */}
      <div className="px-6 py-5">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Median Home Value
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {neighborhood.median_home_value != null
                ? fmtUsd(neighborhood.median_home_value)
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Housing Units
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {fmt(neighborhood.housing_units)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Vacancy Rate
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {neighborhood.vacancy_rate != null
                ? `${neighborhood.vacancy_rate}%`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Median Year Built
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">
              {neighborhood.median_year_built ?? "—"}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
