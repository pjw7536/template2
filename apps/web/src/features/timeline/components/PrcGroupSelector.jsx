// src/features/timeline/components/drilldown/PrcGroupSelector.jsx
import React from "react";
import { usePrcGroups } from "../hooks/useLineQueries";
import { LoadingSpinner } from "./Loaders";

/**
 * PRC Group 드롭다운
 */
export default function PrcGroupSelector({
  lineId,
  sdwtId,
  prcGroup,
  setPrcGroup,
}) {
  const { data: prcGroups = [], isLoading } = usePrcGroups(lineId, sdwtId);

  if (!lineId || !sdwtId)
    return (
      <select
        disabled
        className="w-full px-3 py-1.5 border rounded-lg bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 h-8"
      >
        <option>PRC Group 선택…</option>
      </select>
    );

  if (isLoading) return <LoadingSpinner />;

  return (
    <select
      value={prcGroup}
      onChange={(e) => setPrcGroup(e.target.value)}
      className="w-full px-3 py-1.5 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-xs dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-600 h-8"
      disabled={prcGroups.length === 0}
    >
      <option value="">PRC Group 선택…</option>
      {prcGroups.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
