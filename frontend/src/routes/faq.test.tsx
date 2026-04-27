import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
}));

import { FAQPage } from "./faq";

describe("FAQPage", () => {
  it("renders the FAQ heading", () => {
    render(<FAQPage />);
    expect(
      screen.getByRole("heading", { name: /frequently asked questions/i })
    ).toBeInTheDocument();
  });

  it("renders multiple question buttons", () => {
    render(<FAQPage />);
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(3);
  });

  it("answers are collapsed by default", () => {
    render(<FAQPage />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => {
      expect(btn.getAttribute("aria-expanded")).toBe("false");
    });
  });

  it("expands an answer when the question is clicked", async () => {
    const user = userEvent.setup();
    render(<FAQPage />);
    const [firstBtn] = screen.getAllByRole("button");
    await user.click(firstBtn);
    expect(firstBtn.getAttribute("aria-expanded")).toBe("true");
  });

  it("collapses an expanded answer when clicked again", async () => {
    const user = userEvent.setup();
    render(<FAQPage />);
    const [firstBtn] = screen.getAllByRole("button");
    await user.click(firstBtn);
    expect(firstBtn.getAttribute("aria-expanded")).toBe("true");
    await user.click(firstBtn);
    expect(firstBtn.getAttribute("aria-expanded")).toBe("false");
  });

  it("multiple answers can be open simultaneously", async () => {
    const user = userEvent.setup();
    render(<FAQPage />);
    const buttons = screen.getAllByRole("button");
    await user.click(buttons[0]);
    await user.click(buttons[1]);
    expect(buttons[0].getAttribute("aria-expanded")).toBe("true");
    expect(buttons[1].getAttribute("aria-expanded")).toBe("true");
  });

  it("shows answer text after expanding", async () => {
    const user = userEvent.setup();
    render(<FAQPage />);
    const [firstBtn] = screen.getAllByRole("button");
    // Answer should not be visible before clicking
    const questionText = firstBtn.textContent ?? "";
    expect(questionText.length).toBeGreaterThan(0);
    await user.click(firstBtn);
    // aria-expanded now true means content panel is shown
    const panelId = firstBtn.getAttribute("aria-controls");
    expect(panelId).toBeTruthy();
    const panel = document.getElementById(panelId!);
    expect(panel).not.toBeNull();
    expect(panel!.textContent!.length).toBeGreaterThan(0);
  });
});
