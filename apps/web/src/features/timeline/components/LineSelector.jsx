// src/features/timeline/components/drilldown/LineSelector.jsx
import React from "react";
import { useLines } from "../hooks/useLineQueries";
import { LoadingSpinner } from "./Loaders";

/**
 * 라인 목록 드롭다운
 */
export default function LineSelector({ lineId, setLineId }) {
  const { data: lines = [], isLoading } = useLines();

  if (isLoading) return <LoadingSpinner />;

  return (
    <select
      value={lineId}
      onChange={(e) => setLineId(e.target.value)}
      className="w-full px-3 py-1.5 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-xs dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-600 h-8"
    >
      <option value="">라인 선택…</option>
      {lines.map((l) => (
        <option key={l.id} value={l.id}>
          {l.name}
        </option>
      ))}
    </select>
  );
}
