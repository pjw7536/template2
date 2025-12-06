// src/features/timeline/components/drilldown/EqpSelector.jsx
import React from "react";
import { useEquipments } from "../hooks/useLineQueries";
import { LoadingSpinner } from "./Loaders";

/**
 * EQP 드롭다운
 */
export default function EqpSelector({
  lineId,
  sdwtId,
  prcGroup,
  eqpId,
  setEqpId,
}) {
  // 데이터·상태 가져오기 - prcGroup 추가
  const { data: eqps = [], isLoading } = useEquipments(
    lineId,
    sdwtId,
    prcGroup
  );

  // Line, SDWT, PRC Group 모두 선택해야 활성화
  if (!lineId || !sdwtId || !prcGroup)
    return (
      <select
        disabled
        className="w-full px-3 py-1.5 border rounded-lg bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 h-8"
      >
        <option>EQP 선택…</option>
      </select>
    );

  if (isLoading) return <LoadingSpinner />;

  return (
    <select
      value={eqpId}
      onChange={(e) => setEqpId(e.target.value)}
      className="w-full px-3 py-1.5 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-xs dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-600 h-8"
      disabled={eqps.length === 0}
    >
      <option value="">EQP 선택…</option>
      {eqps.map((e) => (
        <option key={e.id} value={e.id}>
          {e.name}
        </option>
      ))}
    </select>
  );
}
