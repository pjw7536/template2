// src/features/timeline/components/TimelineBoard.jsx
import React from "react";
import EqpTimeline from "./EqpTimeline";
import TipTimeline from "./TipTimeline";
import CtttmTimeline from "./CtttmTimeline";
import RacbTimeline from "./RacbTimeline";
import JiraTimeline from "./JiraTimeline";
import { useTimelineRange } from "../hooks/useTimelineRange";

export default function TimelineBoard({
  lineId,
  eqpId,
  showLegend,
  selectedTipGroups,
  eqpLogs = [],
  tipLogs = [],
  ctttmLogs = [],
  racbLogs = [],
  jiraLogs = [],
  typeFilters,
}) {
  // 모든 로그를 합쳐서 range 계산
  const allLogs = [
    ...eqpLogs,
    ...tipLogs,
    ...ctttmLogs,
    ...racbLogs,
    ...jiraLogs,
  ];
  const range = useTimelineRange(allLogs);

  // 아무 데이터도 없는 경우
  if (allLogs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 dark:text-slate-400">
        표시할 로그 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      {/* 타임라인이 많아질 때를 위한 스크롤 컨테이너 - absolute로 부모의 전체 영역을 차지 */}
      <div className="absolute inset-0 overflow-y-auto space-y-0 scroll-smooth pr-5 mt-5 mb-10 z-[1]">
        {/* EQP 타임라인 */}
        {typeFilters?.EQP && (
          <EqpTimeline
            lineId={lineId}
            eqpId={eqpId}
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            eqpLogs={eqpLogs}
          />
        )}

        {/* TIP 타임라인 */}
        {typeFilters?.TIP && (
          <TipTimeline
            lineId={lineId}
            eqpId={eqpId}
            range={range}
            showLegend={showLegend}
            selectedTipGroups={selectedTipGroups}
            showTimeAxis={true}
            tipLogs={tipLogs}
          />
        )}

        {/* CTTTM 타임라인 */}
        {typeFilters?.CTTTM && (
          <CtttmTimeline
            lineId={lineId}
            eqpId={eqpId}
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            ctttmLogs={ctttmLogs}
          />
        )}

        {/* RACB 타임라인 */}
        {typeFilters?.RACB && (
          <RacbTimeline
            lineId={lineId}
            eqpId={eqpId}
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            racbLogs={racbLogs}
          />
        )}

        {/* JIRA 타임라인 */}
        {typeFilters?.JIRA && (
          <JiraTimeline
            lineId={lineId}
            eqpId={eqpId}
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            jiraLogs={jiraLogs}
          />
        )}
      </div>
    </div>
  );
}
