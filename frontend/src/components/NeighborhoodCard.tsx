const CA_TAX_RATE = 0.0125;

export interface NeighborhoodData {
  median_home_value: number | null;
  housing_units: number | null;
  vacancy_rate: number | null;
  median_year_built: number | null;
  prop13_assessed_value: number | null;
  prop13_base_year: number | null;
  prop13_annual_tax: number | null;
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

type TaxAlert = "amber" | "red" | null;

function taxAlert(sellerTax: number, buyerTax: number): TaxAlert {
  const delta = buyerTax - sellerTax;
  if (delta > 10_000) return "red";
  if (delta > 5_000) return "amber";
  return null;
}

interface Props {
  neighborhood: NeighborhoodData;
  purchasePrice: number | null;
  neighborhoodName?: string | null;
}

const ALERT_COLORS: Record<string, string> = {
  amber: "text-amber-600",
  red: "text-[var(--coral)]",
};

export function NeighborhoodCard({ neighborhood, purchasePrice, neighborhoodName }: Props) {
  const hasProp13 = neighborhood.prop13_assessed_value != null;
  const buyerAnnualTax =
    purchasePrice != null ? Math.round(purchasePrice * CA_TAX_RATE) : null;
  const alert =
    hasProp13 && neighborhood.prop13_annual_tax != null && buyerAnnualTax != null
      ? taxAlert(neighborhood.prop13_annual_tax, buyerAnnualTax)
      : null;

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

      {/* Prop 13 panel */}
      {hasProp13 && (
        <div className="border-t border-[var(--line)] px-6 py-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Prop 13 Tax Impact
          </p>
          <div
            className="rounded-xl border border-[var(--line)] bg-[var(--bg)] p-4"
            data-tax-alert={alert ?? undefined}
          >
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-[var(--ink-muted)]">Seller's est. annual tax</dt>
                <dd className="mt-0.5 text-sm font-semibold text-[var(--ink)]">
                  {neighborhood.prop13_annual_tax != null
                    ? fmtUsd(neighborhood.prop13_annual_tax)
                    : "—"}
                </dd>
                {neighborhood.prop13_base_year && (
                  <p className="mt-0.5 text-xs text-[var(--ink-soft)]">
                    Prop 13 basis since {neighborhood.prop13_base_year}
                  </p>
                )}
              </div>
              <div>
                <dt className="text-xs text-[var(--ink-muted)]">Your est. annual tax</dt>
                <dd className="mt-0.5 text-sm font-semibold text-[var(--ink)]">
                  {buyerAnnualTax != null ? fmtUsd(buyerAnnualTax) : "—"}
                </dd>
                <p className="mt-0.5 text-xs text-[var(--ink-soft)]">at purchase price × 1.25%</p>
              </div>
              {alert && buyerAnnualTax != null && neighborhood.prop13_annual_tax != null && (
                <div>
                  <dt className="text-xs text-[var(--ink-muted)]">Annual increase</dt>
                  <dd
                    className={`mt-0.5 text-sm font-semibold ${ALERT_COLORS[alert]}`}
                  >
                    +{fmtUsd(buyerAnnualTax - neighborhood.prop13_annual_tax)}/yr
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
