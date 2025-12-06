// src/features/timeline/components/JiraTimeline.jsx
import React, { useMemo } from "react";
import BaseTimeline from "./BaseTimeline";
import { processData } from "../utils/timelineUtils";
import { makeGroupLabel } from "../utils/groupLabel";

export default function JiraTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  jiraLogs = [],
}) {
  const groups = useMemo(
    () => [
      {
        id: "JIRA",
        content: makeGroupLabel("JIRA", "JIRA"),
        className: "custom-group-label",
        order: 1,
      },
    ],
    []
  );

  const items = useMemo(() => processData("JIRA", jiraLogs), [jiraLogs]);

  const options = useMemo(
    () => ({
      stack: false,
      min: range.min,
      max: range.max,
      zoomMin: 60 * 60 * 1000,
      height: 76,
      minHeight: 76,
      maxHeight: 76,
      verticalScroll: false,
    }),
    [range]
  );

  const legendItems = [
    { state: "ISSUED", color: "bg-blue-600", label: "ISSUED" },
    { state: "CLOSED", color: "bg-purple-600", label: "CLOSED" },
  ];

  if (jiraLogs.length === 0) {
    return (
      <div className="timeline-container relative">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
            📋 JIRA
          </h3>
        </div>
        <div
          className="flex items-center justify-center bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 h-[74px]"
        >
          <p className="text-sm text-slate-400 dark:text-slate-500">
            JIRA 로그가 없습니다
          </p>
        </div>
      </div>
    );
  }

  return (
    <BaseTimeline
      groups={groups}
      items={items}
      options={options}
      title="📋 JIRA"
      showTimeAxis={showTimeAxis}
      headerExtra={
        <div>
          {/* 범례 - showLegend가 true일 때만 표시 */}
          {showLegend && (
            <div className="flex items-center gap-3 px-2">
              <div className="flex gap-3">
                {legendItems.map(({ state, color, label }) => (
                  <div key={state} className="flex items-center gap-1">
                    <div className={`w-3 h-3 rounded ${color}`} />
                    <span className="text-xs text-slate-600 dark:text-slate-400">
                      {label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      }
    />
  );
}
