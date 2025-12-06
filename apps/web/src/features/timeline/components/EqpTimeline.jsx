// src/features/timeline/components/EqpTimeline.jsx
import React, { useMemo } from "react";
import BaseTimeline from "./BaseTimeline";
import { processData } from "../utils/timelineUtils";
import { makeGroupLabel } from "../utils/groupLabel";

export default function EqpTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  eqpLogs = [],
}) {
  const groups = useMemo(
    () => [
      {
        id: "EQP",
        content: makeGroupLabel("EQP", "EQP 로그"),
        className: "custom-group-label",
        order: 1,
      },
    ],
    []
  );

  const items = useMemo(() => processData("EQP", eqpLogs, true), [eqpLogs]);

  const options = useMemo(
    () => ({
      stack: false,
      min: range.min,
      max: range.max,
      zoomMin: 60 * 60 * 1000,
      height: 75,
      minHeight: 28,
      maxHeight: 75,
      verticalScroll: false,
      horizontalScroll: false,
      align: "top",
      zoomFriction: 5,
    }),
    [range]
  );

  const legendItems = [
    { state: "RUN", color: "bg-blue-600", label: "RUN" },
    { state: "IDLE", color: "bg-green-600", label: "IDLE" },
    { state: "PM", color: "bg-yellow-600", label: "PM" },
    { state: "DOWN", color: "bg-red-600", label: "DOWN" },
  ];

  if (eqpLogs.length === 0) {
    return (
      <div className="timeline-container relative">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
            ⚙️ EQP 상태
          </h3>
        </div>
        <div
          className="flex items-center justify-center bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 h-[74px]"
        >
          <p className="text-sm text-slate-400 dark:text-slate-500">
            EQP 로그가 없습니다
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
      title="⚙️ EQP 상태"
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
