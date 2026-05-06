import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useFetch, type FetchOptions } from "./useFetch";

vi.mock("../lib/auth", () => ({
  authHeaders: () => ({ Authorization: "Bearer test-token" }),
}));

function okResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function errResponse(status: number, statusText = "Error") {
  return new Response(null, { status, statusText });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useFetch", () => {
  it("starts in loading state when url is provided", () => {
    vi.mocked(fetch).mockResolvedValue(okResponse({ value: 1 }));
    const { result } = renderHook(() =>
      useFetch<{ value: number }>("http://api/test")
    );
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("is not loading and does not fetch when url is null", () => {
    const { result } = renderHook(() => useFetch<unknown>(null));
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sets data and clears loading on success", async () => {
    vi.mocked(fetch).mockResolvedValue(okResponse({ name: "test" }));
    const { result } = renderHook(() =>
      useFetch<{ name: string }>("http://api/test")
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ name: "test" });
    expect(result.current.error).toBeNull();
  });

  it("sets error when response is not ok", async () => {
    vi.mocked(fetch).mockResolvedValue(errResponse(404, "Not Found"));
    const { result } = renderHook(() => useFetch<unknown>("http://api/test"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("Not Found");
  });

  it("sets error when network throws", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("Network failure"));
    const { result } = renderHook(() => useFetch<unknown>("http://api/test"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error?.message).toBe("Network failure");
  });

  it("passes auth headers to fetch", async () => {
    const spy = vi.mocked(fetch).mockResolvedValue(okResponse({}));
    renderHook(() => useFetch<unknown>("http://api/test"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const [, init] = spy.mock.calls[0];
    expect((init?.headers as Record<string, string>)?.Authorization).toBe(
      "Bearer test-token"
    );
  });

  it("refetch re-runs the request", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(okResponse({ v: 1 }))
      .mockResolvedValueOnce(okResponse({ v: 2 }));
    const { result } = renderHook(() =>
      useFetch<{ v: number }>("http://api/test")
    );
    await waitFor(() => expect(result.current.data?.v).toBe(1));

    act(() => {
      result.current.refetch();
    });
    await waitFor(() => expect(result.current.data?.v).toBe(2));
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("re-fetches when url changes", async () => {
    vi.mocked(fetch).mockResolvedValue(okResponse({}));
    const { rerender } = renderHook(
      ({ url }) => useFetch<unknown>(url),
      { initialProps: { url: "http://api/a" } }
    );
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    rerender({ url: "http://api/b" });
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(vi.mocked(fetch).mock.calls[1][0]).toBe("http://api/b");
  });

  it("transitions to not-loading when url changes from value to null", async () => {
    vi.mocked(fetch).mockResolvedValue(okResponse({ v: 1 }));
    const { result, rerender } = renderHook(
      ({ url }: { url: string | null }) => useFetch<unknown>(url),
      { initialProps: { url: "http://api/a" as string | null } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    rerender({ url: null });
    expect(result.current.loading).toBe(false);
  });
});

describe("useFetch — retry", () => {
  // Use retries: 2, retryDelayMs: 0 so retries fire immediately — no fake timers needed.
  const RETRY_OPTS = { retries: 2, retryDelayMs: 0 } satisfies FetchOptions;

  it("retries once after a 5xx and resolves on the second attempt", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(errResponse(503, "Service Unavailable"))
      .mockResolvedValueOnce(okResponse({ v: "ok" }));

    const { result } = renderHook(() =>
      useFetch<{ v: string }>("http://api/test", RETRY_OPTS)
    );

    await waitFor(() => expect(result.current.data).toEqual({ v: "ok" }));
    expect(result.current.error).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("retries once after a network error and resolves on the second attempt", async () => {
    vi.mocked(fetch)
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(okResponse({ ok: true }));

    const { result } = renderHook(() =>
      useFetch<{ ok: boolean }>("http://api/test", RETRY_OPTS)
    );

    await waitFor(() => expect(result.current.data).toEqual({ ok: true }));
    expect(result.current.error).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("does not retry on 4xx errors", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(404, "Not Found"));

    const { result } = renderHook(() =>
      useFetch<unknown>("http://api/test", RETRY_OPTS)
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(result.current.error?.message).toBe("Not Found");
  });

  it("does not retry or set error on AbortError", async () => {
    const abortErr = new DOMException("signal is aborted", "AbortError");
    vi.mocked(fetch).mockRejectedValueOnce(abortErr);

    renderHook(() =>
      useFetch<unknown>("http://api/test", RETRY_OPTS)
    );

    // Allow time for any retry that would fire at retryDelayMs=0 to execute.
    await act(async () => {
      await new Promise<void>((r) => setTimeout(r, 30));
    });

    // AbortErrors are silently swallowed: no retry, no error state.
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("exhausts all retries and sets error when every attempt fails", async () => {
    vi.mocked(fetch).mockResolvedValue(errResponse(500, "Internal Server Error"));

    const { result } = renderHook(() =>
      useFetch<unknown>("http://api/test", RETRY_OPTS)
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetch).toHaveBeenCalledTimes(3); // initial + 2 retries
    expect(result.current.error?.message).toBe("Internal Server Error");
  });

  it("stays loading while retrying before final success", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(errResponse(503))
      // second call never resolves — still in-flight
      .mockReturnValueOnce(new Promise<Response>(() => {}));

    const { result } = renderHook(() =>
      useFetch<unknown>("http://api/test", RETRY_OPTS)
    );

    await act(async () => {
      // enough time for the retry delay (0ms) and the second fetch to start
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
