const PERIOD_OPTIONS = [
  { key: "day", label: "일별" },
  { key: "week", label: "주별" },
  { key: "month", label: "월별" },
]

const CHART_VIEW_OPTIONS = [
  { key: "combined", label: "통합" },
  { key: "split", label: "앱별" },
]

const CHART_TYPE_OPTIONS = [
  { key: "bar", label: "Bar" },
  { key: "line", label: "Line" },
]

const MIN_ACCESS_DATE_OFFSET_DAYS = -365
const MAX_ACCESS_DATE_OFFSET_DAYS = 0
const DEFAULT_ACCESS_DATE_OFFSET_DAYS = -6

const CHART_COLOR_OPTIONS = [
  { value: "var(--chart-1)", bgClass: "bg-[var(--chart-1)]", label: "색상 1" },
  { value: "var(--chart-2)", bgClass: "bg-[var(--chart-2)]", label: "색상 2" },
  { value: "var(--chart-3)", bgClass: "bg-[var(--chart-3)]", label: "색상 3" },
  { value: "var(--chart-4)", bgClass: "bg-[var(--chart-4)]", label: "색상 4" },
  { value: "var(--chart-5)", bgClass: "bg-[var(--chart-5)]", label: "색상 5" },
]

const CHART_COLORS = CHART_COLOR_OPTIONS.map((option) => option.value)
const CHART_BG_CLASSES = CHART_COLOR_OPTIONS.map((option) => option.bgClass)
const TOP_RANK_CLASSES = [
  "border-[var(--chart-1)]/40 bg-[var(--chart-1)]/15 text-foreground",
  "border-[var(--chart-2)]/40 bg-[var(--chart-2)]/15 text-foreground",
  "border-[var(--chart-3)]/40 bg-[var(--chart-3)]/15 text-foreground",
  "border-[var(--chart-4)]/40 bg-[var(--chart-4)]/15 text-foreground",
  "border-[var(--chart-5)]/40 bg-[var(--chart-5)]/15 text-foreground",
]

const MANUAL_TEMPLATE_HEADERS = [
  "date",
  "appName",
  "accessCount",
  "uniqueUserCount",
  "memo",
]

const MANUAL_TEMPLATE_FILENAME = "external-app-access-template.csv"

function getKstDateString(offsetDays = 0) {
  const now = new Date()
  const kst = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60 * 1000)
  kst.setDate(kst.getDate() + offsetDays)
  const year = kst.getFullYear()
  const month = String(kst.getMonth() + 1).padStart(2, "0")
  const day = String(kst.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function clampAccessDateOffset(value) {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return DEFAULT_ACCESS_DATE_OFFSET_DAYS
  return Math.min(
    Math.max(Math.round(numericValue), MIN_ACCESS_DATE_OFFSET_DAYS),
    MAX_ACCESS_DATE_OFFSET_DAYS
  )
}

function buildRangeFromOffset(offsetDays) {
  const from = getKstDateString(clampAccessDateOffset(offsetDays))
  const to = getKstDateString()
  return { from, to }
}

function formatAccessDateOffsetLabel(offsetDays) {
  const clampedOffset = clampAccessDateOffset(offsetDays)
  if (clampedOffset === 0) return "오늘"
  return `${Math.abs(clampedOffset)}일 전`
}

function formatStatsRangeLabel(range) {
  if (range.from === range.to) return range.from
  return `${range.from} ~ ${range.to}`
}

function buildStatsParams(range, period) {
  return { ...range, period }
}

function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(Number(value) || 0)
}

function formatSourceLabel(app) {
  if (app?.sourceType === "internal") return "AX Portal"
  if (app?.sourceType === "manual") return "수동"
  if (app?.sourceType === "mixed") return "복합"
  return app?.sourceName || "-"
}

function buildManualTemplateExampleRow() {
  return [getKstDateString(), "AIO", "120", "55", "외부 서버 리포트 기준"]
}

function escapeCsvCell(value) {
  const text = String(value ?? "")
  if (!/[",\n\r]/.test(text)) return text
  return `"${text.replaceAll('"', '""')}"`
}

function buildCsvText(rows) {
  return `${rows.map((row) => row.map(escapeCsvCell).join(",")).join("\n")}\n`
}

function buildManualPasteSample() {
  return buildCsvText([MANUAL_TEMPLATE_HEADERS, buildManualTemplateExampleRow()]).trimEnd()
}

function downloadManualTemplateCsv() {
  const csvText = buildCsvText([MANUAL_TEMPLATE_HEADERS, buildManualTemplateExampleRow()])
  const blob = new Blob([`\ufeff${csvText}`], { type: "text/csv;charset=utf-8" })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = href
  anchor.download = MANUAL_TEMPLATE_FILENAME
  anchor.click()
  URL.revokeObjectURL(href)
}

function parseDateString(value) {
  if (typeof value !== "string") return null
  const [year, month, day] = value.split("-").map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function formatDateString(value) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function getPeriodStartDate(value, period) {
  const date = new Date(value)
  if (period === "week") {
    const mondayOffset = (date.getDay() + 6) % 7
    date.setDate(date.getDate() - mondayOffset)
    return date
  }
  if (period === "month") {
    date.setDate(1)
    return date
  }
  return date
}

function addPeriod(value, period) {
  const next = new Date(value)
  if (period === "week") {
    next.setDate(next.getDate() + 7)
  } else if (period === "month") {
    next.setMonth(next.getMonth() + 1)
  } else {
    next.setDate(next.getDate() + 1)
  }
  return next
}

function buildDateKeys({ from, to }, period) {
  const start = parseDateString(from)
  const end = parseDateString(to)
  if (!start || !end || start > end) return []

  const dates = []
  let cursor = getPeriodStartDate(start, period)
  const endBucket = getPeriodStartDate(end, period)
  while (cursor <= endBucket) {
    dates.push(formatDateString(cursor))
    cursor = addPeriod(cursor, period)
  }
  return dates
}

function formatDateTick(value, period) {
  if (typeof value !== "string") return value
  if (period === "month") return value.slice(0, 7).replace("-", ".")
  if (period === "week") return `${value.slice(5).replace("-", "/")} 주`
  return value.slice(5).replace("-", "/")
}

function buildChartRows(series, apps, range, period) {
  const chartApps = apps
  const chartIds = new Set(chartApps.map((app) => app.appId))
  const rows = new Map(
    buildDateKeys(range, period).map((date) => [
      date,
      Object.fromEntries([["date", date], ...chartApps.map((app) => [app.appId, 0])]),
    ])
  )

  series
    .filter((row) => chartIds.has(row.appId))
    .forEach((row) => {
      if (!rows.has(row.date)) {
        rows.set(row.date, Object.fromEntries([["date", row.date], ...chartApps.map((app) => [app.appId, 0])]))
      }
      rows.get(row.date)[row.appId] = Number(row.accessCount) || 0
    })

  return Array.from(rows.values())
}

function buildSplitChartGroups(series, apps, range, period) {
  const dateKeys = buildDateKeys(range, period)
  const rowsByApp = new Map(
    apps.map((app) => [
      app.appId,
      dateKeys.map((date) => ({ date, accessCount: 0 })),
    ])
  )

  series.forEach((row) => {
    const appRows = rowsByApp.get(row.appId)
    if (!appRows) return

    const targetRow = appRows.find((item) => item.date === row.date)
    if (targetRow) {
      targetRow.accessCount = Number(row.accessCount) || 0
    } else {
      appRows.push({ date: row.date, accessCount: Number(row.accessCount) || 0 })
    }
  })

  return apps.map((app) => ({
    app,
    rows: rowsByApp.get(app.appId) ?? [],
  }))
}


export {
  CHART_BG_CLASSES,
  CHART_COLOR_OPTIONS,
  CHART_COLORS,
  CHART_TYPE_OPTIONS,
  CHART_VIEW_OPTIONS,
  DEFAULT_ACCESS_DATE_OFFSET_DAYS,
  MAX_ACCESS_DATE_OFFSET_DAYS,
  MIN_ACCESS_DATE_OFFSET_DAYS,
  PERIOD_OPTIONS,
  TOP_RANK_CLASSES,
  buildChartRows,
  buildCsvText,
  buildManualPasteSample,
  buildManualTemplateExampleRow,
  buildRangeFromOffset,
  buildSplitChartGroups,
  buildStatsParams,
  clampAccessDateOffset,
  downloadManualTemplateCsv,
  formatAccessDateOffsetLabel,
  formatDateString,
  formatDateTick,
  formatNumber,
  formatSourceLabel,
  formatStatsRangeLabel,
  getKstDateString,
}
