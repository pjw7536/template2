// 파일 경로: src/features/line-dashboard/hooks/useLineDashboardData.js
import { useEffect, useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"

import { buildBackendUrl } from "@/lib/api"
import { lineDashboardQueryKeys } from "../api/queryKeys"

function normalizeError(error) {
  if (!error) return null
  if (error instanceof Error) return error.message
  return String(error)
}

export function useLineDashboardData(initialLineId = "") {
  const [lineId, setLineId] = useState(initialLineId ?? "")

  useEffect(() => {
    setLineId(initialLineId ?? "")
  }, [initialLineId])

  const summaryQuery = useQuery({
    queryKey: lineDashboardQueryKeys.summary(lineId || null),
    queryFn: async () => {
      const endpoint = buildBackendUrl("/api/v1/line-dashboard/summary", { lineId })
      const response = await fetch(endpoint, { credentials: "include" })
      const payload = await response.json().catch(() => ({}))

      if (!response.ok) {
        const message =
          typeof payload?.error === "string"
            ? payload.error
            : `Failed to load summary (${response.status})`
        throw new Error(message)
      }

      return payload
    },
    enabled: Boolean(lineId),
  })

  const refresh = useCallback(() => {
    if (!lineId) return Promise.resolve({ data: null })
    return summaryQuery.refetch()
  }, [lineId, summaryQuery])

  const status = {
    isLoading: summaryQuery.isFetching && Boolean(lineId),
    error: normalizeError(summaryQuery.error),
  }

  return {
    lineId,
    setLineId,
    summary: summaryQuery.data ?? null,
    refresh,
    status,
  }
}
