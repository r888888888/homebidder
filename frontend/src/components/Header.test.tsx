import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Header from "./Header";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

describe("Header", () => {
  it("renders the HomeBidder logo link to /", () => {
    render(<Header />);
    const homeLink = screen.getByRole("link", { name: /homebidder/i });
    expect(homeLink).toHaveAttribute("href", "/");
  });

  it("renders a History nav link to /history", () => {
    render(<Header />);
    const historyLink = screen.getByRole("link", { name: /history/i });
    expect(historyLink).toHaveAttribute("href", "/history");
  });
});
