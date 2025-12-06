import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { AdjustmentsHorizontalIcon } from "@heroicons/react/24/outline";
import { LoadingSpinner } from "../components/Loaders";
import { useTimelineSelectionStore } from "../store/useTimelineSelectionStore";
import { DEFAULT_TYPE_FILTERS } from "../utils/constants";
import { useTimelineStore } from "../store/timelineStore";
import TimelineBoard from "../components/TimelineBoard";
import DataLogSection from "../components/DataLogSection";
import LogViewerSection from "../components/LogViewerSection";
import ShareButton from "../components/ShareButton";
import LogDetailSection from "../components/LogDetailSection";
import TimelineSettings from "../components/TimelineSettings";
import { useUrlValidation } from "../hooks/useUrlValidation";
import { useUrlSync } from "../hooks/useUrlSync";
import { useTimelineLogs } from "../hooks/useTimelineLogs";

export default function TimelinePage() {
  const params = useParams();

  // Selection Store (드릴다운 상태와 선택 상태)
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
  } = useTimelineSelectionStore();

  // Timeline Store (timeline 전용 상태)
  const { showLegend, selectedTipGroups, setShowLegend, setSelectedTipGroups } =
    useTimelineStore();

  // URL 검증
  const { isValidating, validationError, isUrlInitialized } = useUrlValidation(
    params,
    lineId,
    eqpId,
    setLine,
    setSdwt,
    setPrcGroup,
    setEqp
  );

  // useEffect를 추가하여 eqpId가 변경될 때마다 selectedTipGroups를 초기화
  useEffect(() => {
    if (eqpId) {
      // eqpId가 변경될 때마다 TIP 그룹을 전체 선택 상태로 초기화
      setSelectedTipGroups(["__ALL__"]);
    }
  }, [eqpId, setSelectedTipGroups]);

  // URL 동기화
  useUrlSync(lineId, eqpId, isValidating, isUrlInitialized);

  // 로컬 상태 (timeline과 관련 없는 상태들)
  const [typeFilters, setTypeFilters] = useState(() => ({
    ...DEFAULT_TYPE_FILTERS,
  }));
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // 필터 핸들러
  const handleFilter = (e) =>
    setTypeFilters((prev) => ({ ...prev, [e.target.name]: e.target.checked }));

  const {
    logsLoading,
    logsWithDuration,
    mergedLogs,
    tableData,
    filteredTipLogs,
  } = useTimelineLogs(eqpId, typeFilters, selectedTipGroups);

  // 선택된 로그 (병합된 로그에서 찾기)
  const selectedLog = mergedLogs.find(
    (log) => String(log.id) === String(selectedRow)
  );

  const timelineReady = Boolean(eqpId);

  // 검증 중일 때 로딩 표시
  if (isValidating) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <LoadingSpinner />
      </div>
    );
  }

  // 검증 에러 표시
  if (validationError) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-center">
          <p className="text-red-500 mb-2">{validationError}</p>
          <p className="text-gray-500">잠시 후 메인 페이지로 이동합니다...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-row h-[calc(100vh-100px)] mt-3 gap-2">
      {/* 왼쪽 패널 */}
      <div className="flex flex-col h-full min-h-0 w-[35%] gap-2">
        <LogViewerSection
          lineId={lineId}
          sdwtId={sdwtId}
          prcGroup={prcGroup}
          eqpId={eqpId}
          setLine={setLine}
          setSdwt={setSdwt}
          setPrcGroup={setPrcGroup}
          setEqp={setEqp}
        />

        <div className="flex-1 min-h-0 flex flex-col gap-2">
          <DataLogSection
            eqpId={eqpId}
            logsLoading={logsLoading}
            tableData={tableData}
            typeFilters={typeFilters}
            handleFilter={handleFilter}
          />

          <section className="border border-border bg-card shadow-sm rounded-xl p-3 flex-[1] min-h-0 flex flex-col overflow-auto min-h-[180px] max-h-[320px]">
            <h2 className="text-md font-bold text-foreground pb-1">
              📝 Log Detail
            </h2>
            <hr className="my-2 border-border" />
            <LogDetailSection log={selectedLog} />
          </section>
        </div>
      </div>

      {/* 오른쪽 패널 + 설정 패널 포함 */}
      <div className="flex flex-row h-full w-[65%]">
        {/* 타임라인 패널 */}
        <div className="flex flex-col flex-1 overflow-hidden border border-border bg-card shadow-sm rounded-xl pl-4 pr-1 transition-all duration-300 ease-in-out">
          <div className="flex items-center justify-between my-5">
            <div className="flex items-center gap-2">
              <h2 className="text-md font-bold text-foreground">
                📊 Timeline
              </h2>
              {lineId && eqpId && <ShareButton />}
            </div>

            {eqpId && !logsLoading && (
              <button
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className="mr-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-foreground bg-card border border-border rounded-md hover:bg-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4" />
                설정
              </button>
            )}
          </div>

          <hr className="border-border" />

          {!eqpId && !logsLoading ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-center text-slate-600 dark:text-slate-400">
                EQP를 선택하세요.
              </p>
            </div>
          ) : logsLoading ? (
            <div className="flex items-center justify-center h-full">
              <LoadingSpinner />
            </div>
          ) : (
            <TimelineBoard
              lineId={lineId}
              eqpId={eqpId}
              showLegend={showLegend}
              selectedTipGroups={selectedTipGroups}
              eqpLogs={logsWithDuration.eqpLogs}
              tipLogs={logsWithDuration.tipLogs}
              ctttmLogs={logsWithDuration.ctttmLogs}
              racbLogs={logsWithDuration.racbLogs}
              jiraLogs={logsWithDuration.jiraLogs}
              typeFilters={typeFilters}
            />
          )}
        </div>

        {/* 설정 패널 */}
        {timelineReady && !logsLoading && (
          <TimelineSettings
            isOpen={isSettingsOpen}
            onClose={() => setIsSettingsOpen(false)}
            showLegend={showLegend}
            selectedTipGroups={selectedTipGroups}
            onLegendToggle={(e) => setShowLegend(e.target.checked)} // 수정
            onTipFilterChange={setSelectedTipGroups}
            tipLogs={filteredTipLogs}
          />
        )}
      </div>
    </div>
  );
}
