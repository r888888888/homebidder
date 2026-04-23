import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FixerAnalysisCard, type FixerAnalysisData } from "./FixerAnalysisCard";

const BASE: FixerAnalysisData = {
  is_fixer: true,
  fixer_signals: ["Fixer / Contractor Special"],
  offer_recommended: 900_000,
  renovation_estimate_low: 65_000,
  renovation_estimate_mid: 88_000,
  renovation_estimate_high: 111_000,
  line_items: [
    { category: "Kitchen remodel", low: 35_000, high: 60_000 },
    { category: "Bathroom remodel", low: 30_000, high: 51_000 },
  ],
  all_in_fixer_low: 965_000,
  all_in_fixer_mid: 988_000,
  all_in_fixer_high: 1_011_000,
  turnkey_value: 1_100_000,
  renovated_fair_value: 1_100_000,
  implied_equity_mid: 112_000,
  verdict: "cheaper_fixer",
  savings_mid: 112_000,
  scope_notes: "Kitchen and bath are primary work.",
  disclaimer:
    "Renovation costs are rough Bay Area estimates based on current labor and material rates. Get contractor bids before committing.",
};

// Fixture for verdict-flip and cheaper_turnkey tests
// offer=900k, turnkey=1.0M, items=[Full gut 200k-220k + paint 5k-8k]
// allInMid = 900k + 211.5k = 1111.5k → cheaper_turnkey
const FLIP_BASE: FixerAnalysisData = {
  is_fixer: true,
  fixer_signals: ["Fixer / Contractor Special"],
  offer_recommended: 900_000,
  renovation_estimate_low: 205_000,
  renovation_estimate_mid: 211_500,
  renovation_estimate_high: 228_000,
  line_items: [
    { category: "Full gut renovation", low: 200_000, high: 220_000 },
    { category: "Interior paint", low: 5_000, high: 8_000 },
  ],
  all_in_fixer_low: 1_105_000,
  all_in_fixer_mid: 1_111_500,
  all_in_fixer_high: 1_128_000,
  turnkey_value: 1_000_000,
  renovated_fair_value: 1_000_000,
  implied_equity_mid: -111_500,
  verdict: "cheaper_turnkey",
  savings_mid: -111_500,
  disclaimer: "Renovation costs are rough Bay Area estimates.",
};

describe("FixerAnalysisCard", () => {
  it("renders card heading", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/fixer analysis/i)).toBeInTheDocument();
  });

  it("renders verdict badge 'Fixer May Win' for cheaper_fixer", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/fixer may win/i)).toBeInTheDocument();
  });

  it("renders verdict badge 'Turn-key Cheaper' for cheaper_turnkey", () => {
    // offer=900k, items=[Full gut 200k-220k], turnkey=1.0M → allInMid=1.11M → cheaper_turnkey
    render(<FixerAnalysisCard data={FLIP_BASE} />);
    expect(screen.getByText(/turn-key cheaper/i)).toBeInTheDocument();
  });

  it("renders verdict badge 'Comparable Cost' for comparable", () => {
    // offer=900k, items=[Kitchen 190k-210k], turnkey=1.1M → allInMid=1.1M → 0% → comparable
    const comparableData: FixerAnalysisData = {
      ...BASE,
      line_items: [{ category: "Kitchen remodel", low: 190_000, high: 210_000 }],
      renovation_estimate_low: 190_000,
      renovation_estimate_mid: 200_000,
      renovation_estimate_high: 210_000,
      all_in_fixer_low: 1_090_000,
      all_in_fixer_mid: 1_100_000,
      all_in_fixer_high: 1_110_000,
      verdict: "comparable",
      savings_mid: 0,
    };
    render(<FixerAnalysisCard data={comparableData} />);
    expect(screen.getByText(/comparable cost/i)).toBeInTheDocument();
  });

  it("shows all-in fixer mid cost", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // $988,000 formatted
    expect(screen.getByText(/988,000/)).toBeInTheDocument();
  });

  it("shows turn-key AVM", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // $1,100,000 formatted — appears in the Fair Value cell
    expect(screen.getAllByText(/1,100,000/).length).toBeGreaterThan(0);
  });

  it("shows savings amount when fixer is cheaper", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // savings_mid = 112,000 — appears in the savings banner
    expect(screen.getAllByText(/112,000/).length).toBeGreaterThan(0);
  });

  it("shows overage amount when turn-key is cheaper", () => {
    // FLIP_BASE: offer=900k, items=[Full gut 200k-220k + paint 5k-8k], turnkey=1M → overage shown
    render(<FixerAnalysisCard data={FLIP_BASE} />);
    // activeLow=205k, activeHigh=228k, activeMid=216.5k, allInMid=1116.5k, overage=116.5k
    // appears in the delta banner
    expect(screen.getAllByText(/116,500/).length).toBeGreaterThan(0);
  });

  it("renders renovation line item categories", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/kitchen remodel/i)).toBeInTheDocument();
    expect(screen.getByText(/bathroom remodel/i)).toBeInTheDocument();
  });

  it("renders disclaimer text", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/get contractor bids/i)).toBeInTheDocument();
  });

  it("shows reno-adjusted offer label", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/reno-adjusted offer/i)).toBeInTheDocument();
  });

  it("shows reno-adjusted offer value (offer_recommended − activeMid)", () => {
    // offer=900k, activeMid=(65k+111k)/2=88k → 900k-88k=812k
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByText(/\$812,000/)).toBeInTheDocument();
  });
});

describe("FixerAnalysisCard toggle behavior", () => {
  it("all items enabled by default (no disabled styling)", () => {
    render(<FixerAnalysisCard data={BASE} />);
    // Toggle buttons should be present and checked
    const toggles = screen.getAllByRole("checkbox");
    expect(toggles).toHaveLength(BASE.line_items.length);
    toggles.forEach((cb) => expect(cb).toBeChecked());
  });

  it("clicking a toggle button unchecks that item", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    const toggle = screen.getByRole("checkbox", { name: /toggle kitchen remodel/i });
    await userEvent.click(toggle);
    expect(toggle).not.toBeChecked();
  });

  it("re-clicking a disabled item re-enables it", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    const toggle = screen.getByRole("checkbox", { name: /toggle kitchen remodel/i });
    await userEvent.click(toggle); // disable
    await userEvent.click(toggle); // re-enable
    expect(toggle).toBeChecked();
  });

  it("toggle button has accessible aria-label", () => {
    render(<FixerAnalysisCard data={BASE} />);
    expect(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /toggle bathroom remodel/i })).toBeInTheDocument();
  });

  it("total updates when an item is disabled", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    // Before: total should be $65,000–$111,000 (35+30=65k low, 60+51=111k high)
    expect(screen.getByText(/65,000–.111,000/)).toBeInTheDocument();

    // Disable Kitchen remodel (35k-60k); only Bathroom remains (30k-51k)
    // Note: the Total row and the Bathroom line item both show $30,000–$51,000 — use getAllByText
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i }));
    expect(screen.getAllByText(/30,000–.51,000/).length).toBeGreaterThan(0);
  });

  it("all-in fixer cost updates when an item is disabled", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    // Initial all-in mid: 900k + (65k+111k)/2 = 900k + 88k = 988k
    expect(screen.getByText(/988,000/)).toBeInTheDocument();

    // Disable Kitchen (35k-60k); Bathroom only (30k-51k), mid=40500
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i }));
    // new all-in mid: 900k + 40500 = 940500 → displayed as $940,500
    expect(screen.getByText(/940,500/)).toBeInTheDocument();
  });

  it("savings amount updates when an item is disabled", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    // Initial savings: 1.1M - 988k = 112k
    expect(screen.getAllByText(/112,000/).length).toBeGreaterThan(0);

    // Disable Kitchen; new savings: 1.1M - 940500 = 159500
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i }));
    expect(screen.getAllByText(/159,500/).length).toBeGreaterThan(0);
  });

  it("reno-adjusted offer updates when an item is disabled", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    // Initial: 900k - 88k = 812k
    expect(screen.getByText(/\$812,000/)).toBeInTheDocument();

    // Disable Kitchen (35k-60k); Bathroom only (30k-51k), mid=40500 → 900k-40500=859500
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i }));
    expect(screen.getByText(/\$859,500/)).toBeInTheDocument();
  });

  it("verdict badge updates when disabling items changes the cost ratio", async () => {
    render(<FixerAnalysisCard data={FLIP_BASE} />);
    // Initial: cheaper_turnkey
    expect(screen.getByText(/turn-key cheaper/i)).toBeInTheDocument();

    // Disable big item (Full gut renovation: 200k-220k); only paint (5k-8k) remains
    // new all-in mid: 900k + 6500 = 906500, savings: 1M - 906500 = 93500 (>3%) → cheaper_fixer
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle full gut renovation/i }));
    expect(screen.getByText(/fixer may win/i)).toBeInTheDocument();
  });
});

describe("FixerAnalysisCard persistence", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true } as Response);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("initializes disabled items from initialDisabledIndices prop", () => {
    render(<FixerAnalysisCard data={BASE} analysisId={42} initialDisabledIndices={[0]} />);
    const kitchenToggle = screen.getByRole("checkbox", { name: /toggle kitchen remodel/i });
    const bathroomToggle = screen.getByRole("checkbox", { name: /toggle bathroom remodel/i });
    expect(kitchenToggle).not.toBeChecked();
    expect(bathroomToggle).toBeChecked();
  });

  it("sends PATCH request after toggle when analysisId is provided", async () => {
    render(<FixerAnalysisCard data={BASE} analysisId={42} />);
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i }));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/analyses/42/renovation-toggles",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ disabled_indices: [0] }),
        }),
      );
    }, { timeout: 1000 });
  });

  it("does not send PATCH when analysisId is not provided", async () => {
    render(<FixerAnalysisCard data={BASE} />);
    await userEvent.click(screen.getByRole("checkbox", { name: /toggle kitchen remodel/i }));
    // Give debounce time to fire if it were going to
    await new Promise((r) => setTimeout(r, 600));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
