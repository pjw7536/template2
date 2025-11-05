// src/features/line-dashboard/hooks/useLineDashboardData.js
"use client"

import * as React from "react"

import { buildBackendUrl } from "@/lib/api"

const createIdleStatus = () => ({ isLoading: false, error: null })

/**
 * 라인 대시보드 페이지에서 공통으로 사용하는 요약 데이터를 관리합니다.
 * - lineId가 바뀌면 내부 상태를 초기화하고
 * - refresh( ) 호출 시 최신 요약 정보를 /api에서 받아옵니다.
 */
export function useLineDashboardData(initialLineId = "") {
  const [lineId, setLineId] = React.useState(initialLineId)
  const [status, setStatus] = React.useState(createIdleStatus)
  const [summary, setSummary] = React.useState(null)

  React.useEffect(() => {
    setLineId(initialLineId)
    setSummary(null)
    setStatus(createIdleStatus())
  }, [initialLineId])

  const refresh = React.useCallback(
    async (overrideLineId) => {
      const targetLine = overrideLineId ?? lineId
      if (!targetLine) return

      setStatus({ isLoading: true, error: null })

      try {
        const endpoint = buildBackendUrl("/line-dashboard/summary", {
          lineId: targetLine,
        })
        const response = await fetch(endpoint)
        if (!response.ok) {
          throw new Error(`Failed to load summary (${response.status})`)
        }
        const payload = await response.json()
        setSummary(payload)
        setStatus(createIdleStatus())
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error"
        setStatus({ isLoading: false, error: message })
      }
    },
    [lineId]
  )

  return React.useMemo(
    () => ({ lineId, setLineId, summary, refresh, status }),
    [lineId, summary, refresh, status]
  )
}
