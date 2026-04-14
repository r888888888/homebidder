import { useState, useEffect } from "react";

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
  listing_description?: string | null;
  description_signals?: {
    version?: string;
    raw_description_present?: boolean;
    detected_signals?: Array<{
      label?: string;
      category?: string;
      direction?: string;
      weight_pct?: number;
      matched_phrases?: string[];
    }>;
    net_adjustment_pct?: number;
    llm?: {
      used?: boolean;
      confidence?: number | null;
      model?: string | null;
      adjustment_pct?: number;
    } | null;
  } | null;
  price_history: unknown[];
  avm_estimate: number | null;
  listing_url?: string | null;
  photos?: string[] | null;
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

function zillowUrl(p: PropertyData): string {
  const slug = p.address_matched
    .toLowerCase()
    .replace(/,/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
  return `https://www.zillow.com/homes/${slug}_rb/`;
}

function redfinUrl(p: PropertyData): string {
  return `https://www.redfin.com/zipcode/${p.zip_code}/homes-for-sale`;
}

function toTitleCase(s: string): string {
  return s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function realtorUrl(p: PropertyData): string {
  if (p.listing_url) return p.listing_url;
  const street = toTitleCase(p.address_matched.split(",")[0].trim()).replace(/\s+/g, "-");
  const city = (p.city ?? "").replace(/\s+/g, "-");
  return `https://www.realtor.com/realestateandhomes-detail/${street}_${city}_${p.state}_${p.zip_code}/`;
}

function streetViewUrl(p: PropertyData): string {
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${p.latitude},${p.longitude}`;
}

function googleMapsUrl(p: PropertyData): string {
  return `https://www.google.com/maps/search/?api=1&query=${p.latitude},${p.longitude}`;
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
  const [descExpanded, setDescExpanded] = useState(false);
  const [galleryExpanded, setGalleryExpanded] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  useEffect(() => {
    if (lightboxIndex === null) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxIndex(null);
      if (e.key === "ArrowRight")
        setLightboxIndex((i) => (i !== null && property.photos ? Math.min(i + 1, property.photos.length - 1) : i));
      if (e.key === "ArrowLeft")
        setLightboxIndex((i) => (i !== null ? Math.max(i - 1, 0) : i));
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [lightboxIndex, property.photos]);
  const displayAddress = property.address_input?.trim() || property.address_matched;
  const matchedAddressDisplay = normalizeMatchedAddressWithUnit(
    property.address_input,
    property.address_matched
  );
  const hasDifferentMatchedAddress =
    !!property.address_input &&
    property.address_input.trim().toLowerCase() !== matchedAddressDisplay.trim().toLowerCase();

  const priceDisplay = property.price != null ? fmtUsd(property.price) : "—";

  const isCondo = /condo|townhome|townhouse/i.test(property.property_type ?? "");
  const descriptionSignals = property.description_signals?.detected_signals ?? [];
  const llm = property.description_signals?.llm;
  const llmAdjustment = llm?.adjustment_pct ?? 0;
  const llmBadgeLabel =
    llm?.used && llmAdjustment !== 0
      ? llmAdjustment < 0
        ? "AI: Fixer"
        : "AI: Move-in Ready"
      : null;

  const coreFields: Field[] = [
    { label: property.source === "homeharvest_sold" ? "Last Sold Price" : "List Price", value: priceDisplay },
    { label: "HOA / mo", value: fmtUsd(property.hoa_fee) },
    { label: "Beds", value: fmt(property.bedrooms) },
    { label: "Baths", value: fmt(property.bathrooms) },
    { label: "Type", value: formatPropertyType(property.property_type) },
    { label: "Sqft", value: property.sqft != null ? fmt(property.sqft) : "—" },
    ...(!isCondo
      ? [
          {
            label: "Lot Size (sqft)",
            value: property.lot_size != null ? fmt(property.lot_size) : "—",
          },
        ]
      : []),
    { label: "Year Built", value: property.year_built ?? "—" },
    { label: "City", value: property.city ?? "—" },
    { label: "County", value: property.county || "—" },
    { label: "Days on Market", value: domLabel(property.list_date, property.days_on_market) },
  ];

  if (property.unit) {
    const typeIndex = coreFields.findIndex((f) => f.label === "Type");
    coreFields.splice(typeIndex + 1, 0, { label: "Unit", value: property.unit });
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
          <span className="capitalize">
            {property.source === "homeharvest_sold" ? "Recent Sale" : property.source}
          </span>
        </p>
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
          {[
            { label: "Zillow", href: zillowUrl(property) },
            { label: "Redfin", href: redfinUrl(property) },
            { label: "Realtor", href: realtorUrl(property) },
            { label: "Google Maps", href: googleMapsUrl(property) },
            { label: "Street View", href: streetViewUrl(property) },
          ].map(({ label, href }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-[var(--navy)] hover:underline"
            >
              {label} ↗
            </a>
          ))}
        </div>
        {property.photos && property.photos.length > 0 && (() => {
          const allPhotos = property.photos!;
          const visiblePhotos = galleryExpanded ? allPhotos : allPhotos.slice(0, 6);
          const hasMore = allPhotos.length > 6;
          return (
            <div className="mt-3">
              <div className="grid grid-cols-3 gap-1 sm:grid-cols-4">
                {visiblePhotos.map((url, i) => (
                  <button
                    key={i}
                    type="button"
                    aria-label={`Property photo ${i + 1}`}
                    onClick={() => setLightboxIndex(i)}
                    className="group relative overflow-hidden rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--navy)]"
                  >
                    <img
                      src={url}
                      alt={`Property photo ${i + 1}`}
                      className="h-20 w-full object-cover transition-transform duration-200 group-hover:scale-105"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors duration-200 group-hover:bg-black/20">
                      <svg className="h-5 w-5 text-white opacity-0 drop-shadow transition-opacity duration-200 group-hover:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0zM11 8v6M8 11h6" />
                      </svg>
                    </div>
                  </button>
                ))}
              </div>
              {hasMore && (
                <button
                  type="button"
                  onClick={() => setGalleryExpanded((v) => !v)}
                  className="mt-1 text-[11px] text-[var(--navy)] hover:underline"
                >
                  {galleryExpanded
                    ? "Show fewer photos"
                    : `Show all ${allPhotos.length} photos`}
                </button>
              )}
            </div>
          );
        })()}
        {lightboxIndex !== null && property.photos && (() => {
          const photos = property.photos!;
          const idx = lightboxIndex;
          return (
            <div
              role="dialog"
              aria-label="Photo lightbox"
              aria-modal="true"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/85"
              onClick={() => setLightboxIndex(null)}
            >
              <button
                type="button"
                aria-label="Close"
                onClick={() => setLightboxIndex(null)}
                className="absolute right-4 top-4 rounded-full bg-black/50 p-2 text-white hover:bg-black/70 focus:outline-none"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              {idx > 0 && (
                <button
                  type="button"
                  aria-label="Previous photo"
                  onClick={(e) => { e.stopPropagation(); setLightboxIndex(idx - 1); }}
                  className="absolute left-4 rounded-full bg-black/50 p-2 text-white hover:bg-black/70 focus:outline-none"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
              )}
              <img
                src={photos[idx]}
                alt={`Property photo ${idx + 1}`}
                className="max-h-[85vh] max-w-[90vw] rounded object-contain shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              />
              {idx < photos.length - 1 && (
                <button
                  type="button"
                  aria-label="Next photo"
                  onClick={(e) => { e.stopPropagation(); setLightboxIndex(idx + 1); }}
                  className="absolute right-4 rounded-full bg-black/50 p-2 text-white hover:bg-black/70 focus:outline-none"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              )}
              <div className="absolute bottom-4 text-sm text-white/70">
                {idx + 1} / {photos.length}
              </div>
            </div>
          );
        })()}
        {property.listing_description && (() => {
          const isLong = property.listing_description.length > 180;
          return (
            <div className="mt-2">
              <p className={`text-xs text-[var(--ink-soft)] leading-relaxed${!descExpanded && isLong ? " line-clamp-3" : ""}`}>
                {property.listing_description}
              </p>
              {isLong && (
                <button
                  type="button"
                  onClick={() => setDescExpanded((v) => !v)}
                  className="mt-0.5 text-[11px] text-[var(--navy)] hover:underline"
                >
                  {descExpanded ? "Show less" : "Show more"}
                </button>
              )}
            </div>
          );
        })()}
        {(descriptionSignals.length > 0 || llmBadgeLabel) && (
          <div className="mt-2">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              Description Signals
            </p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {llmBadgeLabel && (
                <span
                  className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                    llmAdjustment < 0
                      ? "border-amber-300 bg-amber-50 text-amber-700"
                      : "border-emerald-300 bg-emerald-50 text-emerald-700"
                  }`}
                >
                  {llmBadgeLabel}
                  {llm?.confidence != null && (
                    <span className="ml-1 opacity-70">{Math.round(llm.confidence * 100)}%</span>
                  )}
                </span>
              )}
              {descriptionSignals.map((signal, idx) => {
                const chipClass =
                  signal.direction === "positive"
                    ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                    : signal.direction === "negative"
                      ? "border-amber-300 bg-amber-50 text-amber-700"
                      : "border-[var(--line)] bg-[var(--bg)] text-[var(--ink-soft)]";
                return (
                  <span
                    key={`${signal.label ?? "signal"}-${idx}`}
                    className={`rounded-full border px-2 py-0.5 text-[11px] ${chipClass}`}
                  >
                    {signal.label}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="px-6 py-5">
        <FieldGrid fields={coreFields} />
      </div>
    </div>
  );
}
