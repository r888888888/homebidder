import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useMutation } from "./useMutation";

describe("useMutation", () => {
  it("starts in idle state", () => {
    const { result } = renderHook(() =>
      useMutation(() => Promise.resolve("ok"))
    );
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("is loading during an in-flight mutation", async () => {
    let resolvePromise!: () => void;
    const pending = new Promise<string>((res) => {
      resolvePromise = () => res("done");
    });
    const { result } = renderHook(() => useMutation(() => pending));

    act(() => {
      void result.current.mutate(null);
    });
    expect(result.current.loading).toBe(true);

    await act(async () => {
      resolvePromise();
      await pending;
    });
    expect(result.current.loading).toBe(false);
  });

  it("sets data and clears loading on success", async () => {
    const { result } = renderHook(() =>
      useMutation(() => Promise.resolve({ id: 1 }))
    );
    await act(() => result.current.mutate(null));
    expect(result.current.data).toEqual({ id: 1 });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("passes input to the mutation function", async () => {
    const fn = vi.fn((x: number) => Promise.resolve(x * 2));
    const { result } = renderHook(() => useMutation(fn));
    await act(() => result.current.mutate(5));
    expect(fn).toHaveBeenCalledWith(5);
    expect(result.current.data).toBe(10);
  });

  it("calls onSuccess with the result", async () => {
    const onSuccess = vi.fn();
    const { result } = renderHook(() =>
      useMutation(() => Promise.resolve("value"), onSuccess)
    );
    await act(() => result.current.mutate(null));
    expect(onSuccess).toHaveBeenCalledWith("value");
  });

  it("sets error and clears loading on failure", async () => {
    const { result } = renderHook(() =>
      useMutation(() => Promise.reject(new Error("oops")))
    );
    await act(async () => {
      await result.current.mutate(null).catch(() => {});
    });
    expect(result.current.error?.message).toBe("oops");
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("re-throws so callers can handle errors", async () => {
    const { result } = renderHook(() =>
      useMutation(() => Promise.reject(new Error("fail")))
    );
    await act(async () => {
      await expect(result.current.mutate(null)).rejects.toThrow("fail");
    });
  });

  it("does not call onSuccess when mutation fails", async () => {
    const onSuccess = vi.fn();
    const { result } = renderHook(() =>
      useMutation(() => Promise.reject(new Error("no")), onSuccess)
    );
    await act(async () => {
      await result.current.mutate(null).catch(() => {});
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("reset clears data, error, and loading", async () => {
    const { result } = renderHook(() =>
      useMutation(() => Promise.resolve({ id: 2 }))
    );
    await act(() => result.current.mutate(null));
    expect(result.current.data).toEqual({ id: 2 });

    act(() => {
      result.current.reset();
    });
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });
});
