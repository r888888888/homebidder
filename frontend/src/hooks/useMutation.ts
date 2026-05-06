import { useCallback, useState } from "react";

export interface MutationState<TInput, TOutput> {
  mutate: (input: TInput) => Promise<TOutput>;
  data: TOutput | null;
  loading: boolean;
  error: Error | null;
  reset: () => void;
}

/**
 * Wraps an async mutation function with loading/error/data state.
 *
 * `mutate` always re-throws on failure so callers can do their own error
 * handling (e.g. toast a specific message for a 409 ALREADY_SEEN error).
 * `onSuccess` fires only when the mutation succeeds.
 *
 * Usage:
 *   const { mutate, loading } = useMutation(
 *     (input) => apiClient.markSeen(...),
 *     (result) => { toast.success("Saved"); onChanged?.(); }
 *   );
 */
export function useMutation<TInput, TOutput>(
  fn: (input: TInput) => Promise<TOutput>,
  onSuccess?: (data: TOutput) => void
): MutationState<TInput, TOutput> {
  const [data, setData] = useState<TOutput | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const mutate = useCallback(
    async (input: TInput): Promise<TOutput> => {
      setLoading(true);
      setError(null);
      try {
        const result = await fn(input);
        setData(result);
        onSuccess?.(result);
        return result;
      } catch (err) {
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [fn, onSuccess]
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { mutate, data, loading, error, reset };
}
