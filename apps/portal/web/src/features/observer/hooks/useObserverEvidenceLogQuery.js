import { useQuery } from "@tanstack/react-query";

import { observerApi } from "../api/observerApi";
import { observerQueryKeys } from "../api/queryKeys";

function shouldRetry(failureCount, error) {
  if (failureCount >= 1 || error?.status === 404) return false;
  return !error?.status || [429, 502, 503].includes(error.status);
}

export function useObserverEvidenceLogQuery(
  eqpId,
  evidenceNavigation,
  options = {}
) {
  const logKey = evidenceNavigation?.logKey || "";
  const evidenceId = evidenceNavigation?.evidenceId || "";
  const range = {
    from: evidenceNavigation?.from || "",
    to: evidenceNavigation?.to || "",
  };
  const enabled =
    Boolean(eqpId && logKey && evidenceId && range.from && range.to) &&
    (options.enabled ?? true);

  return useQuery({
    queryKey: observerQueryKeys.evidenceLog(
      logKey,
      eqpId,
      evidenceId,
      range
    ),
    queryFn: ({ signal }) =>
      observerApi.fetchEvidenceLog({
        logKey,
        eqpId,
        evidenceId,
        ...range,
        signal,
      }),
    enabled,
    staleTime: 1000 * 60 * 5,
    gcTime: 1000 * 60 * 2,
    retry: shouldRetry,
  });
}
