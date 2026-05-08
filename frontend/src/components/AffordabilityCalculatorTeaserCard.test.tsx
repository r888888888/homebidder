import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AffordabilityCalculatorTeaserCard } from "./AffordabilityCalculatorTeaserCard";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

beforeEach(() => {
  localStorage.clear();
});

describe("AffordabilityCalculatorTeaserCard", () => {
  it("renders teaser copy and upgrade link to /pricing", () => {
    render(<AffordabilityCalculatorTeaserCard />);

    expect(screen.getByText("Affordability Calculator")).toBeInTheDocument();
    const upgradeLink = screen.getByRole("link", { name: /upgrade to investor/i });
    expect(upgradeLink).toHaveAttribute("href", "/pricing");
  });

  it("renders no input fields", () => {
    render(<AffordabilityCalculatorTeaserCard />);

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/income/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/down payment/i)).not.toBeInTheDocument();
  });
});
