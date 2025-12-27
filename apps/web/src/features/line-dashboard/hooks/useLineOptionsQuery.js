// src/features/line-dashboard/hooks/useLineOptionsQuery.js
// 라인 선택 드롭다운에서 사용할 옵션을 React Query로 관리합니다.
// - account/line-sdwt-options 응답을 기반으로 line 목록만 추출합니다.

import { useQuery } from "@tanstack/react-query"

import { lineDashboardQueryKeys } from "../api/query-keys"
import { getLineSdwtOptions } from "../api/get-line-sdwt-options"

function toLineOptions(payload) {
  const rawLines = Array.isArray(payload?.lines) ? payload.lines : []
  const normalized = rawLines
    .map((line) => (typeof line?.lineId === "string" ? line.lineId.trim() : ""))
    .filter(Boolean)

  return Array.from(new Set(normalized))
}

export function useLineOptionsQuery(options = {}) {
  const { enabled = true } = options

  return useQuery({
    queryKey: lineDashboardQueryKeys.lineSdwtOptions(),
    queryFn: getLineSdwtOptions,
    select: toLineOptions,
    // Keep the home entry page from "refreshing" when returning to the tab
    // by disabling automatic refetch on window focus.
    refetchOnWindowFocus: false,
    enabled,
  })
}
