import { useEffect, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { observerApi } from "../api/observerApi";

export function useObserverAnalysis(scope) {
  const scopeKey = useMemo(() => JSON.stringify(scope), [scope]);
  const mutation = useMutation({
    mutationFn: () => observerApi.analyzeLogs(scope),
    retry: false,
  });
  const reset = mutation.reset;

  useEffect(() => {
    reset();
  }, [reset, scopeKey]);

  return {
    scopeKey,
    canRun: Boolean(scope?.eqpId && scope?.from && scope?.to && scope?.logTypes?.length),
    data: mutation.data || null,
    error: mutation.isError ? mutation.error : null,
    isPending: mutation.isPending,
    run: mutation.mutate,
    reset,
  };
}
