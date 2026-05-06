import { useCallback, useEffect, useRef, useState } from "react";
import { authHeaders } from "../lib/auth";

export interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export interface FetchOptions {
  /**
   * Number of additional attempts after the first failure (default: 0 — no retry).
   * Pass `retries: 2` to retry up to twice on transient errors.
   */
  retries?: number;
  /** Base delay in ms between retries; doubles each attempt (default: 300). */
  retryDelayMs?: number;
}

const sleep = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Fetches JSON from `url` and manages loading/error/data state.
 *
 * Pass `null` to skip fetching (e.g. when the user is not authenticated).
 * The caller controls auth-gating via a conditional URL:
 *
 *   const { data } = useFetch(user ? `${apiBase}/api/resource` : null);
 *
 * Auth headers are attached automatically via authHeaders().
 * AbortController cancels in-flight requests on unmount or URL change.
 * Transient failures (5xx, network errors) are retried up to `retries` times
 * with exponential back-off. 4xx errors and AbortErrors are never retried.
 */
export function useFetch<T>(
  url: string | null,
  { retries = 0, retryDelayMs = 300 }: FetchOptions = {}
): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(url !== null);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const optionsRef = useRef({ retries, retryDelayMs });
  optionsRef.current = { retries, retryDelayMs };

  const execute = useCallback((targetUrl: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    const { retries: maxRetries, retryDelayMs: delay } = optionsRef.current;

    const isAbortError = (err: unknown): boolean =>
      (err as { name?: string } | null)?.name === "AbortError";

    function attempt(n: number): Promise<T> {
      return fetch(targetUrl, {
        headers: authHeaders(),
        signal: controller.signal,
      }).then(
        async (r) => {
          if (!r.ok) {
            const err = new Error(r.statusText || String(r.status));
            // 4xx — client error; never retry
            if (r.status >= 400 && r.status < 500) throw err;
            // 5xx — transient; retry if attempts remain
            if (n < maxRetries) {
              await sleep(delay * Math.pow(2, n));
              return attempt(n + 1);
            }
            throw err;
          }
          return r.json() as Promise<T>;
        },
        async (fetchErr: unknown) => {
          // fetch() itself threw — network error or AbortError
          if (isAbortError(fetchErr)) throw fetchErr;
          if (n < maxRetries) {
            await sleep(delay * Math.pow(2, n));
            return attempt(n + 1);
          }
          throw fetchErr;
        }
      );
    }

    attempt(0)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (isAbortError(err)) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setLoading(false);
      });
  }, []);

  const refetch = useCallback(() => {
    if (url) execute(url);
  }, [url, execute]);

  useEffect(() => {
    if (!url) {
      setData(null);
      setLoading(false);
      return;
    }
    execute(url);
    return () => {
      abortRef.current?.abort();
    };
  }, [url, execute]);

  return { data, loading, error, refetch };
}
