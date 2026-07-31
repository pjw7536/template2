import { useEffect, useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { observerApi } from "../api/observerApi";
import { observerQueryKeys } from "../api/queryKeys";
import {
  DEFAULT_LOG_QUERY_OPTIONS,
  DEFAULT_TYPE_FILTERS,
} from "../utils/constants";
import { transformLogsToTableData } from "../utils/dataTransformers";
import { addDurationToLogs, mergeLogsByTime } from "../utils/logs";
import {
  getEnabledLogKeys,
  mergeUniqueLogItems,
  OBSERVER_LOG_CONFIG,
  OBSERVER_LOG_PAGE_SIZE,
  OBSERVER_RESIDENT_LOG_LIMIT,
} from "../utils/logPagination";

const LOG_QUERY_STALE_TIME = 1000 * 60 * 5;
const LOG_QUERY_GC_TIME = 1000 * 60 * 2;
const ALL_LOG_KEYS = OBSERVER_LOG_CONFIG.map(({ logKey }) => logKey);
const ALL_LOG_KEY_VALUE = ALL_LOG_KEYS.join(",");

function shouldRetry(failureCount, error) {
  if (failureCount >= 1) return false;
  return !error?.status || [429, 502, 503].includes(error.status);
}

function buildScopeKey(eqpId, logQueryOptions) {
  return JSON.stringify([eqpId || "", logQueryOptions]);
}

function getLogTimestamp(item) {
  const timestamp = Date.parse(item?.eventTime || "");
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function mergeResidentLogs(batchData, entries, pageQueries) {
  const result = {};
  const seen = new Set();
  let residentCount = 0;

  for (const { logKey } of OBSERVER_LOG_CONFIG) {
    const initialItems = mergeUniqueLogItems(
      [batchData?.[logKey]?.items || []],
      OBSERVER_RESIDENT_LOG_LIMIT
    );
    result[logKey] = initialItems;
    residentCount += initialItems.length;
    initialItems.forEach((item) => seen.add(`${logKey}:${item.id}`));
  }

  const extraItems = [];
  entries.forEach((entry, index) => {
    for (const item of pageQueries[index]?.data?.items || []) {
      const identity = `${entry.logKey}:${item.id}`;
      if (seen.has(identity)) continue;
      seen.add(identity);
      extraItems.push({
        item,
        logKey: entry.logKey,
        sequence: extraItems.length,
      });
    }
  });
  extraItems.sort(
    (left, right) =>
      getLogTimestamp(right.item) - getLogTimestamp(left.item) ||
      left.sequence - right.sequence
  );

  const remainingBudget = Math.max(
    OBSERVER_RESIDENT_LOG_LIMIT - residentCount,
    0
  );
  extraItems.slice(0, remainingBudget).forEach(({ item, logKey }) => {
    result[logKey].push(item);
  });
  return result;
}

function getLatestPageState(logKey, batchData, entries, pageQueries) {
  const matchingIndexes = entries
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => entry.logKey === logKey);
  const lastMatch = matchingIndexes.at(-1);
  if (lastMatch) {
    const query = pageQueries[lastMatch.index];
    if (query?.data) {
      return {
        cursor: query.data.page?.nextCursor,
        hasMore: Boolean(query.data.page?.hasMore),
      };
    }
  }
  const initial = batchData?.[logKey];
  return {
    cursor: initial?.nextCursor,
    hasMore: Boolean(initial?.hasMore),
  };
}

export function useObserverLogs(
  eqpId,
  typeFilters = DEFAULT_TYPE_FILTERS,
  selectedTipGroups = ["__ALL__"],
  logQueryOptions = DEFAULT_LOG_QUERY_OPTIONS
) {
  const enabledTypes = typeFilters || DEFAULT_TYPE_FILTERS;
  const enabledLogKeys = useMemo(
    () => getEnabledLogKeys(enabledTypes),
    [enabledTypes]
  );
  const enabledLogKeySet = useMemo(
    () => new Set(enabledLogKeys),
    [enabledLogKeys]
  );
  const scopeKey = useMemo(
    () => buildScopeKey(eqpId, logQueryOptions),
    [eqpId, logQueryOptions]
  );
  const [pageRequests, setPageRequests] = useState({
    scopeKey,
    entries: [],
  });
  const activePageRequests = useMemo(
    () => (pageRequests.scopeKey === scopeKey ? pageRequests.entries : []),
    [pageRequests.entries, pageRequests.scopeKey, scopeKey]
  );

  useEffect(() => {
    setPageRequests({ scopeKey, entries: [] });
  }, [scopeKey]);

  const batchQuery = useQuery({
    queryKey: observerQueryKeys.logBatch(
      eqpId,
      ALL_LOG_KEY_VALUE,
      logQueryOptions
    ),
    queryFn: ({ signal }) =>
      observerApi.fetchLogBatch({
        eqpId,
        types: ALL_LOG_KEYS,
        pageSize: OBSERVER_LOG_PAGE_SIZE,
        signal,
        ...logQueryOptions,
      }),
    enabled: Boolean(eqpId),
    staleTime: LOG_QUERY_STALE_TIME,
    gcTime: LOG_QUERY_GC_TIME,
    retry: shouldRetry,
  });

  const pageQueries = useQueries({
    queries: activePageRequests.map(({ logKey, cursor }) => ({
      queryKey: observerQueryKeys.logPage(
        logKey,
        eqpId,
        logQueryOptions,
        cursor
      ),
      queryFn: ({ signal }) =>
        observerApi.fetchLogPage({
          logKey,
          eqpId,
          cursor,
          pageSize: OBSERVER_LOG_PAGE_SIZE,
          signal,
          ...logQueryOptions,
        }),
      enabled: Boolean(eqpId && cursor),
      staleTime: LOG_QUERY_STALE_TIME,
      gcTime: LOG_QUERY_GC_TIME,
      retry: shouldRetry,
    })),
  });

  const batchData = batchQuery.data?.data;
  const logsByKey = useMemo(
    () => mergeResidentLogs(batchData, activePageRequests, pageQueries),
    [activePageRequests, batchData, pageQueries]
  );

  const residentLogCount = useMemo(
    () =>
      Object.values(logsByKey).reduce(
        (total, items) => total + items.length,
        0
      ),
    [logsByKey]
  );
  const hasMoreByType = useMemo(() => {
    const result = {};
    for (const { logKey } of OBSERVER_LOG_CONFIG) {
      result[logKey] =
        enabledLogKeySet.has(logKey) &&
        residentLogCount < OBSERVER_RESIDENT_LOG_LIMIT &&
        getLatestPageState(
          logKey,
          batchData,
          activePageRequests,
          pageQueries
        ).hasMore;
    }
    return result;
  }, [
    activePageRequests,
    batchData,
    enabledLogKeySet,
    pageQueries,
    residentLogCount,
  ]);
  const loadingMoreTypes = useMemo(() => {
    const values = new Set();
    activePageRequests.forEach((entry, index) => {
      if (pageQueries[index]?.isFetching) values.add(entry.logKey);
    });
    return values;
  }, [activePageRequests, pageQueries]);

  const loadMoreType = (logKey) => {
    const pageState = getLatestPageState(
      logKey,
      batchData,
      activePageRequests,
      pageQueries
    );
    if (
      !pageState.hasMore ||
      !pageState.cursor ||
      !enabledLogKeySet.has(logKey) ||
      loadingMoreTypes.has(logKey) ||
      residentLogCount >= OBSERVER_RESIDENT_LOG_LIMIT
    ) {
      return;
    }
    setPageRequests((current) => {
      const entries = current.scopeKey === scopeKey ? current.entries : [];
      if (
        entries.some(
          (entry) => entry.logKey === logKey && entry.cursor === pageState.cursor
        )
      ) {
        return current;
      }
      return {
        scopeKey,
        entries: [...entries, { logKey, cursor: pageState.cursor }],
      };
    });
  };

  const allLogsWithDuration = useMemo(
    () => ({
      eqpLogs: addDurationToLogs(logsByKey.eqp || [], "EQP"),
      tipLogs: addDurationToLogs(logsByKey.tip || [], "TIP"),
      spcInterlockLogs: logsByKey["spc-interlock"] || [],
      fdcInterlockLogs: logsByKey["fdc-interlock"] || [],
      ctttmLogs: logsByKey.ctttm || [],
      racbLogs: logsByKey.racb || [],
      esopLogs: logsByKey.esop || [],
    }),
    [logsByKey]
  );
  const logsWithDuration = useMemo(
    () => ({
      eqpLogs: enabledTypes.EQP ? allLogsWithDuration.eqpLogs : [],
      tipLogs: enabledTypes.TIP ? allLogsWithDuration.tipLogs : [],
      spcInterlockLogs: enabledTypes.SPC_ITL
        ? allLogsWithDuration.spcInterlockLogs
        : [],
      fdcInterlockLogs: enabledTypes.FDC_ITL
        ? allLogsWithDuration.fdcInterlockLogs
        : [],
      ctttmLogs: enabledTypes.CTTTM
        ? allLogsWithDuration.ctttmLogs
        : [],
      racbLogs: enabledTypes.RACB ? allLogsWithDuration.racbLogs : [],
      esopLogs: enabledTypes.ESOP ? allLogsWithDuration.esopLogs : [],
    }),
    [allLogsWithDuration, enabledTypes]
  );

  const logErrors = useMemo(() => {
    const errors = [];
    if (batchQuery.isError) {
      errors.push({
        type: "전체",
        message:
          batchQuery.error instanceof Error
            ? batchQuery.error.message
            : "로그 조회에 실패했습니다.",
        refetch: batchQuery.refetch,
      });
      return errors;
    }
    for (const { logKey, label } of OBSERVER_LOG_CONFIG) {
      const sourceError = batchData?.[logKey]?.error;
      if (sourceError) {
        errors.push({
          type: label,
          message: sourceError.message,
          refetch: batchQuery.refetch,
        });
      }
    }
    activePageRequests.forEach((entry, index) => {
      const query = pageQueries[index];
      if (!query?.isError) return;
      const label =
        OBSERVER_LOG_CONFIG.find(({ logKey }) => logKey === entry.logKey)
          ?.label || entry.logKey;
      errors.push({
        type: label,
        message:
          query.error instanceof Error
            ? query.error.message
            : "추가 로그 조회에 실패했습니다.",
        refetch: query.refetch,
      });
    });
    return errors;
  }, [
    activePageRequests,
    batchData,
    batchQuery.error,
    batchQuery.isError,
    batchQuery.refetch,
    pageQueries,
  ]);

  const refetchFailedLogs = () => {
    logErrors.forEach((error) => error.refetch());
  };
  const mergedLogs = useMemo(
    () => (eqpId ? mergeLogsByTime(logsWithDuration) : []),
    [eqpId, logsWithDuration]
  );
  const logsLoading = Boolean(eqpId) && batchQuery.isLoading;
  const tableData = useMemo(() => {
    if (!eqpId || logsLoading) return [];
    return transformLogsToTableData(
      mergedLogs,
      enabledTypes,
      selectedTipGroups
    );
  }, [enabledTypes, eqpId, logsLoading, mergedLogs, selectedTipGroups]);
  const filteredTipLogs = useMemo(
    () => mergedLogs.filter((log) => log.logType === "TIP"),
    [mergedLogs]
  );

  return {
    logsLoading,
    logsWithDuration,
    mergedLogs,
    tableData,
    filteredTipLogs,
    logErrors,
    hasLogErrors: logErrors.length > 0,
    refetchFailedLogs,
    hasMoreByType,
    loadMoreType,
    loadingMoreTypes,
    residentLogCount,
    residentLimitReached:
      residentLogCount >= OBSERVER_RESIDENT_LOG_LIMIT,
  };
}
