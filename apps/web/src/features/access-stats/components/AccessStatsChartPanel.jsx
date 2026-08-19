import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, BarChart3 } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { cn } from "@/lib/utils"

import {
  CHART_BG_CLASSES,
  CHART_COLOR_OPTIONS,
  CHART_COLORS,
  CHART_TYPE_OPTIONS,
  CHART_VIEW_OPTIONS,
  MAX_ACCESS_DATE_OFFSET_DAYS,
  MIN_ACCESS_DATE_OFFSET_DAYS,
  PERIOD_OPTIONS,
  buildSplitChartGroups,
  clampAccessDateOffset,
  formatAccessDateOffsetLabel,
  formatDateTick,
  formatNumber,
  getKstDateString,
} from "../utils/accessStatsPage"
import { StatePanel } from "./AccessStatsSummaryPanels"

function AccessDateSlider({ value, onChange }) {
  const normalizedValue = clampAccessDateOffset(value)
  const [draftValue, setDraftValue] = useState(normalizedValue)
  const selectedDate = getKstDateString(draftValue)
  const selectedLabel = formatAccessDateOffsetLabel(draftValue)

  useEffect(() => {
    setDraftValue(normalizedValue)
  }, [normalizedValue])

  function handleValueChange(nextValue) {
    setDraftValue(clampAccessDateOffset(nextValue[0]))
  }

  function handleValueCommit(nextValue) {
    const nextOffset = clampAccessDateOffset(nextValue[0])
    setDraftValue(nextOffset)
    onChange?.(nextOffset)
  }

  return (
    <div className="flex h-9 min-w-[252px] max-w-[420px] flex-1 items-center gap-2 rounded-md border-border bg-card px-2">
      <span className="mt-5 shrink-0 text-[11px] text-muted-foreground">-365일</span>
      <div className="relative min-w-[120px] flex-1 pt-5">
        <span className="absolute left-1/2 top-0 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-muted-foreground">
          {selectedDate} ({selectedLabel})
        </span>
        <Slider
          className="[&>span:first-child]:h-2 [&>span:first-child]:bg-primary [&>span:first-child>span]:bg-muted [&_[role=slider]]:size-3 [&_[role=slider]]:shadow-sm"
          min={MIN_ACCESS_DATE_OFFSET_DAYS}
          max={MAX_ACCESS_DATE_OFFSET_DAYS}
          step={1}
          value={[draftValue]}
          onValueChange={handleValueChange}
          onValueCommit={handleValueCommit}
          aria-label="접속 통계 날짜 선택"
        />
      </div>
      <span className="mt-5 shrink-0 text-[11px] text-muted-foreground">오늘</span>
    </div>
  )
}

function ChartColorPicker({ appName, colorValue, colorClassName, onColorChange }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="size-5 rounded-sm p-0"
          aria-label={`${appName} 차트 색상 변경`}
        >
          <span className={cn("size-3 rounded-full", colorClassName)} aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-36">
        <DropdownMenuLabel className="px-2 py-1 text-xs">색상</DropdownMenuLabel>
        <div className="grid grid-cols-5 gap-1 p-1">
          {CHART_COLOR_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={cn(
                "flex size-6 items-center justify-center rounded-sm border outline-none transition focus-visible:ring-2 focus-visible:ring-ring",
                colorValue === option.value && "ring-2 ring-ring ring-offset-2 ring-offset-background"
              )}
              onClick={() => onColorChange(option.value)}
              aria-label={`${appName} ${option.label} 적용`}
              aria-pressed={colorValue === option.value}
            >
              <span className={cn("size-3 rounded-full", option.bgClass)} aria-hidden="true" />
            </button>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function ChartPanel({
  apps,
  series,
  range,
  chartRows,
  isLoading,
  error,
  period,
  dateOffset,
  onDateOffsetChange,
  periodKey,
  onPeriodChange,
}) {
  const [hiddenAppIds, setHiddenAppIds] = useState(() => new Set())
  const [chartView, setChartView] = useState("split")
  const [chartType, setChartType] = useState("line")
  const [chartColorByAppId, setChartColorByAppId] = useState({})
  const chartApps = apps
  const visibleChartApps = chartApps.filter((app) => !hiddenAppIds.has(app.appId))
  const getChartColor = (appId, index) => chartColorByAppId[appId] || CHART_COLORS[index % CHART_COLORS.length]
  const getChartBgClass = (appId, index) => {
    const color = getChartColor(appId, index)
    return CHART_COLOR_OPTIONS.find((option) => option.value === color)?.bgClass || CHART_BG_CLASSES[index % CHART_BG_CLASSES.length]
  }
  const chartConfig = Object.fromEntries(
    chartApps.map((app, index) => [
      app.appId,
      { label: app.appName, color: getChartColor(app.appId, index) },
    ])
  )
  const splitChartGroups = useMemo(
    () => buildSplitChartGroups(series, apps, range, period),
    [apps, period, range, series]
  )

  function toggleChartApp(appId) {
    setHiddenAppIds((current) => {
      const next = new Set(current)
      if (next.has(appId)) {
        next.delete(appId)
      } else {
        next.add(appId)
      }
      return next
    })
  }

  function updateChartColor(appId, color) {
    setChartColorByAppId((current) => ({ ...current, [appId]: color }))
  }

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col gap-0 overflow-hidden rounded-lg py-0 shadow-none">
      <div className="flex min-h-12 shrink-0 items-center border-b px-4 py-2">
        <div className="flex w-full min-w-0 flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center text-sm font-semibold leading-none">
            앱별 접속 추이
          </CardTitle>
          <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
            <AccessDateSlider value={dateOffset} onChange={onDateOffsetChange} />
            <div className="flex items-center rounded-md border bg-background p-0.5">
              {CHART_VIEW_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={chartView === option.key ? "default" : "ghost"}
                  className="h-6 px-2 text-xs"
                  onClick={() => setChartView(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <div className="flex items-center rounded-md border bg-background p-0.5">
              {CHART_TYPE_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={chartType === option.key ? "default" : "ghost"}
                  className="h-6 px-2 text-xs"
                  onClick={() => setChartType(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <div className="flex items-center rounded-md border bg-background p-0.5">
              {PERIOD_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={periodKey === option.key ? "default" : "ghost"}
                  className="h-6 px-2 text-xs"
                  onClick={() => onPeriodChange(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <CardContent className="min-h-0 flex-1 px-4 py-2">
        {isLoading ? (
          <div className="grid h-full min-h-72 gap-3">
            <Skeleton className="h-full min-h-64 w-full" />
          </div>
        ) : error ? (
          <StatePanel
            icon={AlertTriangle}
            title="차트를 불러오지 못했습니다."
            description={error.message || "접속 통계 요청 중 오류가 발생했습니다."}
          />
        ) : chartRows.length === 0 || chartApps.length === 0 ? (
          <StatePanel
            icon={BarChart3}
            title="접속 기록이 없습니다."
            description="선택한 기간에 기록된 앱 접속 이벤트가 없습니다."
          />
        ) : chartView === "split" ? (
          <div className="h-full min-h-72 min-w-0 overflow-y-auto pr-1">
            <div className="grid grid-cols-3 gap-3">
              {splitChartGroups.map(({ app, rows }, index) => {
                const chartColor = getChartColor(app.appId, index)
                const chartBgClass = getChartBgClass(app.appId, index)
                const splitChartConfig = {
                  accessCount: { label: app.appName, color: chartColor },
                }

                return (
                  <section key={app.appId} className="min-w-0 rounded-md border bg-background">
                    <div className="flex h-10 items-center justify-between gap-3 border-b px-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <ChartColorPicker
                          appName={app.appName}
                          colorValue={chartColor}
                          colorClassName={chartBgClass}
                          onColorChange={(color) => updateChartColor(app.appId, color)}
                        />
                        <h3 className="truncate text-sm font-semibold">{app.appName}</h3>
                      </div>
                      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatNumber(app.accessCount)}회
                      </span>
                    </div>
                    <div className="h-56 min-w-0 px-3 py-2">
                      <ChartContainer config={splitChartConfig} className="h-full min-w-0">
                        <ResponsiveContainer width="100%" height="100%">
                          {chartType === "line" ? (
                            <LineChart data={rows} margin={{ top: 12, right: 16, left: 0, bottom: 28 }}>
                              <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                              <XAxis
                                dataKey="date"
                                tickFormatter={(value) => formatDateTick(value, period)}
                                tickLine={false}
                                axisLine={{ stroke: "var(--border)" }}
                                tick={{ fontSize: 12 }}
                                angle={-45}
                                textAnchor="end"
                                tickMargin={6}
                                height={44}
                                minTickGap={16}
                              />
                              <YAxis
                                tickLine={false}
                                axisLine={{ stroke: "var(--border)" }}
                                tick={{ fontSize: 12 }}
                                tickMargin={6}
                                allowDecimals={false}
                                width={52}
                              />
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Line
                                type="monotone"
                                dataKey="accessCount"
                                name={app.appName}
                                stroke={chartColor}
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 4 }}
                              />
                            </LineChart>
                          ) : (
                            <BarChart
                              data={rows}
                              margin={{ top: 12, right: 16, left: 0, bottom: 28 }}
                              barCategoryGap="24%"
                            >
                              <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                              <XAxis
                                dataKey="date"
                                tickFormatter={(value) => formatDateTick(value, period)}
                                tickLine={false}
                                axisLine={{ stroke: "var(--border)" }}
                                tick={{ fontSize: 12 }}
                                angle={-45}
                                textAnchor="end"
                                tickMargin={6}
                                height={44}
                                minTickGap={16}
                              />
                              <YAxis
                                tickLine={false}
                                axisLine={{ stroke: "var(--border)" }}
                                tick={{ fontSize: 12 }}
                                tickMargin={6}
                                allowDecimals={false}
                                width={52}
                              />
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Bar
                                dataKey="accessCount"
                                name={app.appName}
                                fill={chartColor}
                                maxBarSize={44}
                              />
                            </BarChart>
                          )}
                        </ResponsiveContainer>
                      </ChartContainer>
                    </div>
                  </section>
                )
              })}
            </div>
          </div>
        ) : (
          <div className="flex h-full min-h-72 min-w-0 gap-4">
            <ChartContainer config={chartConfig} className="h-full min-h-0 min-w-0 flex-1">
              <ResponsiveContainer width="100%" height="100%">
                {chartType === "line" ? (
                  <LineChart data={chartRows} margin={{ top: 16, right: 16, left: 0, bottom: 28 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => formatDateTick(value, period)}
                      tickLine={false}
                      axisLine={{ stroke: "var(--border)" }}
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      tickMargin={6}
                      height={44}
                      minTickGap={16}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={{ stroke: "var(--border)" }}
                      tick={{ fontSize: 12 }}
                      tickMargin={6}
                      allowDecimals={false}
                      width={52}
                    />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    {visibleChartApps.map((app) => {
                      const colorIndex = chartApps.findIndex((item) => item.appId === app.appId)
                      return (
                        <Line
                          key={app.appId}
                          type="monotone"
                          dataKey={app.appId}
                          name={app.appName}
                          stroke={getChartColor(app.appId, colorIndex)}
                          strokeWidth={2}
                          dot={false}
                          activeDot={{ r: 4 }}
                        />
                      )
                    })}
                  </LineChart>
                ) : (
                  <BarChart
                    data={chartRows}
                    margin={{ top: 16, right: 16, left: 0, bottom: 28 }}
                    barCategoryGap="24%"
                  >
                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => formatDateTick(value, period)}
                      tickLine={false}
                      axisLine={{ stroke: "var(--border)" }}
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      tickMargin={6}
                      height={44}
                      minTickGap={16}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={{ stroke: "var(--border)" }}
                      tick={{ fontSize: 12 }}
                      tickMargin={6}
                      allowDecimals={false}
                      width={52}
                    />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    {visibleChartApps.map((app) => {
                      const colorIndex = chartApps.findIndex((item) => item.appId === app.appId)
                      return (
                        <Bar
                          key={app.appId}
                          dataKey={app.appId}
                          name={app.appName}
                          stackId="access"
                          fill={getChartColor(app.appId, colorIndex)}
                          maxBarSize={44}
                        />
                      )
                    })}
                  </BarChart>
                )}
              </ResponsiveContainer>
            </ChartContainer>
            <div className="flex max-h-full w-40 shrink-0 flex-col gap-2 overflow-y-auto pr-1">
              {chartApps.map((app, index) => {
                const isHidden = hiddenAppIds.has(app.appId)
                return (
                  <div
                    key={app.appId}
                    className={cn(
                      "flex min-w-0 items-center gap-2 rounded-sm text-left text-xs text-muted-foreground outline-none transition-opacity hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
                      isHidden && "opacity-40"
                    )}
                  >
                    <ChartColorPicker
                      appName={app.appName}
                      colorValue={getChartColor(app.appId, index)}
                      colorClassName={getChartBgClass(app.appId, index)}
                      onColorChange={(color) => updateChartColor(app.appId, color)}
                    />
                    <button
                      type="button"
                      className="min-w-0 truncate whitespace-nowrap text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={() => toggleChartApp(app.appId)}
                      aria-pressed={!isHidden}
                    >
                      {app.appName}
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
