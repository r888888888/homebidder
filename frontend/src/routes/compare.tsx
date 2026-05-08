import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { apiClient, type AnalysisSummary } from "../lib/api";
import { useToast } from "../components/Toast";
import type { PropertyData } from "../components/PropertySummaryCard";
import type { OfferData } from "../components/OfferRecommendationCard";
import type { RiskData } from "../components/RiskAnalysisCard";

export const Route = createFileRoute("/compare")({ component: ComparePage });

const MAX_SELECTION = 4;
const MIN_SELECTION = 2;

interface AnalysisDetail {
  id: number;
  address: string;
  offer_recommended: number | null;
  risk_level: string | null;
  property_data: PropertyData | null;
  offer_data: OfferData | null;
  risk_data: RiskData | null;
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function fmtPpsf(price: number | null | undefined, sqft: number | null | undefined): string {
  if (!price || !sqft || sqft <= 0) return "—";
  return "$" + Math.round(price / sqft).toLocaleString("en-US") + "/sqft";
}

function fmtSqft(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US") + " sqft";
}

function fmtBedsBaths(beds: number | null | undefined, baths: number | null | undefined): string {
  if (beds == null && baths == null) return "—";
  const bedsStr = beds == null ? "—" : String(beds);
  const bathsStr = baths == null ? "—" : String(baths);
  return `${bedsStr} bd / ${bathsStr} ba`;
}

const RISK_PILL_STYLES: Record<string, string> = {
  Low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Moderate: "bg-amber-50 text-amber-700 border-amber-200",
  High: "bg-orange-50 text-orange-700 border-orange-200",
  "Very High": "bg-red-50 text-red-700 border-red-200",
};

function RiskPill({ level }: { level: string | null }) {
  if (!level) return <span>—</span>;
  const style = RISK_PILL_STYLES[level] ?? "bg-[var(--bg)] text-[var(--ink-soft)] border-[var(--line)]";
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {level}
    </span>
  );
}

interface ComparisonRow {
  label: string;
  render: (a: AnalysisDetail) => React.ReactNode;
}

const COMPARISON_ROWS: ComparisonRow[] = [
  {
    label: "City",
    render: (a) => a.property_data?.city ?? "—",
  },
  {
    label: "Neighborhood",
    render: (a) => a.property_data?.neighborhoods ?? "—",
  },
  {
    label: "Beds / Baths",
    render: (a) => fmtBedsBaths(a.property_data?.bedrooms, a.property_data?.bathrooms),
  },
  {
    label: "Sqft",
    render: (a) => fmtSqft(a.property_data?.sqft),
  },
  {
    label: "Lot Size",
    render: (a) => fmtSqft(a.property_data?.lot_size),
  },
  {
    label: "List Price",
    render: (a) => fmtUsd(a.offer_data?.list_price),
  },
  {
    label: "Recommended Offer",
    render: (a) => fmtUsd(a.offer_recommended),
  },
  {
    label: "Fair Value",
    render: (a) => fmtUsd(a.offer_data?.fair_value_estimate ?? null),
  },
  {
    label: "$/sqft",
    render: (a) => fmtPpsf(a.offer_data?.list_price ?? a.offer_recommended, a.property_data?.sqft),
  },
  {
    label: "Risk Level",
    render: (a) => <RiskPill level={a.risk_level ?? a.risk_data?.overall_risk ?? null} />,
  },
];

export function ComparePage() {
  const toast = useToast();
  const [favorites, setFavorites] = useState<AnalysisSummary[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [details, setDetails] = useState<AnalysisDetail[] | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Fetch all favorited analyses on mount.
  useEffect(() => {
    let alive = true;
    apiClient
      .getAnalysesList(1, "", 100, { favorites: true })
      .then((res) => {
        if (alive) setFavorites(res.items);
      })
      .catch(() => {
        if (alive) toast.error("Failed to load favorited analyses.");
      });
    return () => {
      alive = false;
    };
  }, [toast]);

  const atMax = selected.size >= MAX_SELECTION;
  const canCompare = selected.size >= MIN_SELECTION && selected.size <= MAX_SELECTION;

  const toggleSelected = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < MAX_SELECTION) next.add(id);
      return next;
    });
  };

  const startCompare = async () => {
    if (!canCompare) return;
    setLoadingDetails(true);
    setComparing(true);
    try {
      const ids = Array.from(selected);
      const responses = await Promise.all(
        ids.map((id) => apiClient.getAnalysis(id))
      );
      const loaded: AnalysisDetail[] = [];
      for (let i = 0; i < responses.length; i += 1) {
        const r = responses[i];
        if ("notFound" in r) {
          toast.error(`Analysis ${ids[i]} was not found.`);
        } else {
          loaded.push(r.data as unknown as AnalysisDetail);
        }
      }
      setDetails(loaded);
    } catch {
      toast.error("Failed to load analysis details.");
      setComparing(false);
    } finally {
      setLoadingDetails(false);
    }
  };

  const backToSelection = () => {
    setComparing(false);
    setDetails(null);
  };

  const sortedFavorites = useMemo(() => favorites ?? [], [favorites]);

  return (
    <main className="page-wrap py-10">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="display-title text-2xl font-bold text-[var(--ink)]">
          Compare Properties
        </h1>
        <Link to="/history" className="text-sm underline text-[var(--ink-soft)]">
          History
        </Link>
      </div>

      {!comparing && (
        <p className="text-sm text-[var(--ink-soft)] mb-4">
          Pick {MIN_SELECTION}–{MAX_SELECTION} favorited analyses to compare side-by-side.
        </p>
      )}

      {favorites === null ? (
        <p className="text-[var(--ink-soft)]">Loading favorites…</p>
      ) : favorites.length === 0 ? (
        <div className="rounded-lg border border-[var(--line)] bg-[var(--card)] p-6 text-center">
          <p className="text-[var(--ink-soft)] mb-3">
            No favorited analyses yet.
          </p>
          <p className="text-sm text-[var(--ink-soft)]">
            Favorite some analyses from your{" "}
            <Link to="/history" className="underline text-[var(--navy)]">History</Link>{" "}
            to compare them here.
          </p>
        </div>
      ) : !comparing ? (
        <SelectionView
          favorites={sortedFavorites}
          selected={selected}
          atMax={atMax}
          canCompare={canCompare}
          onToggle={toggleSelected}
          onCompare={startCompare}
        />
      ) : (
        <ComparisonView
          details={details}
          loading={loadingDetails}
          onBack={backToSelection}
        />
      )}
    </main>
  );
}

function SelectionView({
  favorites,
  selected,
  atMax,
  canCompare,
  onToggle,
  onCompare,
}: {
  favorites: AnalysisSummary[];
  selected: Set<number>;
  atMax: boolean;
  canCompare: boolean;
  onToggle: (id: number) => void;
  onCompare: () => void;
}) {
  return (
    <div className="space-y-4">
      <ul className="divide-y divide-[var(--line)] rounded-lg border border-[var(--line)] bg-[var(--card)]">
        {favorites.map((a) => {
          const isChecked = selected.has(a.id);
          const disabled = !isChecked && atMax;
          return (
            <li key={a.id} className="px-4 py-3">
              <label
                className={`flex items-center gap-3 ${disabled ? "opacity-50" : "cursor-pointer"}`}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  disabled={disabled}
                  onChange={() => onToggle(a.id)}
                  className="h-4 w-4 cursor-pointer"
                />
                <span className="flex-1 text-sm">
                  <span className="font-medium text-[var(--ink)]">{a.address}</span>
                  <span className="ml-2 text-xs text-[var(--ink-muted)]">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </span>
                <span className="text-xs text-[var(--ink-soft)]">
                  {a.offer_recommended ? `$${a.offer_recommended.toLocaleString()}` : "—"}
                </span>
              </label>
            </li>
          );
        })}
      </ul>

      <div className="flex items-center justify-between">
        <span className="text-sm text-[var(--ink-soft)]">
          {selected.size} selected
        </span>
        <button
          type="button"
          onClick={onCompare}
          disabled={!canCompare}
          className="rounded-lg bg-[var(--navy)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Compare
        </button>
      </div>
    </div>
  );
}

function ComparisonView({
  details,
  loading,
  onBack,
}: {
  details: AnalysisDetail[] | null;
  loading: boolean;
  onBack: () => void;
}) {
  if (loading || details === null) {
    return <p className="text-[var(--ink-soft)]">Loading comparison…</p>;
  }
  if (details.length < 2) {
    return (
      <div className="space-y-4">
        <p className="text-[var(--ink-soft)]">
          Not enough analyses available to compare.
        </p>
        <button
          type="button"
          onClick={onBack}
          className="text-sm underline text-[var(--navy)]"
        >
          Change selection
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="text-sm underline text-[var(--navy)]"
        >
          ← Change selection
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--line)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--line)] bg-[var(--bg)]">
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Field
              </th>
              {details.map((d) => (
                <th
                  key={d.id}
                  className="px-4 py-3 text-left text-xs font-semibold text-[var(--ink)]"
                >
                  <Link
                    to="/analysis/$id"
                    params={{ id: String(d.id) }}
                    className="hover:underline"
                  >
                    {d.address}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARISON_ROWS.map((row) => (
              <tr key={row.label} className="border-b border-[var(--line)] last:border-b-0">
                <td className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-[var(--ink-muted)]">
                  {row.label}
                </td>
                {details.map((d) => (
                  <td key={d.id} className="px-4 py-3 text-[var(--ink)]">
                    {row.render(d)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
