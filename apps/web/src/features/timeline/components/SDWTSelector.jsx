// src/features/timeline/components/drilldown/SDWTSelector.jsx
import React from "react";
import { useSDWT } from "../hooks/useLineQueries";
import { LoadingSpinner } from "./Loaders";

/**
 * SDWT 드롭다운
 */
export default function SDWTSelector({ lineId, sdwtId, setSdwtId }) {
  const { data: sdwts = [], isLoading } = useSDWT(lineId);

  if (!lineId)
    return (
      <select
        disabled
        className="w-full px-3 py-1.5 border rounded-lg bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 h-8"
      >
        <option>SDWT 선택…</option>
      </select>
    );

  if (isLoading) return <LoadingSpinner />;

  return (
    <select
      value={sdwtId}
      onChange={(e) => setSdwtId(e.target.value)}
      className="w-full px-3 py-1.5 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-xs dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-600 h-8"
    >
      <option value="">SDWT 선택…</option>
      {sdwts.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
        </option>
      ))}
    </select>
  );
}
