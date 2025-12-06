// src/features/timeline/components/JiraTimeline.jsx
import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions, processData } from "../utils/timelineUtils";
import { makeGroupLabel } from "../utils/groupLabel";
import { timelineLegends } from "../utils/timelineLegends";

const JIRA_GROUP = {
  id: "JIRA",
  content: makeGroupLabel("JIRA", "JIRA"),
  className: "custom-group-label",
  order: 1,
};

export default function JiraTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  jiraLogs = [],
}) {
  const items = processData("JIRA", jiraLogs);

  const options = buildFixedHeightOptions(range, 76);

  if (jiraLogs.length === 0) {
    return (
      <TimelineEmptyState title="📋 JIRA" message="JIRA 로그가 없습니다" />
    );
  }

  return (
    <BaseTimeline
      groups={[JIRA_GROUP]}
      items={items}
      options={options}
      title="📋 JIRA"
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.JIRA} /> : null
      }
    />
  );
}
