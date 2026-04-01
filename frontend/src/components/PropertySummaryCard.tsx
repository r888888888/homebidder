export interface PropertyData {
  address_matched: string;
  latitude: number;
  longitude: number;
  county: string;
  state: string;
  zip_code: string;
  price: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  year_built: number | null;
  lot_size: number | null;
  property_type: string | null;
  hoa_fee: number | null;
  days_on_market: number | null;
  price_history: unknown[];
  avm_estimate: number | null;
  source: string;
}

function fmt(n: number | null | undefined, opts?: Intl.NumberFormatOptions): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", opts);
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function formatPropertyType(raw: string | null | undefined): string {
  if (!raw) return "—";
  return raw
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function avmDelta(price: number | null, avm: number | null): string | null {
  if (price == null || avm == null) return null;
  const pct = ((avm - price) / price) * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

interface Field {
  label: string;
  value: React.ReactNode;
}

function FieldGrid({ fields }: { fields: Field[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
      {fields.map(({ label, value }) => (
        <div key={label}>
          <dt className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            {label}
          </dt>
          <dd className="mt-0.5 text-sm font-medium text-[var(--ink)]">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

interface Props {
  property: PropertyData;
}

export function PropertySummaryCard({ property }: Props) {
  const delta = avmDelta(property.price, property.avm_estimate);

  const priceDisplay = property.price != null ? fmtUsd(property.price) : "not listed";

  const avmDisplay =
    property.avm_estimate != null ? (
      <span>
        {fmtUsd(property.avm_estimate)}
        {delta && (
          <span
            className={`ml-1.5 text-xs font-semibold ${
              delta.startsWith("+") ? "text-[var(--green)]" : "text-[var(--coral)]"
            }`}
          >
            {delta}
          </span>
        )}
      </span>
    ) : (
      "N/A"
    );

  const coreFields: Field[] = [
    { label: "List Price", value: priceDisplay },
    { label: "AVM Estimate", value: avmDisplay },
    { label: "Beds", value: fmt(property.bedrooms) },
    { label: "Baths", value: fmt(property.bathrooms) },
    { label: "Sqft", value: property.sqft != null ? fmt(property.sqft) : "—" },
    { label: "Year Built", value: property.year_built ?? "—" },
    { label: "Lot Size (sqft)", value: property.lot_size != null ? fmt(property.lot_size) : "—" },
    { label: "Type", value: formatPropertyType(property.property_type) },
    { label: "Days on Market", value: fmt(property.days_on_market) },
  ];

  if (property.hoa_fee != null) {
    coreFields.push({ label: "HOA / mo", value: fmtUsd(property.hoa_fee) });
  }

  return (
    <div className="card overflow-hidden fade-up">
      <div className="border-b border-[var(--line)] px-6 py-4">
        <p className="mb-0.5 text-xs font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Property Summary
        </p>
        <h2 className="display-title text-base font-semibold text-[var(--ink)]">
          {property.address_matched}
        </h2>
        <p className="mt-0.5 text-xs text-[var(--ink-soft)]">
          {property.county} County &middot; {property.state} {property.zip_code}
          {" \u00b7 "}
          <span className="capitalize">{property.source}</span>
        </p>
      </div>

      <div className="px-6 py-5">
        <FieldGrid fields={coreFields} />
      </div>
    </div>
  );
}
