// 파일 경로: src/features/line-dashboard/hooks/useLineHistoryData.js
import { useMemo, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"

import { buildBackendUrl } from "@/lib/api"
import { lineDashboardQueryKeys } from "../api/queryKeys"

const DATE_ONLY_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
})
const KST_OFFSET = "+09:00"

function hasPositiveValue(records, key) {
  return (
    Array.isArray(records) &&
    records.some((record) => (Number(record?.[key] ?? 0) || 0) > 0)
  )
}

function formatKstDateOnly(value) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  const time = date.getTime()
  if (Number.isNaN(time)) return null
  return DATE_ONLY_FORMATTER.format(date)
}

function calcRangeDays(fromValue, toValue) {
  if (!fromValue || !toValue) return null
  const start = new Date(`${fromValue}T00:00:00${KST_OFFSET}`)
  const end = new Date(`${toValue}T00:00:00${KST_OFFSET}`)
  const startMs = start.getTime()
  const endMs = end.getTime()
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null
  const diff = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)) + 1)
  return diff
}

export function useLineHistoryData({ lineId, dateRange }) {
  const { fromValue, toValue, rangeDays } = useMemo(() => {
    const normalizedFrom = formatKstDateOnly(dateRange?.from)
    const normalizedTo = formatKstDateOnly(dateRange?.to)
    return {
      fromValue: normalizedFrom,
      toValue: normalizedTo,
      rangeDays: calcRangeDays(normalizedFrom, normalizedTo),
    }
  }, [dateRange])

  const historyQuery = useQuery({
    queryKey: lineDashboardQueryKeys.history(lineId ?? null, {
      from: fromValue,
      to: toValue,
    }),
    enabled: Boolean(lineId && fromValue && toValue && rangeDays),
    queryFn: async () => {
      const isWithinRange = (value) => {
        if (!fromValue || !toValue) return true
        const key = formatKstDateOnly(value)
        if (!key) return false
        return key >= fromValue && key <= toValue
      }

      const filterRecords = (records) =>
        Array.isArray(records) ? records.filter((record) => isWithinRange(record?.date)) : []

      const params = new URLSearchParams({ lineId: String(lineId) })
      params.set("rangeDays", String(rangeDays))
      params.set("from", fromValue)
      params.set("to", toValue)

      const endpoint = buildBackendUrl("/api/v1/line-dashboard/history", params)
      const response = await fetch(endpoint, { credentials: "include" })

      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        const message =
          typeof payload?.error === "string"
            ? payload.error
            : "Failed to load history data"
        throw new Error(message)
      }

      const filteredTotals = filterRecords(payload?.totals)
      const filteredBreakdowns =
        payload?.breakdowns && typeof payload.breakdowns === "object"
          ? Object.fromEntries(
              Object.entries(payload.breakdowns).map(([key, records]) => [
                key,
                filterRecords(records),
              ]),
            )
          : {}

      return {
        ...payload,
        totals: filteredTotals,
        breakdowns: filteredBreakdowns,
      }
    },
  })

  const refresh = useCallback(() => {
    if (!lineId || !fromValue || !toValue || !rangeDays) {
      return Promise.resolve({ data: null })
    }
    return historyQuery.refetch()
  }, [historyQuery, lineId, fromValue, toValue, rangeDays])

  const totalsData = useMemo(() => historyQuery.data?.totals ?? [], [historyQuery.data])
  const breakdownRecordsByDimension = useMemo(
    () => historyQuery.data?.breakdowns ?? {},
    [historyQuery.data]
  )

  const hasSendJiraData = useMemo(
    () =>
      hasPositiveValue(totalsData, "sendJiraCount") ||
      Object.values(breakdownRecordsByDimension).some((records) =>
        hasPositiveValue(records, "sendJiraCount")
      ),
    [totalsData, breakdownRecordsByDimension]
  )

  return {
    data: historyQuery.data ?? null,
    isLoading: historyQuery.isFetching,
    error: historyQuery.error ? (historyQuery.error instanceof Error ? historyQuery.error.message : String(historyQuery.error)) : null,
    totalsData,
    breakdownRecordsByDimension,
    hasSendJiraData,
    refresh,
  }
}
