import { useMemo } from "react";
import { useEqpLogs } from "./useEqpLogs";
import { useTipLogs } from "./useTipLogs";
import { useCtttmLogs } from "./useCtttmLogs";
import { useRacbLogs } from "./useRacbLogs";
import { useJiraLogs } from "./useJiraLogs";
import { DEFAULT_TYPE_FILTERS } from "../utils/constants";
import { transformLogsToTableData } from "../utils/dataTransformers";
import { addDurationToLogs, mergeLogsByTime } from "../utils/logs";

export function useTimelineLogs(
  eqpId,
  typeFilters = DEFAULT_TYPE_FILTERS,
  selectedTipGroups = ["__ALL__"]
) {
  const { data: eqpLogs = [], isLoading: eqpLoading } = useEqpLogs(eqpId);
  const { data: tipLogs = [], isLoading: tipLoading } = useTipLogs(eqpId);
  const { data: ctttmLogs = [], isLoading: ctttmLoading } = useCtttmLogs(eqpId);
  const { data: racbLogs = [], isLoading: racbLoading } = useRacbLogs(eqpId);
  const { data: jiraLogs = [], isLoading: jiraLoading } = useJiraLogs(eqpId);

  const logsLoading =
    eqpLoading || tipLoading || ctttmLoading || racbLoading || jiraLoading;

  // Heavy transforms (sorting + duration calc) stay memoized to avoid recomputing
  // on every minor UI toggle.
  const logsWithDuration = useMemo(
    () => ({
      eqpLogs: addDurationToLogs(eqpLogs, "EQP"),
      tipLogs: addDurationToLogs(tipLogs, "TIP"),
      ctttmLogs: ctttmLogs || [],
      racbLogs: racbLogs || [],
      jiraLogs: jiraLogs || [],
    }),
    [eqpLogs, tipLogs, ctttmLogs, racbLogs, jiraLogs]
  );

  const mergedLogs = useMemo(
    () => (eqpId ? mergeLogsByTime(logsWithDuration) : []),
    [eqpId, logsWithDuration]
  );

  const tableData = useMemo(() => {
    if (!eqpId || logsLoading) return [];
    return transformLogsToTableData(
      mergedLogs,
      typeFilters || DEFAULT_TYPE_FILTERS,
      selectedTipGroups
    );
  }, [eqpId, logsLoading, mergedLogs, typeFilters, selectedTipGroups]);

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
  };
}
