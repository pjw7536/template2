// src/features/timeline/components/CtttmTimeline.jsx
import React, { useMemo } from "react";
import BaseTimeline from "./BaseTimeline";
import { processData } from "../utils/timelineUtils";
import { makeGroupLabel } from "../utils/groupLabel";

export default function CtttmTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  ctttmLogs = [],
}) {
  const groups = useMemo(
    () => [
      {
        id: "CTTTM",
        content: makeGroupLabel("CTTTM", "CTTTM"),
        className: "custom-group-label",
        order: 1,
      },
    ],
    []
  );

  const items = useMemo(() => processData("CTTTM", ctttmLogs), [ctttmLogs]);

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

  // CTTTM 범례 항목
  const legendItems = [
    { state: "TTM_FAIL", color: "bg-red-600", label: "TTM_FAIL" },
    { state: "TTM_WARN", color: "bg-yellow-600", label: "TTM_WARN" },
  ];

  return (
    <BaseTimeline
      groups={groups}
      items={items}
      options={options}
      title="⚠️ CTTTM"
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
