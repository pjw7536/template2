// src/features/timeline/components/RacbTimeline.jsx
import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions, processData } from "../utils/timelineUtils";
import { makeGroupLabel } from "../utils/groupLabel";
import { timelineLegends } from "../utils/timelineLegends";

const RACB_GROUP = {
  id: "RACB",
  content: makeGroupLabel("RACB", "RACB"),
  className: "custom-group-label",
  order: 1,
};

export default function RacbTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  racbLogs = [],
}) {
  const items = processData("RACB", racbLogs);

  const options = buildFixedHeightOptions(range, 76);

  if (racbLogs.length === 0) {
    return (
      <TimelineEmptyState title="🚨 RACB" message="RACB 로그가 없습니다" />
    );
  }

  return (
    <BaseTimeline
      groups={[RACB_GROUP]}
      items={items}
      options={options}
      title="🚨 RACB"
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.RACB} /> : null
      }
    />
  );
}
