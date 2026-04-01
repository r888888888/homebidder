import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ToastProvider, useToast } from "./Toast";

function ShowToast({ message }: { message: string }) {
  const toast = useToast();
  return <button onClick={() => toast.error(message)}>show</button>;
}

describe("Toast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders error message when triggered", () => {
    render(
      <ToastProvider>
        <ShowToast message="Rate limit hit. Try again in 30 seconds." />
      </ToastProvider>
    );
    act(() => screen.getByRole("button").click());
    expect(screen.getByRole("alert")).toHaveTextContent("Rate limit hit. Try again in 30 seconds.");
  });

  it("auto-dismisses after 5 seconds", () => {
    render(
      <ToastProvider>
        <ShowToast message="Something went wrong." />
      </ToastProvider>
    );
    act(() => screen.getByRole("button").click());
    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(5000));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("can be dismissed manually", async () => {
    render(
      <ToastProvider>
        <ShowToast message="Dismiss me." />
      </ToastProvider>
    );
    act(() => screen.getByRole("button", { name: "show" }).click());
    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => screen.getByRole("button", { name: "Dismiss" }).click());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
