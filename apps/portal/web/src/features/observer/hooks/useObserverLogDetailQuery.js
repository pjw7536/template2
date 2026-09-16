import { useQuery } from "@tanstack/react-query";
import { observerApi } from "../api/observerApi";
import { observerQueryKeys } from "../api/queryKeys";
import { getLogKey } from "../utils/logPagination";

function shouldRetry(failureCount, error) {
  if (failureCount >= 1) return false;
  return !error?.status || [429, 502, 503].includes(error.status);
}

export function useObserverLogDetailQuery(eqpId, compactLog) {
  const logKey = getLogKey(compactLog?.logType);
  const detailId = compactLog?.detailId;

  return useQuery({
    queryKey: observerQueryKeys.logDetail(logKey, eqpId, detailId),
    queryFn: ({ signal }) =>
      observerApi.fetchLogDetail({ logKey, eqpId, detailId, signal }),
    enabled: Boolean(eqpId && logKey && detailId),
    staleTime: 1000 * 60 * 5,
    gcTime: 1000 * 60 * 2,
    retry: shouldRetry,
  });
}
