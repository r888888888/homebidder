import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (config: unknown) => config,
}));

import { ChangelogPage } from "./changelog";

describe("ChangelogPage", () => {
  it("renders the Changelog heading", () => {
    render(<ChangelogPage />);
    expect(
      screen.getByRole("heading", { name: /changelog/i })
    ).toBeInTheDocument();
  });

  it("shows at least one version number", () => {
    render(<ChangelogPage />);
    expect(screen.getAllByText(/v1\.\d+\.\d+/).length).toBeGreaterThan(0);
  });

  it("shows the most recent version (v1.5.0) at the top", () => {
    render(<ChangelogPage />);
    expect(screen.getByText(/v1\.5\.0/)).toBeInTheDocument();
  });
});
