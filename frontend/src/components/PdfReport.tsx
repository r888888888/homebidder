import { Document, Page, View, Text, StyleSheet } from "@react-pdf/renderer";
import type { AnalysisDetail } from "../routes/analysis_.$id";

const NAVY = "#0F2035";
const CORAL = "#E55A3A";
const INK = "#111827";
const INK_MUTED = "#6B7280";
const BORDER = "#E5E7EB";
const BG_ALT = "#F9FAFB";

const styles = StyleSheet.create({
  page: { fontFamily: "Helvetica", fontSize: 9, color: INK, backgroundColor: "#FFFFFF" },

  // Header
  header: {
    backgroundColor: NAVY,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  headerLogo: { color: "#FFFFFF", fontSize: 13, fontFamily: "Helvetica-Bold" },
  headerSubtitle: { color: "#FFFFFF", fontSize: 8, opacity: 0.8 },

  // Content area
  content: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 36 },

  // Property headline
  addressText: { fontSize: 16, fontFamily: "Helvetica-Bold", color: NAVY, marginBottom: 4 },
  dateText: { fontSize: 8, color: INK_MUTED, marginBottom: 4 },
  propertyChips: { flexDirection: "row", gap: 8, marginBottom: 12 },
  chip: {
    backgroundColor: BG_ALT,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    fontSize: 8,
    color: INK_MUTED,
  },

  // Section
  section: { marginBottom: 14 },
  divider: { borderBottomWidth: 0.5, borderBottomColor: BORDER, marginBottom: 10 },
  sectionLabel: {
    fontSize: 7,
    fontFamily: "Helvetica-Bold",
    color: CORAL,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 6,
  },

  // Offer recommendation
  offerRow: { flexDirection: "row", gap: 6, marginBottom: 6 },
  offerBox: {
    flex: 1,
    borderWidth: 0.5,
    borderColor: BORDER,
    borderRadius: 4,
    padding: 6,
    alignItems: "center",
  },
  offerBoxHighlight: {
    flex: 1,
    borderWidth: 1,
    borderColor: CORAL,
    borderRadius: 4,
    padding: 6,
    alignItems: "center",
    backgroundColor: "#FFF5F3",
  },
  offerLabel: { fontSize: 7, color: INK_MUTED, marginBottom: 2 },
  offerValue: { fontSize: 11, fontFamily: "Helvetica-Bold", color: INK },
  offerMeta: { flexDirection: "row", gap: 16 },
  offerMetaItem: { fontSize: 8, color: INK_MUTED },

  // Risk
  riskRow: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  riskBadge: { borderRadius: 3, paddingHorizontal: 6, paddingVertical: 2, fontSize: 8, fontFamily: "Helvetica-Bold" },
  riskFactor: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2, borderBottomWidth: 0.5, borderBottomColor: BORDER },
  riskFactorName: { fontSize: 8, color: INK, flex: 3 },
  riskFactorLevel: { fontSize: 8, color: INK_MUTED, flex: 1, textAlign: "right" },

  // Comps table
  tableHeader: { flexDirection: "row", backgroundColor: BG_ALT, paddingVertical: 4, paddingHorizontal: 4, borderBottomWidth: 0.5, borderBottomColor: BORDER },
  tableRow: { flexDirection: "row", paddingVertical: 3, paddingHorizontal: 4, borderBottomWidth: 0.5, borderBottomColor: BORDER },
  tableRowAlt: { flexDirection: "row", paddingVertical: 3, paddingHorizontal: 4, borderBottomWidth: 0.5, borderBottomColor: BORDER, backgroundColor: BG_ALT },
  colAddress: { flex: 4, fontSize: 7 },
  colPrice: { flex: 2, fontSize: 7, textAlign: "right" },
  colBedBath: { flex: 1, fontSize: 7, textAlign: "center" },
  colSqft: { flex: 1.5, fontSize: 7, textAlign: "right" },
  colPsf: { flex: 1.5, fontSize: 7, textAlign: "right" },
  colPct: { flex: 1.5, fontSize: 7, textAlign: "right" },
  tableHeaderText: { fontSize: 7, fontFamily: "Helvetica-Bold", color: INK_MUTED },

  // Investment
  projRow: { flexDirection: "row", gap: 6, marginBottom: 6 },
  projBox: { flex: 1, borderWidth: 0.5, borderColor: BORDER, borderRadius: 4, padding: 6, alignItems: "center" },
  projLabel: { fontSize: 7, color: INK_MUTED, marginBottom: 2 },
  projValue: { fontSize: 10, fontFamily: "Helvetica-Bold", color: NAVY },
  rentRow: { flexDirection: "row", gap: 16, marginBottom: 4 },
  rentItem: { fontSize: 8, color: INK_MUTED },
  footnote: { fontSize: 7, color: INK_MUTED, marginTop: 4 },

  // Footer
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: NAVY,
    paddingVertical: 8,
    paddingHorizontal: 24,
    alignItems: "center",
  },
  footerText: { color: "#FFFFFF", fontSize: 7, opacity: 0.8, textAlign: "center" },
});

function formatMoney(n: number): string {
  return "$" + n.toLocaleString("en-US");
}

function riskColor(level: string): string {
  switch (level?.toLowerCase()) {
    case "low": return "#16A34A";
    case "moderate": return "#D97706";
    case "high": return "#EA580C";
    case "very high": return "#DC2626";
    default: return INK_MUTED;
  }
}

interface Props {
  analysis: AnalysisDetail;
}

export function PdfReport({ analysis }: Props) {
  const { offer_data, risk_data, investment_data, comps, property_data } = analysis;
  const date = new Date(analysis.created_at).toLocaleDateString("en-US", { dateStyle: "long" });
  const topComps = comps.slice(0, 5);

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        {/* ── Header ── */}
        <View style={styles.header}>
          <Text style={styles.headerLogo}>HomeBidder</Text>
          <Text style={styles.headerSubtitle}>Property Analysis Report</Text>
        </View>

        <View style={styles.content}>
          {/* ── Property Headline ── */}
          <View style={styles.section}>
            <Text style={styles.addressText}>{analysis.address}</Text>
            <Text style={styles.dateText}>Analysis generated {date}</Text>
            {property_data && (
              <View style={styles.propertyChips}>
                {property_data.bedrooms != null && (
                  <Text style={styles.chip}>{property_data.bedrooms} bed</Text>
                )}
                {property_data.bathrooms != null && (
                  <Text style={styles.chip}>{property_data.bathrooms} bath</Text>
                )}
                {property_data.sqft != null && (
                  <Text style={styles.chip}>{property_data.sqft.toLocaleString()} sqft</Text>
                )}
                {property_data.year_built != null && (
                  <Text style={styles.chip}>Built {property_data.year_built}</Text>
                )}
              </View>
            )}
          </View>

          {/* ── Offer Recommendation ── */}
          {offer_data && (
            <View style={styles.section}>
              <View style={styles.divider} />
              <Text style={styles.sectionLabel}>Offer Recommendation</Text>
              <View style={styles.offerRow}>
                <View style={styles.offerBox}>
                  <Text style={styles.offerLabel}>Conservative</Text>
                  <Text style={styles.offerValue}>{formatMoney(offer_data.offer_low)}</Text>
                </View>
                <View style={styles.offerBoxHighlight}>
                  <Text style={styles.offerLabel}>★ Recommended</Text>
                  <Text style={styles.offerValue}>{formatMoney(offer_data.offer_recommended)}</Text>
                </View>
                <View style={styles.offerBox}>
                  <Text style={styles.offerLabel}>Aggressive</Text>
                  <Text style={styles.offerValue}>{formatMoney(offer_data.offer_high)}</Text>
                </View>
              </View>
              <View style={styles.offerMeta}>
                <Text style={styles.offerMetaItem}>
                  Fair Value: {formatMoney(offer_data.fair_value_estimate)}
                </Text>
                <Text style={styles.offerMetaItem}>
                  List Price: {formatMoney(offer_data.list_price)}
                </Text>
                {offer_data.posture && (
                  <Text style={styles.offerMetaItem}>
                    Posture: {offer_data.posture.charAt(0).toUpperCase() + offer_data.posture.slice(1)}
                  </Text>
                )}
              </View>
            </View>
          )}

          {/* ── Risk Summary ── */}
          {risk_data && (
            <View style={styles.section}>
              <View style={styles.divider} />
              <Text style={styles.sectionLabel}>Risk Assessment</Text>
              <View style={styles.riskRow}>
                <Text style={styles.offerMetaItem}>Overall Risk:</Text>
                <View
                  style={[
                    styles.riskBadge,
                    { backgroundColor: riskColor(risk_data.overall_risk) + "22", color: riskColor(risk_data.overall_risk) },
                  ]}
                >
                  <Text style={{ color: riskColor(risk_data.overall_risk), fontSize: 8, fontFamily: "Helvetica-Bold" }}>
                    {risk_data.overall_risk}
                  </Text>
                </View>
              </View>
              {risk_data.factors.slice(0, 5).map((f, i) => (
                <View key={i} style={styles.riskFactor}>
                  <Text style={styles.riskFactorName}>{f.name}</Text>
                  <Text style={[styles.riskFactorLevel, { color: riskColor(f.level) }]}>{f.level}</Text>
                </View>
              ))}
            </View>
          )}

          {/* ── Comparable Sales ── */}
          {topComps.length > 0 && (
            <View style={styles.section}>
              <View style={styles.divider} />
              <Text style={styles.sectionLabel}>Comparable Sales</Text>
              <View style={styles.tableHeader}>
                <Text style={[styles.colAddress, styles.tableHeaderText]}>Address</Text>
                <Text style={[styles.colPrice, styles.tableHeaderText]}>Sold Price</Text>
                <Text style={[styles.colBedBath, styles.tableHeaderText]}>Bd/Ba</Text>
                <Text style={[styles.colSqft, styles.tableHeaderText]}>Sqft</Text>
                <Text style={[styles.colPsf, styles.tableHeaderText]}>$/Sqft</Text>
                <Text style={[styles.colPct, styles.tableHeaderText]}>% Ask</Text>
              </View>
              {topComps.map((c, i) => (
                <View key={i} style={i % 2 === 0 ? styles.tableRow : styles.tableRowAlt}>
                  <Text style={styles.colAddress}>{c.address}</Text>
                  <Text style={styles.colPrice}>{c.sold_price ? formatMoney(c.sold_price) : "—"}</Text>
                  <Text style={styles.colBedBath}>{c.bedrooms}/{c.bathrooms}</Text>
                  <Text style={styles.colSqft}>{c.sqft ? c.sqft.toLocaleString() : "—"}</Text>
                  <Text style={styles.colPsf}>{c.price_per_sqft ? "$" + c.price_per_sqft : "—"}</Text>
                  <Text style={styles.colPct}>
                    {c.pct_over_asking != null ? (c.pct_over_asking > 0 ? "+" : "") + c.pct_over_asking.toFixed(1) + "%" : "—"}
                  </Text>
                </View>
              ))}
            </View>
          )}

          {/* ── Investment Snapshot ── */}
          {investment_data && (
            <View style={styles.section}>
              <View style={styles.divider} />
              <Text style={styles.sectionLabel}>Investment Snapshot</Text>
              <View style={styles.projRow}>
                <View style={styles.projBox}>
                  <Text style={styles.projLabel}>10yr Projected</Text>
                  <Text style={styles.projValue}>{formatMoney(investment_data.projected_value_10yr)}</Text>
                </View>
                <View style={styles.projBox}>
                  <Text style={styles.projLabel}>20yr Projected</Text>
                  <Text style={styles.projValue}>{formatMoney(investment_data.projected_value_20yr)}</Text>
                </View>
                <View style={styles.projBox}>
                  <Text style={styles.projLabel}>30yr Projected</Text>
                  <Text style={styles.projValue}>{formatMoney(investment_data.projected_value_30yr)}</Text>
                </View>
              </View>
              <View style={styles.rentRow}>
                <Text style={styles.rentItem}>
                  Monthly Buy Cost: {formatMoney(investment_data.monthly_buy_cost)}
                </Text>
                <Text style={styles.rentItem}>
                  Monthly Rent: {formatMoney(investment_data.monthly_rent_equivalent)}
                </Text>
              </View>
              <Text style={styles.footnote}>* Based on FHFA HPI trend — not financial advice.</Text>
            </View>
          )}
        </View>

        {/* ── Footer ── */}
        <View style={styles.footer} fixed>
          <Text style={styles.footerText}>
            Generated by HomeBidder · homebidder.com · For informational purposes only. Not a substitute for professional real estate advice.
          </Text>
        </View>
      </Page>
    </Document>
  );
}
