// src/features/line-dashboard/history/LineHistoryDashboard.jsx
"use client"

import * as React from "react"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"
import { IconAlertCircle, IconRefresh } from "@tabler/icons-react"

import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { buildBackendUrl } from "@/lib/api"
import { cn } from "@/lib/utils"

const RANGE_OPTIONS = [
  { label: "7일", value: 7 },
  { label: "14일", value: 14 },
  { label: "30일", value: 30 },
]

const DIMENSION_OPTIONS = [
  { value: "sdwt", label: "SDWT" },
  { value: "user_sdwt", label: "User SDWT" },
  { value: "eqp_id", label: "EQP ID" },
  { value: "main_step", label: "Main Step" },
  { value: "sample_type", label: "Sample Type" },
  { value: "line_id", label: "Line ID" },
]

const METRIC_OPTIONS = [
  { value: "rowCount", label: "진행 건수" },
  { value: "sendJiraCount", label: "Send Jira" },
]

const CATEGORY_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--primary)",
]

const totalsChartConfig = {
  rowCount: { label: "진행 건수", color: "var(--chart-1)" },
  sendJiraCount: { label: "Send Jira", color: "var(--chart-2)" },
}

function formatDateLabel(value) {
  if (!value) return ""
  const date = new Date(`${value}T00:00:00Z`)
  if (!Number.isFinite(date.getTime())) return value
  return new Intl.DateTimeFormat("ko-KR", { month: "2-digit", day: "2-digit" }).format(date)
}

function buildCategorySeries(records, metricKey, limit = 5) {
  if (!Array.isArray(records) || records.length === 0) {
    return { data: [], categories: [], config: {} }
  }

  const totalsByCategory = new Map()
  const dateSet = new Set()

  for (const record of records) {
    const category = typeof record?.category === "string" && record.category.trim().length > 0
      ? record.category.trim()
      : "Unspecified"
    const value = Number(record?.[metricKey] ?? 0) || 0
    dateSet.add(record?.date)
    totalsByCategory.set(category, (totalsByCategory.get(category) ?? 0) + value)
  }

  const categories = Array.from(totalsByCategory.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([category]) => category)

  const sortedDates = Array.from(dateSet)
    .filter(Boolean)
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))

  const basePoints = sortedDates.map((date) => {
    const point = { date }
    for (const category of categories) {
      point[category] = 0
    }
    return point
  })

  const pointsByDate = new Map(basePoints.map((point) => [point.date, point]))

  for (const record of records) {
    const category = typeof record?.category === "string" && record.category.trim().length > 0
      ? record.category.trim()
      : "Unspecified"
    if (!categories.includes(category)) continue
    const date = record?.date
    if (!date || !pointsByDate.has(date)) continue
    const value = Number(record?.[metricKey] ?? 0) || 0
    const point = pointsByDate.get(date)
    point[category] = (point[category] ?? 0) + value
  }

  const config = {}
  categories.forEach((category, index) => {
    const color = CATEGORY_COLORS[index % CATEGORY_COLORS.length]
    config[category] = { label: category, color }
  })

  return { data: basePoints, categories, config }
}

function hasPositiveValue(records, key) {
  return Array.isArray(records) && records.some((record) => (Number(record?.[key] ?? 0) || 0) > 0)
}

export function LineHistoryDashboard({ lineId, initialRangeDays = 14 }) {
  const [rangeDays, setRangeDays] = React.useState(initialRangeDays)
  const [dimension, setDimension] = React.useState(DIMENSION_OPTIONS[0].value)
  const [metric, setMetric] = React.useState(METRIC_OPTIONS[0].value)
  const [refreshToken, setRefreshToken] = React.useState(0)
  const [state, setState] = React.useState({ data: null, isLoading: false, error: null })

  React.useEffect(() => {
    setState({ data: null, isLoading: true, error: null })
  }, [lineId])

  React.useEffect(() => {
    const controller = new AbortController()

    async function load() {
      if (!lineId) {
        setState({ data: null, isLoading: false, error: null })
        return
      }

      setState((previous) => ({ ...previous, isLoading: true, error: null }))

      try {
        const params = new URLSearchParams({ lineId: String(lineId), rangeDays: String(rangeDays) })
        const endpoint = buildBackendUrl("/line-dashboard/history", params)
        const response = await fetch(endpoint, {
          signal: controller.signal,
          credentials: "include",
        })

        if (!response.ok) {
          const payload = await response.json().catch(() => ({}))
          const message = typeof payload?.error === "string" ? payload.error : "Failed to load history data"
          throw new Error(message)
        }

        const payload = await response.json()
        setState({ data: payload, isLoading: false, error: null })
      } catch (error) {
        if (controller.signal.aborted) return
        const message = error instanceof Error ? error.message : "Failed to load history data"
        setState({ data: null, isLoading: false, error: message })
      }
    }

    load()

    return () => controller.abort()
  }, [lineId, rangeDays, refreshToken])

  const availableDimensions = React.useMemo(() => {
    if (!state.data?.breakdowns) return []
    return DIMENSION_OPTIONS.filter((option) => {
      const rows = state.data.breakdowns?.[option.value]
      return Array.isArray(rows) && rows.length > 0
    })
  }, [state.data])

  React.useEffect(() => {
    if (!availableDimensions.length) return
    if (!availableDimensions.some((option) => option.value === dimension)) {
      setDimension(availableDimensions[0].value)
    }
  }, [availableDimensions, dimension])

  const totalsData = React.useMemo(() => state.data?.totals ?? [], [state.data])
  const breakdownRecords = React.useMemo(
    () => (dimension ? state.data?.breakdowns?.[dimension] ?? [] : []),
    [state.data, dimension]
  )

  const categorySeries = React.useMemo(
    () => buildCategorySeries(breakdownRecords, metric, 5),
    [breakdownRecords, metric]
  )

  const showSendJira = React.useMemo(
    () => hasPositiveValue(totalsData, "sendJiraCount") || hasPositiveValue(breakdownRecords, "sendJiraCount"),
    [totalsData, breakdownRecords]
  )

  const handleRefresh = React.useCallback(() => {
    setRefreshToken((value) => value + 1)
  }, [])

  const handleDimensionChange = React.useCallback((event) => {
    setDimension(event.target.value)
  }, [])

  const handleMetricChange = React.useCallback((event) => {
    setMetric(event.target.value)
  }, [])

  const { data, isLoading, error } = state

  return (
    <div className="relative flex h-full flex-col gap-4">
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">History · {lineId}</h1>
            <p className="text-sm text-muted-foreground">
              라인별 E-SOP 진행 추이를 일별로 확인하고 주요 분류별로 비교합니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {RANGE_OPTIONS.map((option) => (
              <Button
                key={option.value}
                size="sm"
                variant={rangeDays === option.value ? "default" : "outline"}
                onClick={() => setRangeDays(option.value)}
                disabled={isLoading && rangeDays === option.value}
              >
                {option.label}
              </Button>
            ))}
            <Button
              size="icon"
              variant="outline"
              onClick={handleRefresh}
              disabled={isLoading}
            >
              <IconRefresh className={cn("size-4", isLoading && "animate-spin")} />
            </Button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>
            범위: {data?.from ?? "-"} ~ {data?.to ?? "-"}
          </span>
          {data?.generatedAt && (
            <span>
              업데이트: {new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.generatedAt))}
            </span>
          )}
        </div>
        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            <IconAlertCircle className="size-4" />
            <span>{error}</span>
          </div>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h2 className="text-base font-semibold">일별 진행 현황</h2>
              <p className="text-xs text-muted-foreground">Daily ESOP row count와 Send Jira 건수를 비교합니다.</p>
            </div>
          </div>
          <ChartContainer config={totalsChartConfig} className="h-[340px]">
            <ResponsiveContainer>
              <LineChart data={totalsData} margin={{ top: 12, right: 16, left: 8, bottom: 16 }}>
                <CartesianGrid strokeDasharray="4 4" className="stroke-muted" />
                <XAxis dataKey="date" tickFormatter={formatDateLabel} tickMargin={12} />
                <YAxis allowDecimals={false} width={64} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend formatter={(value) => totalsChartConfig[value]?.label ?? value} />
                <Line
                  type="monotone"
                  dataKey="rowCount"
                  name={totalsChartConfig.rowCount.label}
                  stroke={totalsChartConfig.rowCount.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                />
                {showSendJira && (
                  <Line
                    type="monotone"
                    dataKey="sendJiraCount"
                    name={totalsChartConfig.sendJiraCount.label}
                    stroke={totalsChartConfig.sendJiraCount.color}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 5 }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </ChartContainer>
        </div>

        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-base font-semibold">분류별 추이</h2>
              <p className="text-xs text-muted-foreground">상위 5개 분류의 일별 트렌드를 확인합니다.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="history-dimension">
                분류
              </label>
              <select
                id="history-dimension"
                className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-sm focus:outline-none"
                value={dimension}
                onChange={handleDimensionChange}
              >
                {availableDimensions.length === 0 && <option value="">데이터 없음</option>}
                {availableDimensions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="history-metric">
                지표
              </label>
              <select
                id="history-metric"
                className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-sm focus:outline-none"
                value={metric}
                onChange={handleMetricChange}
              >
                {METRIC_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {categorySeries.data.length > 0 ? (
            <ChartContainer config={categorySeries.config} className="h-[340px]">
              <ResponsiveContainer>
                <LineChart data={categorySeries.data} margin={{ top: 12, right: 16, left: 8, bottom: 16 }}>
                  <CartesianGrid strokeDasharray="4 4" className="stroke-muted" />
                  <XAxis dataKey="date" tickFormatter={formatDateLabel} tickMargin={12} />
                  <YAxis allowDecimals={false} width={64} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Legend formatter={(value) => categorySeries.config?.[value]?.label ?? value} />
                  {categorySeries.categories.map((category) => (
                    <Line
                      key={category}
                      type="monotone"
                      dataKey={category}
                      name={categorySeries.config?.[category]?.label ?? category}
                      stroke={categorySeries.config?.[category]?.color ?? "var(--chart-1)"}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 5 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </ChartContainer>
          ) : (
            <div className="flex h-[340px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
              {availableDimensions.length === 0
                ? "선택된 기간에 대한 분류 데이터가 없습니다."
                : "선택한 분류에 대한 데이터가 없습니다."}
            </div>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="pointer-events-none absolute inset-x-0 top-24 flex justify-center">
          <div className="rounded-full border border-muted bg-background/90 px-3 py-1 text-xs text-muted-foreground shadow-sm">
            데이터를 불러오는 중...
          </div>
        </div>
      )}
    </div>
  )
}
