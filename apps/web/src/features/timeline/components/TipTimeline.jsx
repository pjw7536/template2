// src/features/timeline/components/TipTimeline.jsx
import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions, processData } from "../utils/timelineUtils";
import { makeTipGroupLabel } from "../utils/groupLabel";
import { getTipGroupKey } from "../utils/tipUtils";
import { timelineLegends } from "../utils/timelineLegends";

const GROUP_HEIGHT = 28;
const TIME_AXIS_HEIGHT = 46;

export default function TipTimeline({
  tipLogs = [],
  totalTipLogCount,
  range,
  showLegend,
  showTimeAxis = true,
}) {
  const totalCount =
    typeof totalTipLogCount === "number" ? totalTipLogCount : tipLogs.length;
  const hasAnyTipLogs = totalCount > 0;
  const hasVisibleTipLogs = tipLogs.length > 0;

  const groupMap = new Map();
  const groupedLogs = new Map();

  tipLogs.forEach((log) => {
    const groupKey = `TIP_${getTipGroupKey(log)}`;

    if (!groupMap.has(groupKey)) {
      groupMap.set(groupKey, {
        id: groupKey,
        content: makeTipGroupLabel(log.process, log.step, log.ppid),
        className: "custom-group-label tip-group",
        order: 100 + groupMap.size,
        title: `Line: ${log.lineId || "N/A"} | Process: ${
          log.process || "N/A"
        } | Step: ${log.step || "N/A"} | PPID: ${log.ppid || "N/A"}`,
      });
    }

    if (!groupedLogs.has(groupKey)) {
      groupedLogs.set(groupKey, []);
    }
    groupedLogs.get(groupKey).push(log);
  });

  const groups = Array.from(groupMap.values()).sort((a, b) => a.order - b.order);

  const items = [];
  groupedLogs.forEach((logs, groupKey) => {
    const processed = processData("TIP", logs, true);
    processed.forEach((item) => {
      items.push({ ...item, group: groupKey });
    });
  });

  const calculatedHeight =
    groups.length === 0 ? TIME_AXIS_HEIGHT : GROUP_HEIGHT * groups.length + TIME_AXIS_HEIGHT;

  const options = buildFixedHeightOptions(range, calculatedHeight, {
    groupHeightMode: "fixed",
  });

  if (!hasAnyTipLogs || !hasVisibleTipLogs) {
    return (
      <TimelineEmptyState
        title="🔧 TIP 로그"
        headerNote={!hasAnyTipLogs ? "로그 없음" : "선택된 그룹 없음"}
        message={!hasAnyTipLogs ? "TIP 로그가 없습니다" : "표시할 TIP 그룹을 선택하세요"}
      />
    );
  }

  return (
    <BaseTimeline
      key={`tip-timeline-${groups.length}`}
      groups={groups}
      items={items}
      options={options}
      title={`🔧 TIP 로그 (${groups.length}개 그룹)`}
      showTimeAxis={showTimeAxis}
      className="tip-timeline"
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.TIP} /> : null
      }
    />
  );
}
