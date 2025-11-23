// src/features/line-dashboard/components/data-table/hooks/useStatusChart.js
import * as React from "react"

import { STATUS_COLORS, STATUS_LABELS, STATUS_SEQUENCE } from "../../../constants/status-labels"
import { normalizeStatus } from "../column-defs/normalizers"

const STATUS_ORDER_INDEX = new Map(STATUS_SEQUENCE.map((status, index) => [status, index]))
const STATUS_CHART_FALLBACK_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
]
const UNKNOWN_STATUS_KEY = "__UNKNOWN__"

export function useStatusChart({ filteredRows, statusSection }) {
  return React.useMemo(() => {
    if (!filteredRows || filteredRows.length === 0) {
      return { data: [], config: {} }
    }

    const counts = new Map()
    const getRowStatus =
      typeof statusSection?.getValue === "function"
        ? statusSection.getValue
        : (row) =>
            normalizeStatus(
              row?.status ??
                row?.STATUS ??
                row?.Status ??
                row?.StatusName ??
                row?.status_label ??
                null
            )

    filteredRows.forEach((row) => {
      const normalized = getRowStatus(row)
      const key = normalized ?? UNKNOWN_STATUS_KEY
      counts.set(key, (counts.get(key) ?? 0) + 1)
    })

    const statusOptions = Array.isArray(statusSection?.options) ? statusSection.options : []
    const fallbackOrderIndex = new Map(statusOptions.map((option, index) => [option.value, index]))
    const optionLabelMap = new Map(statusOptions.map((option) => [option.value, option.label]))

    const entries = Array.from(counts.entries())
    entries.sort((a, b) => {
      const statusA = a[0]
      const statusB = b[0]
      const seqOrderA = STATUS_ORDER_INDEX.has(statusA)
        ? STATUS_ORDER_INDEX.get(statusA)
        : Number.POSITIVE_INFINITY
      const seqOrderB = STATUS_ORDER_INDEX.has(statusB)
        ? STATUS_ORDER_INDEX.get(statusB)
        : Number.POSITIVE_INFINITY
      if (seqOrderA !== seqOrderB) return seqOrderA - seqOrderB
      const fallbackOrderA = fallbackOrderIndex.has(statusA)
        ? fallbackOrderIndex.get(statusA)
        : Number.POSITIVE_INFINITY
      const fallbackOrderB = fallbackOrderIndex.has(statusB)
        ? fallbackOrderIndex.get(statusB)
        : Number.POSITIVE_INFINITY
      if (fallbackOrderA !== fallbackOrderB) return fallbackOrderA - fallbackOrderB
      if (statusA === UNKNOWN_STATUS_KEY && statusB !== UNKNOWN_STATUS_KEY) return 1
      if (statusA !== UNKNOWN_STATUS_KEY && statusB === UNKNOWN_STATUS_KEY) return -1
      return statusA.localeCompare(statusB)
    })

    const data = entries.map(([status, value], index) => {
      const label =
        optionLabelMap.get(status) ??
        (status === UNKNOWN_STATUS_KEY
          ? "Unknown"
          : STATUS_LABELS[status] ?? status?.replace(/_/g, " ") ?? "Unknown")
      const fill =
        STATUS_COLORS[status] ??
        STATUS_CHART_FALLBACK_COLORS[index % STATUS_CHART_FALLBACK_COLORS.length]
      return {
        status,
        label,
        value,
        fill,
      }
    })

    const config = data.reduce((acc, item) => {
      acc[item.status] = { label: item.label, color: item.fill }
      return acc
    }, {})

    return { data, config }
  }, [filteredRows, statusSection])
}
