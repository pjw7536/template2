// src/features/line-dashboard/hooks/useLineOptionsQuery.js
// 라인 선택 드롭다운에서 사용할 옵션을 React Query로 관리합니다.
// - getDistinctLineIds API를 감싼 쿼리 훅으로, feature 외부(레이아웃)에서도 재사용됩니다.

import { useQuery } from "@tanstack/react-query"

import { lineDashboardQueryKeys } from "../api/query-keys"
import { getDistinctLineIds } from "../api/get-line-ids"

function toLineOptions(rawLineIds) {
  if (!Array.isArray(rawLineIds)) return []
  // 중복 제거 후 문자열 배열만 유지
  const normalized = rawLineIds
    .filter((value) => typeof value === "string" && value.trim().length > 0)
    .map((value) => value.trim())

  return Array.from(new Set(normalized))
}

export function useLineOptionsQuery() {
  return useQuery({
    queryKey: lineDashboardQueryKeys.lineOptions(),
    queryFn: getDistinctLineIds,
    select: toLineOptions,
    // Keep the landing entry page from "refreshing" when returning to the tab
    // by disabling automatic refetch on window focus.
    refetchOnWindowFocus: false,
  })
}
