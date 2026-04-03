import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
  useNavigate: () => vi.fn(),
}));

vi.mock("../components/AnalysisForm", () => ({
  AnalysisForm: () => <div data-testid="analysis-form" />,
}));

describe("HomePage", () => {
  it("renders stylized cards in the How it works section", async () => {
    const { Route } = await import("./index");
    const Component = (Route as { component: () => JSX.Element }).component;

    const { container } = render(<Component />);

    expect(screen.getByRole("heading", { name: /how it works/i })).toBeInTheDocument();

    const cards = container.querySelectorAll(".how-it-works-card");
    expect(cards).toHaveLength(3);

    cards.forEach((card) => {
      expect(card.className).toContain("group");
      expect(card.className).toContain("transition");
    });

    const stepBadge = container.querySelector(".how-it-works-step-badge");
    expect(stepBadge).toBeTruthy();
    expect(stepBadge?.className).toContain("mx-auto");
    expect(stepBadge?.className).toContain("bg-transparent");
    expect(stepBadge?.className).toContain("[font-family:Georgia,'Times_New_Roman',serif]");
    expect(stepBadge?.className).not.toContain("rounded-full");
  });
});
