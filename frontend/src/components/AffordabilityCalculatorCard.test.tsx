import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AffordabilityCalculatorCard } from "./AffordabilityCalculatorCard";
import type { InvestmentData } from "./InvestmentCard";
import type { OfferData } from "./OfferRecommendationCard";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const mockUseAuth = vi.fn();
vi.mock("../lib/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const BASE_INVESTMENT: InvestmentData = {
  purchase_price: 900_000,
  projected_value_10yr: null,
  projected_value_20yr: null,
  projected_value_30yr: null,
  rate_30yr_fixed: 6.8,
  as_of_date: "2026-01-01",
  hpi_yoy_assumption_pct: 4.0,
  monthly_buy_cost: 5_500,
  monthly_rent_equivalent: 3_200,
  monthly_cost_diff: 2_300,
  opportunity_cost_10yr: null,
  opportunity_cost_20yr: null,
  opportunity_cost_30yr: null,
  adu_potential: false,
  adu_rent_estimate: null,
  rent_controlled: false,
  rent_control_city: null,
  rent_control_implications: null,
  nearest_bart_station: null,
  bart_distance_miles: null,
  nearest_muni_stop: null,
  muni_distance_miles: null,
  transit_premium_likely: false,
  nearby_schools: [],
};

const BASE_OFFER: OfferData = {
  list_price: 899_000,
  is_unlisted: false,
  fair_value_estimate: 900_000,
  offer_low: 880_000,
  offer_recommended: 920_000,
  offer_high: 960_000,
  posture: "competitive",
  spread_vs_list_pct: 2.3,
  median_pct_over_asking: 5,
  pct_sold_over_asking: 70,
  offer_review_advisory: null,
  contingency_recommendation: null,
  hoa_equivalent_sfh_value: null,
};

beforeEach(() => {
  localStorage.clear();
  mockUseAuth.mockReturnValue({
    user: { id: "user-test-123", subscription_tier: "investor" },
    isLoading: false,
  });
});

describe("AffordabilityCalculatorCard", () => {
  it("renders five labeled inputs with correct defaults when localStorage is empty", () => {
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    expect(screen.getByLabelText(/annual income/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/monthly debts/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/down payment/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/hoa/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/target rate/i)).toBeInTheDocument();

    // Rate should be seeded from investment.rate_30yr_fixed (6.8)
    expect(screen.getByLabelText(/target rate/i)).toHaveValue("6.8");
    // HOA defaults to 0 (no HOA in BASE_OFFER)
    expect(screen.getByLabelText(/hoa/i)).toHaveValue("0");
  });

  it("falls back to 6.5 when rate_30yr_fixed is null and no localStorage", () => {
    render(
      <AffordabilityCalculatorCard
        investment={{ ...BASE_INVESTMENT, rate_30yr_fixed: null }}
        offer={BASE_OFFER}
      />
    );

    expect(screen.getByLabelText(/target rate/i)).toHaveValue("6.5");
  });

  it("typing income shows max purchase price", async () => {
    const user = userEvent.setup();
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "200000");

    // Max price should appear (not placeholder dash)
    await waitFor(() => {
      expect(screen.getByText(/max purchase price/i)).toBeInTheDocument();
      // Some formatted dollar amount should be visible
      expect(screen.getByTestId("max-price-value")).toBeInTheDocument();
    });
  });

  it("adding monthly debts reduces the max purchase price", async () => {
    const user = userEvent.setup();
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "200000");

    await waitFor(() => {
      expect(screen.getByTestId("max-price-value")).toBeInTheDocument();
    });

    const priceWithNoDebts = screen.getByTestId("max-price-value").textContent ?? "";

    await user.clear(screen.getByLabelText(/monthly debts/i));
    await user.type(screen.getByLabelText(/monthly debts/i), "1500");

    await waitFor(() => {
      const priceWithDebts = screen.getByTestId("max-price-value").textContent ?? "";
      expect(priceWithDebts).not.toBe(priceWithNoDebts);
    });
  });

  it("monthly comparison shows emerald message when property fits in budget", async () => {
    const user = userEvent.setup();
    // monthly_buy_cost = 5500, give high enough income to have hMax > 5500
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    // $300k income, DTI 45%, H_max = 0.45 × 25000 = 11250 > 5500
    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "300000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "200000");

    await waitFor(() => {
      expect(screen.getByTestId("monthly-comparison")).toBeInTheDocument();
    });

    expect(screen.getByTestId("monthly-comparison")).toHaveAttribute("data-positive", "true");
    expect(screen.getByTestId("monthly-comparison").textContent).toMatch(/margin/i);
  });

  it("monthly comparison shows amber message when property exceeds budget", async () => {
    const user = userEvent.setup();
    // monthly_buy_cost = 5500, give low income so H_max < 5500
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    // $100k income, DTI 40%, H_max = 0.40 × 8333 = 3333 < 5500
    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "100000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "200000");

    await waitFor(() => {
      expect(screen.getByTestId("monthly-comparison")).toBeInTheDocument();
    });

    expect(screen.getByTestId("monthly-comparison")).toHaveAttribute("data-positive", "false");
    expect(screen.getByTestId("monthly-comparison").textContent).toMatch(/over your max/i);
  });

  it("monthly comparison is hidden when monthly_buy_cost is null", async () => {
    const user = userEvent.setup();
    render(
      <AffordabilityCalculatorCard
        investment={{ ...BASE_INVESTMENT, monthly_buy_cost: null }}
        offer={BASE_OFFER}
      />
    );

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "200000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "200000");

    await waitFor(() => {
      expect(screen.queryByTestId("monthly-comparison")).not.toBeInTheDocument();
    });
  });

  it("price gap renders against offer_recommended; falls back to list_price; hides when both null", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />
    );

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "200000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "200000");

    await waitFor(() => {
      expect(screen.getByTestId("price-gap")).toBeInTheDocument();
    });

    // Test fallback to list_price
    rerender(
      <AffordabilityCalculatorCard
        investment={BASE_INVESTMENT}
        offer={{ ...BASE_OFFER, offer_recommended: null, list_price: 890_000 }}
      />
    );

    // With offer_recommended null and list_price set, price-gap should still show
    await waitFor(() => {
      expect(screen.getByTestId("price-gap")).toBeInTheDocument();
    });

    // Test hide when both null
    rerender(
      <AffordabilityCalculatorCard
        investment={BASE_INVESTMENT}
        offer={{ ...BASE_OFFER, offer_recommended: null, list_price: null }}
      />
    );

    await waitFor(() => {
      expect(screen.queryByTestId("price-gap")).not.toBeInTheDocument();
    });
  });

  it("persists buyer fields to localStorage and rehydrates on remount; HOA not persisted", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <AffordabilityCalculatorCard
        investment={BASE_INVESTMENT}
        offer={{ ...BASE_OFFER, hoa_equivalent_sfh_value: { monthly_hoa_fee: 500, extra_purchase_power: 0, equivalent_sfh_price_no_hoa: 0, assumptions: { mortgage_rate_pct: 6.5, mortgage_term_years: 30, down_payment_pct: 0.20 } } }}
      />
    );

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "180000");
    await user.clear(screen.getByLabelText(/monthly debts/i));
    await user.type(screen.getByLabelText(/monthly debts/i), "800");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "150000");

    // Verify localStorage was updated
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem("homebidder_affordability_user-test-123") ?? "{}");
      expect(stored.annualIncome).toBe(180000);
    });

    unmount();

    // Remount — different offer (HOA 700 instead of 500)
    render(
      <AffordabilityCalculatorCard
        investment={BASE_INVESTMENT}
        offer={{ ...BASE_OFFER, hoa_equivalent_sfh_value: { monthly_hoa_fee: 700, extra_purchase_power: 0, equivalent_sfh_price_no_hoa: 0, assumptions: { mortgage_rate_pct: 6.5, mortgage_term_years: 30, down_payment_pct: 0.20 } } }}
      />
    );

    // Buyer fields should rehydrate from localStorage
    await waitFor(() => {
      expect(screen.getByLabelText(/annual income/i)).toHaveValue("180000");
      expect(screen.getByLabelText(/monthly debts/i)).toHaveValue("800");
      // HOA should be from new offer prefill (700), NOT from prior session
      expect(screen.getByLabelText(/hoa/i)).toHaveValue("700");
    });
  });

  it("shows debts-exceed-budget message when debts + HOA blow the DTI cap", async () => {
    const user = userEvent.setup();
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    // $100k income, DTI 40%, monthly income $8333, H_max = 3333
    // Debts = 4000 > 3333 → blown
    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "100000");
    await user.clear(screen.getByLabelText(/monthly debts/i));
    await user.type(screen.getByLabelText(/monthly debts/i), "4000");

    await waitFor(() => {
      expect(screen.getByTestId("debts-blown")).toBeInTheDocument();
      expect(screen.getByTestId("debts-blown").textContent).toMatch(/40%/);
    });
  });

  it("renders DTI cap label that updates when income crosses a tier boundary", async () => {
    const user = userEvent.setup();
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "99000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "100000");

    await waitFor(() => {
      expect(screen.getByTestId("dti-cap-label")).toHaveTextContent("36%");
    });

    // Cross the $100k tier boundary
    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "100000");

    await waitFor(() => {
      expect(screen.getByTestId("dti-cap-label")).toHaveTextContent("40%");
    });
  });

  it("tooltip info button is present and has aria-describedby pointing to rationale text", async () => {
    const user = userEvent.setup();
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "150000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "100000");

    await waitFor(() => {
      const infoBtn = screen.getByRole("button", { name: /about dti cap/i });
      expect(infoBtn).toBeInTheDocument();
      const tooltipId = infoBtn.getAttribute("aria-describedby");
      expect(tooltipId).toBeTruthy();
      const tooltip = document.getElementById(tooltipId!);
      expect(tooltip).toBeInTheDocument();
      expect(tooltip?.textContent).toMatch(/informed product judgment/i);
    });
  });

  it("shows PMI indicator when implied dp < 20%; absent when dp >= 20%", async () => {
    const user = userEvent.setup();
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    // Low down payment — will be sub-20%
    await user.clear(screen.getByLabelText(/annual income/i));
    await user.type(screen.getByLabelText(/annual income/i), "200000");
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "50000");

    await waitFor(() => {
      expect(screen.getByTestId("dp-pct-line").textContent).toMatch(/pmi/i);
    });

    // High down payment — no PMI
    await user.clear(screen.getByLabelText(/down payment/i));
    await user.type(screen.getByLabelText(/down payment/i), "300000");

    await waitFor(() => {
      expect(screen.getByTestId("dp-pct-line").textContent).not.toMatch(/pmi/i);
    });
  });

  it("renders disclaimer about closing costs and reserves", () => {
    render(<AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />);

    expect(screen.getByText(/closing costs/i)).toBeInTheDocument();
    expect(screen.getByText(/reserves/i)).toBeInTheDocument();
  });

  it("returns null and does not crash when user is null", () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false });
    const { container } = render(
      <AffordabilityCalculatorCard investment={BASE_INVESTMENT} offer={BASE_OFFER} />
    );

    expect(container.firstChild).toBeNull();
  });
});
