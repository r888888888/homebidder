export interface PropertyData {
  address_input?: string | null;
  address_matched: string;
  latitude: number;
  longitude: number;
  county: string;
  state: string;
  zip_code: string;
  unit?: string | null;
  price: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  year_built: number | null;
  lot_size: number | null;
  property_type: string | null;
  hoa_fee: number | null;
  days_on_market: number | null;
  list_date: string | null;
  city: string | null;
  neighborhoods: string | null;
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

function extractUnitToken(text: string | null | undefined): string | null {
  if (!text) return null;
  const m = text.match(
    /(?:#\s*([\w-]+)|\bunit\s+([\w-]+)|\bapt\.?\s+([\w-]+)|\bsuite\s+([\w-]+)|\bste\.?\s+([\w-]+))/i
  );
  if (!m) return null;
  for (const group of m.slice(1)) {
    if (group) return group;
  }
  return null;
}

function normalizeMatchedAddressWithUnit(
  addressInput: string | null | undefined,
  matchedAddress: string
): string {
  const unit = extractUnitToken(addressInput);
  if (!unit) return matchedAddress;
  if (extractUnitToken(matchedAddress)) return matchedAddress;

  const parts = matchedAddress.split(",");
  if (parts.length === 0) return matchedAddress;
  const street = parts[0].trim();
  const tail = parts.slice(1).map((p) => p.trim()).filter(Boolean);
  const withUnitStreet = `${street} UNIT ${unit}`;
  return tail.length > 0 ? `${withUnitStreet}, ${tail.join(", ")}` : withUnitStreet;
}

/**
 * Returns a human-friendly time-on-market string.
 * Uses list_date for sub-day precision; falls back to days_on_market.
 */
function domLabel(listDate: string | null, daysOnMarket: number | null): string {
  const fallback = (dom: number | null): string => {
    if (dom == null) return "—";
    return `${dom} day${dom === 1 ? "" : "s"}`;
  };

  if (!listDate) return fallback(daysOnMarket);

  // Parse as UTC (homeharvest timestamps are UTC)
  const listedAt = new Date(listDate.replace(" ", "T") + "Z");
  const ts = listedAt.getTime();
  if (!Number.isFinite(ts)) return fallback(daysOnMarket);

  const hoursAgo = (Date.now() - ts) / (1000 * 60 * 60);
  if (hoursAgo < 0) return fallback(daysOnMarket);

  const derivedDays = Math.floor(hoursAgo / 24);

  if (daysOnMarket != null) {
    // Guard against provider drift where list_date can be stale by years.
    const driftDays = Math.abs(derivedDays - daysOnMarket);
    if (driftDays > 14) return fallback(daysOnMarket);
  }

  if (hoursAgo < 1) return "< 1 hr";
  if (hoursAgo < 24) {
    const h = Math.floor(hoursAgo);
    return `${h} hr${h === 1 ? "" : "s"}`;
  }

  return `${derivedDays} day${derivedDays === 1 ? "" : "s"}`;
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
  const displayAddress = property.address_input?.trim() || property.address_matched;
  const matchedAddressDisplay = normalizeMatchedAddressWithUnit(
    property.address_input,
    property.address_matched
  );
  const hasDifferentMatchedAddress =
    !!property.address_input &&
    property.address_input.trim().toLowerCase() !== matchedAddressDisplay.trim().toLowerCase();

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

  const isCondo = /condo|townhome|townhouse/i.test(property.property_type ?? "");

  const coreFields: Field[] = [
    { label: "List Price", value: priceDisplay },
    { label: "AVM Estimate", value: avmDisplay },
    { label: "Beds", value: fmt(property.bedrooms) },
    { label: "Baths", value: fmt(property.bathrooms) },
    { label: "Sqft", value: property.sqft != null ? fmt(property.sqft) : "—" },
    { label: "Year Built", value: property.year_built ?? "—" },
    { label: "City", value: property.city ?? "—" },
    { label: "County", value: property.county || "—" },
    { label: "Type", value: formatPropertyType(property.property_type) },
    { label: "Days on Market", value: domLabel(property.list_date, property.days_on_market) },
  ];

  if (property.unit) {
    coreFields.splice(2, 0, { label: "Unit", value: property.unit });
  }

  if (!isCondo) {
    coreFields.splice(
      coreFields.findIndex((f) => f.label === "Year Built") + 1,
      0,
      { label: "Lot Size (sqft)", value: property.lot_size != null ? fmt(property.lot_size) : "—" }
    );
  }

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
          {displayAddress}
        </h2>
        {hasDifferentMatchedAddress && (
          <p className="mt-0.5 text-xs text-[var(--ink-soft)]">
            Matched as: {matchedAddressDisplay}
          </p>
        )}
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
