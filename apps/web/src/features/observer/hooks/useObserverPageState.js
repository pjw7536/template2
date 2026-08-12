import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  DEFAULT_TYPE_FILTERS,
} from "../utils/constants";
import {
  buildLogDateRangeOptions,
  getDefaultLogRange,
  getLogRangeFromSearchParams,
  normalizeLogRange,
} from "../utils/logDateRange";
import {
  buildLogRangeSearch,
  getObserverEquipmentPath,
  isObserverEquipmentPath,
} from "../utils/observerLocation";
import {
  clearObserverEvidenceSearch,
  getObserverEvidenceNavigation,
  matchesObserverEvidence,
} from "../utils/observerEvidence";
import { useObserverSelectionStore } from "../store/useObserverSelectionStore";
import { useObserverStore } from "../store/useObserverStore";
import { useObserverLogs } from "./useObserverLogs";
import { useObserverLogDetailQuery } from "./useObserverLogDetailQuery";
import { useObserverAssistantContext } from "./useObserverAssistantContext";
import { useEquipmentInfoQuery } from "./useEquipmentInfoQuery";
import {
  getEnabledLogKeys,
  OBSERVER_LOG_CONFIG,
} from "../utils/logPagination";
import { transformLogsToTableData } from "../utils/dataTransformers";
import { useObserverEvidenceLogQuery } from "./useObserverEvidenceLogQuery";

/**
 * ObserverPage에서 흩어져 있던 상태/파생 데이터를 한 곳에 모아둔 훅.
 * - URL 검증 및 동기화
 * - 드릴다운/Observer 전용 전역 상태
 * - 테이블/Observer에 필요한 파생 데이터 계산
 */
export function useObserverPageState(params) {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    lineId,
    sdwtId,
    prcGroup,
    eqpId,
    setLine,
    setSdwt,
    setPrcGroup,
    setEqp,
    selectedRow,
    setSelectedRow,
    resetSelection,
  } = useObserverSelectionStore();

  const {
    showLegend,
    selectedTipGroups,
    setShowLegend,
    setSelectedTipGroups,
  } = useObserverStore();

  // 페이지 로컬 UI 상태
  const evidenceNavigation = useMemo(
    () => getObserverEvidenceNavigation(new URLSearchParams(location.search)),
    [location.search]
  );
  const appliedEvidenceSelectionKeyRef = useRef("");
  const [typeFilters, setTypeFilters] = useState(() => ({
    ...DEFAULT_TYPE_FILTERS,
  }));
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [logRange, setLogRange] = useState(() => {
    const initialRange = getLogRangeFromSearchParams(
      new URLSearchParams(location.search)
    );
    return initialRange || getDefaultLogRange();
  });
  const logQueryOptions = useMemo(
    () => buildLogDateRangeOptions(logRange),
    [logRange]
  );

  useEffect(() => {
    if (!evidenceNavigation) return;
    const evidenceFilterType = OBSERVER_LOG_CONFIG.find(
      ({ logKey }) => logKey === evidenceNavigation.logKey
    )?.filterType;
    if (evidenceFilterType) {
      setTypeFilters((currentFilters) =>
        currentFilters[evidenceFilterType]
          ? currentFilters
          : { ...currentFilters, [evidenceFilterType]: true }
      );
    }
    if (evidenceNavigation.tipGroups.length) {
      setSelectedTipGroups(evidenceNavigation.tipGroups);
    }
  }, [evidenceNavigation, setSelectedTipGroups]);

  // URL 파라미터 검증 및 상태 반영 (과도한 파일 분리를 줄이기 위해 이 훅 안에서 처리)
  const [validationError, setValidationError] = useState(null);
  const [appliedEquipmentRouteId, setAppliedEquipmentRouteId] = useState("");
  const shouldValidateEqpOnly = Boolean(params.eqpId && !params.lineId);
  const {
    data: equipmentInfo,
    isFetching: isEquipmentInfoFetching,
    isError: isEquipmentInfoError,
    error: equipmentInfoError,
  } = useEquipmentInfoQuery(params.eqpId, { enabled: shouldValidateEqpOnly });

  const isValidating = shouldValidateEqpOnly && isEquipmentInfoFetching;
  const hasValidationResult = !shouldValidateEqpOnly || !isEquipmentInfoFetching;

  useEffect(() => {
    const nextRange = getLogRangeFromSearchParams(
      new URLSearchParams(location.search)
    );
    if (!nextRange) {
      const nextSearch = buildLogRangeSearch(location.search, logQueryOptions);
      if (!nextSearch) return;

      navigate(
        {
          pathname: location.pathname,
          search: nextSearch,
          hash: location.hash,
        },
        { replace: true }
      );
      return;
    }

    setLogRange((currentRange) => {
      const current = normalizeLogRange(currentRange);
      if (
        current.startDaysAgo === nextRange.startDaysAgo &&
        current.endDaysAgo === nextRange.endDaysAgo
      ) {
        return currentRange;
      }

      return nextRange;
    });
  }, [
    location.hash,
    location.pathname,
    location.search,
    logQueryOptions,
    navigate,
  ]);

  const handleLogRangeChange = useCallback((nextRangeValue) => {
    const nextRange = normalizeLogRange(nextRangeValue);
    const nextSearch = buildLogRangeSearch(
      location.search,
      buildLogDateRangeOptions(nextRange)
    );
    if (!nextSearch) return;

    navigate(
      {
        pathname: location.pathname,
        search: nextSearch,
        hash: location.hash,
      },
      { replace: true }
    );
  }, [
    location.hash,
    location.pathname,
    location.search,
    navigate,
  ]);

  useEffect(() => {
    if (!shouldValidateEqpOnly) {
      setValidationError(null);
      setAppliedEquipmentRouteId("");
      return;
    }

    if (equipmentInfo) {
      setValidationError(null);
      setLine(equipmentInfo.lineId);
      setSdwt(equipmentInfo.sdwtId);
      setPrcGroup(equipmentInfo.prcGroup);
      setEqp(params.eqpId);
      setAppliedEquipmentRouteId(params.eqpId);
      return;
    }

    if (isEquipmentInfoError || (!equipmentInfo && !isEquipmentInfoFetching)) {
      const message =
        equipmentInfoError instanceof Error
          ? equipmentInfoError.message
          : "유효하지 않은 EQP ID입니다.";
      setValidationError(message);
      const timeoutId = setTimeout(() => navigate("/observer"), 1500);
      return () => clearTimeout(timeoutId);
    }
  }, [
    equipmentInfo,
    equipmentInfoError,
    isEquipmentInfoError,
    isEquipmentInfoFetching,
    navigate,
    params.eqpId,
    setEqp,
    setLine,
    setPrcGroup,
    setSdwt,
    shouldValidateEqpOnly,
  ]);

  // 선택한 eqpId와 URL을 동기화
  useEffect(() => {
    const isEquipmentRoutePending = Boolean(
      params.eqpId && appliedEquipmentRouteId !== params.eqpId
    );
    if (isValidating || !hasValidationResult || isEquipmentRoutePending) return;

    const currentPath = location.pathname;
    const isParamRoute = isObserverEquipmentPath(currentPath);

    if (eqpId) {
      const newPath = getObserverEquipmentPath(eqpId);
      if (currentPath !== newPath) {
        navigate(
          {
            pathname: newPath,
            search: clearObserverEvidenceSearch(location.search),
            hash: location.hash,
          },
          { replace: true }
        );
      }
    } else if (isParamRoute) {
      navigate(
        {
          pathname: getObserverEquipmentPath(null),
          search: clearObserverEvidenceSearch(location.search),
          hash: location.hash,
        },
        { replace: true }
      );
    }
  }, [
    eqpId,
    appliedEquipmentRouteId,
    hasValidationResult,
    isValidating,
    location.hash,
    location.pathname,
    location.search,
    navigate,
    params.eqpId,
  ]);

  useEffect(() => {
    resetSelection();
  }, [eqpId, resetSelection]);

  // EQP가 바뀔 때마다 TIP 필터를 초기화하여 예전 선택이 남지 않도록 한다.
  useEffect(() => {
    if (eqpId && !evidenceNavigation?.tipGroups.length) {
      setSelectedTipGroups(["__ALL__"]);
    }
  }, [eqpId, evidenceNavigation, setSelectedTipGroups]);

  const handleFilterChange = (event) => {
    const { name, checked } = event.target;
    setTypeFilters((prev) => ({ ...prev, [name]: checked }));
  };

  const logs = useObserverLogs(
    eqpId,
    typeFilters,
    selectedTipGroups,
    logQueryOptions
  );
  const residentEvidenceLog = useMemo(
    () =>
      evidenceNavigation
        ? logs.mergedLogs.find((log) =>
            matchesObserverEvidence(log, evidenceNavigation.evidenceId)
          ) || null
        : null,
    [evidenceNavigation, logs.mergedLogs]
  );
  const isEvidenceEquipmentPending = Boolean(
    evidenceNavigation && params.eqpId && eqpId !== params.eqpId
  );
  const evidenceLogQuery = useObserverEvidenceLogQuery(
    isEvidenceEquipmentPending ? "" : eqpId,
    evidenceNavigation,
    { enabled: Boolean(evidenceNavigation && !residentEvidenceLog) }
  );
  const fetchedEvidenceLog = useMemo(() => {
    if (!evidenceLogQuery.data) return null;
    return {
      ...evidenceLogQuery.data,
      detailId:
        evidenceLogQuery.data.detailId ?? evidenceLogQuery.data.sourceId,
    };
  }, [evidenceLogQuery.data]);
  const evidenceLog = residentEvidenceLog || fetchedEvidenceLog;
  const visibleTableData = useMemo(() => {
    if (!fetchedEvidenceLog || residentEvidenceLog) return logs.tableData;
    const [evidenceRow] = transformLogsToTableData(
      [fetchedEvidenceLog],
      { [fetchedEvidenceLog.logType]: true },
      ["__ALL__"]
    );
    if (!evidenceRow) return logs.tableData;
    return [
      evidenceRow,
      ...logs.tableData.filter(
        (row) => String(row.id) !== String(evidenceRow.id)
      ),
    ];
  }, [fetchedEvidenceLog, logs.tableData, residentEvidenceLog]);
  useEffect(() => {
    if (!evidenceNavigation) {
      appliedEvidenceSelectionKeyRef.current = "";
      return;
    }
    if (!evidenceLog) return;

    const evidenceSelectionKey = `${eqpId}:${evidenceNavigation.evidenceId}:${evidenceLog.id}`;
    if (appliedEvidenceSelectionKeyRef.current === evidenceSelectionKey) return;

    // 근거 링크 진입 시에만 자동 선택하고 이후 사용자 선택은 유지합니다.
    appliedEvidenceSelectionKeyRef.current = evidenceSelectionKey;
    setSelectedRow(evidenceLog.id, "assistant");
  }, [eqpId, evidenceLog, evidenceNavigation, setSelectedRow]);
  const evidenceNavigationStatus = evidenceNavigation
    ? {
        evidenceId: evidenceNavigation.evidenceId,
        status: evidenceLog
          ? "found"
          : isEvidenceEquipmentPending ||
              logs.logsLoading ||
              evidenceLogQuery.isFetching
            ? "loading"
            : evidenceLogQuery.isError && evidenceLogQuery.error?.status !== 404
              ? "error"
              : "not_found",
        retry: evidenceLogQuery.refetch,
      }
    : null;
  const analysisScope = useMemo(
    () => ({
      eqpId,
      ...logQueryOptions,
      logTypes: getEnabledLogKeys(typeFilters),
      tipGroups: selectedTipGroups,
    }),
    [eqpId, logQueryOptions, selectedTipGroups, typeFilters]
  );
  useObserverAssistantContext(analysisScope);
  const selectedCompactLog =
    logs.mergedLogs.find((log) => String(log.id) === String(selectedRow)) ||
    (evidenceLog && String(evidenceLog.id) === String(selectedRow)
      ? evidenceLog
      : null) ||
    null;
  const selectedLogDetail = useObserverLogDetailQuery(
    eqpId,
    selectedCompactLog
  );
  const selectedLog = selectedCompactLog
    ? {
        ...selectedCompactLog,
        ...(selectedLogDetail.data || {}),
      }
    : null;

  return {
    selection: {
      lineId,
      sdwtId,
      prcGroup,
      eqpId,
      setLine,
      setSdwt,
      setPrcGroup,
      setEqp,
      selectedRow,
    },
    observerPrefs: {
      showLegend,
      selectedTipGroups,
      setShowLegend,
      setSelectedTipGroups,
    },
    filters: {
      typeFilters,
      handleFilterChange,
    },
    settings: {
      isSettingsOpen,
      setIsSettingsOpen,
      logRange,
      setLogRange: handleLogRangeChange,
    },
    validation: { isValidating, validationError },
    logs: {
      ...logs,
      tableData: visibleTableData,
    },
    selectedLog,
    selectedLogDetail: {
      isLoading:
        Boolean(selectedCompactLog) &&
        selectedLogDetail.isFetching &&
        !selectedLogDetail.data,
      error: selectedLogDetail.isError ? selectedLogDetail.error : null,
      refetch: selectedLogDetail.refetch,
    },
    evidenceNavigationStatus,
    observerReady: Boolean(eqpId),
  };
}
