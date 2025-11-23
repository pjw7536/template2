// src/features/line-dashboard/components/data-table/hooks/useTableQuery.js
import * as React from "react"

import { buildBackendUrl } from "@/lib/api"

import { composeEqpChamber, normalizeTablePayload } from "../../../utils"
import {
  DEFAULT_TABLE,
  getDefaultFromValue,
  getDefaultToValue,
} from "../utils/constants"
import {
  createRecentHoursRange,
  normalizeRecentHoursRange,
} from "../filters/quickFilters"

/**
 * 테이블 데이터(컬럼/행/날짜 범위) 로딩을 담당하는 훅입니다.
 * - 날짜/최근 시간 범위를 정규화해 쿼리스트링을 만들고,
 *   서버 응답을 normalizeTablePayload로 안전하게 정리합니다.
 * - 오래된 응답이 최신 상태를 덮어쓰지 않도록 요청 id를 비교합니다.
 * - rows가 외부에서 수정될 수 있도록 setRows를 함께 반환합니다.
 */
export function useTableQuery({ lineId }) {
  const [selectedTable, setSelectedTable] = React.useState(DEFAULT_TABLE)
  const [columns, setColumns] = React.useState([])
  const [rows, setRows] = React.useState([])

  const [fromDate, setFromDate] = React.useState(() => getDefaultFromValue())
  const [toDate, setToDate] = React.useState(() => getDefaultToValue())

  const [appliedFrom, setAppliedFrom] = React.useState(() => getDefaultFromValue())
  const [appliedTo, setAppliedTo] = React.useState(() => getDefaultToValue())

  const [recentHoursRange, setRecentHoursRangeState] = React.useState(() =>
    createRecentHoursRange()
  )

  const [isLoadingRows, setIsLoadingRows] = React.useState(false)
  const [rowsError, setRowsError] = React.useState(null)
  const [lastFetchedCount, setLastFetchedCount] = React.useState(0)
  const [hydrationKey, setHydrationKey] = React.useState(0)

  const rowsRequestRef = React.useRef(0)

  const setRecentHoursRange = React.useCallback((nextRange) => {
    setRecentHoursRangeState((previous) => {
      const normalized = normalizeRecentHoursRange(nextRange)
      if (
        previous &&
        previous.start === normalized.start &&
        previous.end === normalized.end
      ) {
        return previous
      }
      return normalized
    })
  }, [])

  const fetchRows = React.useCallback(async () => {
    const requestId = ++rowsRequestRef.current
    setIsLoadingRows(true)
    setRowsError(null)

    try {
      let effectiveFrom = fromDate && fromDate.length > 0 ? fromDate : null
      let effectiveTo = toDate && toDate.length > 0 ? toDate : null

      if (effectiveFrom && effectiveTo) {
        const fromTime = new Date(`${effectiveFrom}T00:00:00Z`).getTime()
        const toTime = new Date(`${effectiveTo}T23:59:59Z`).getTime()
        if (Number.isFinite(fromTime) && Number.isFinite(toTime) && fromTime > toTime) {
          ;[effectiveFrom, effectiveTo] = [effectiveTo, effectiveFrom]
        }
      }

      const params = new URLSearchParams({ table: selectedTable })
      if (effectiveFrom) params.set("from", effectiveFrom)
      if (effectiveTo) params.set("to", effectiveTo)
      if (lineId) params.set("lineId", lineId)

      const normalizedRecent = normalizeRecentHoursRange(recentHoursRange)
      params.set("recentHoursStart", String(normalizedRecent.start))
      params.set("recentHoursEnd", String(normalizedRecent.end))

      const endpoint = buildBackendUrl("/tables", params)
      const response = await fetch(endpoint, { cache: "no-store", credentials: "include" })

      let payload = {}
      try {
        payload = await response.json()
      } catch {
        payload = {}
      }

      if (!response.ok) {
        const message =
          payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string"
            ? payload.error
            : `Request failed with status ${response.status}`
        throw new Error(message)
      }

      if (rowsRequestRef.current !== requestId) return

      const defaults = { table: DEFAULT_TABLE, from: getDefaultFromValue(), to: getDefaultToValue() }
      const {
        columns: fetchedColumns,
        rows: fetchedRows,
        rowCount,
        from: appliedFromValue,
        to: appliedToValue,
        table,
      } = normalizeTablePayload(payload, defaults)

      const baseColumns = fetchedColumns.filter((column) => column && column.toLowerCase() !== "id")

      const composedRows = fetchedRows.map((row) => {
        const eqpId = row?.eqp_id ?? row?.EQP_ID ?? row?.EqpId
        const chamber = row?.chamber_ids ?? row?.CHAMBER_IDS ?? row?.ChamberIds
        return { ...row, EQP_CB: composeEqpChamber(eqpId, chamber) }
      })

      const columnsWithoutOriginals = baseColumns.filter((column) => {
        const normalized = column.toLowerCase()
        return normalized !== "eqp_id" && normalized !== "chamber_ids"
      })

      const nextColumns = columnsWithoutOriginals.includes("EQP_CB")
        ? columnsWithoutOriginals
        : ["EQP_CB", ...columnsWithoutOriginals]

      setColumns(nextColumns)
      setRows(composedRows)
      setLastFetchedCount(rowCount)
      setAppliedFrom(appliedFromValue ?? null)
      setAppliedTo(appliedToValue ?? null)

      if (table && table !== selectedTable) {
        setSelectedTable(table)
      }

      setHydrationKey((prev) => prev + 1)
    } catch (error) {
      if (rowsRequestRef.current !== requestId) return

      const message = error instanceof Error ? error.message : "Failed to load table rows"
      setRowsError(message)
      setColumns([])
      setRows([])
      setLastFetchedCount(0)
    } finally {
      if (rowsRequestRef.current === requestId) {
        setIsLoadingRows(false)
      }
    }
  }, [fromDate, toDate, selectedTable, lineId, recentHoursRange])

  React.useEffect(() => {
    fetchRows()
  }, [fetchRows])

  return {
    selectedTable,
    setSelectedTable,
    columns,
    rows,
    setRows,
    fromDate,
    setFromDate,
    toDate,
    setToDate,
    appliedFrom,
    appliedTo,
    recentHoursRange,
    setRecentHoursRange,
    isLoadingRows,
    rowsError,
    lastFetchedCount,
    fetchRows,
    hydrationKey,
  }
}
