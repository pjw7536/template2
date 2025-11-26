// src/features/line-dashboard/history/useLineHistoryData.js
import * as React from "react"

import { buildBackendUrl } from "@/lib/api"

const DATE_ONLY_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
})

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

function calcRangeDays(dateRange) {
  const { from, to } = dateRange ?? {}
  if (!from || !to) return null
  const start = new Date(from)
  const end = new Date(to)
  const diff = Math.max(1, Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1)
  return diff
}

export function useLineHistoryData({ lineId, dateRange }) {
  const [state, setState] = React.useState({
    data: null,
    isLoading: false,
    error: null,
  })
  const [refreshToken, setRefreshToken] = React.useState(0)

  const rangeDays = React.useMemo(() => calcRangeDays(dateRange), [dateRange])

  React.useEffect(() => {
    setState({ data: null, isLoading: true, error: null })
  }, [lineId])

  React.useEffect(() => {
    const controller = new AbortController()

    async function load() {
      const fromValue = formatKstDateOnly(dateRange?.from)
      const toValue = formatKstDateOnly(dateRange?.to)

      if (!lineId || !fromValue || !toValue || !rangeDays) {
        setState((prev) => ({ ...prev, isLoading: false }))
        return
      }

      setState((previous) => ({ ...previous, isLoading: true, error: null }))

      try {
        const params = new URLSearchParams({ lineId: String(lineId) })
        params.set("rangeDays", String(rangeDays))
        params.set("from", fromValue)
        params.set("to", toValue)

        const endpoint = buildBackendUrl("/line-dashboard/history", params)
        const response = await fetch(endpoint, {
          signal: controller.signal,
          credentials: "include",
        })

        if (!response.ok) {
          const payload = await response.json().catch(() => ({}))
          const message =
            typeof payload?.error === "string"
              ? payload.error
              : "Failed to load history data"
          throw new Error(message)
        }

        const payload = await response.json()
        setState({ data: payload, isLoading: false, error: null })
      } catch (error) {
        if (controller.signal.aborted) return
        const message =
          error instanceof Error ? error.message : "Failed to load history data"
        setState({ data: null, isLoading: false, error: message })
      }
    }

    load()

    return () => controller.abort()
  }, [lineId, dateRange, rangeDays, refreshToken])

  const refresh = React.useCallback(() => {
    setRefreshToken((value) => value + 1)
  }, [])

  const totalsData = React.useMemo(() => state.data?.totals ?? [], [state.data])
  const breakdownRecordsByDimension = React.useMemo(
    () => state.data?.breakdowns ?? {},
    [state.data]
  )

  const hasSendJiraData = React.useMemo(
    () =>
      hasPositiveValue(totalsData, "sendJiraCount") ||
      Object.values(breakdownRecordsByDimension).some((records) =>
        hasPositiveValue(records, "sendJiraCount")
      ),
    [totalsData, breakdownRecordsByDimension]
  )

  return {
    data: state.data,
    isLoading: state.isLoading,
    error: state.error,
    totalsData,
    breakdownRecordsByDimension,
    hasSendJiraData,
    refresh,
  }
}
