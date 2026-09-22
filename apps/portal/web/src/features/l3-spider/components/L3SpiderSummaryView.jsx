import { useEffect, useMemo, useState } from "react"
import { Inbox, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { useAuth } from "@/lib/auth"

import { useL3SpiderDailySummary, useL3SpiderTrend } from "../hooks/useL3SpiderQueries"
import { formatNumber } from "../utils/format"
import { sortLineNames } from "../utils/selection"
import { LineSummaryTotals, LineTable, ProcessEdsSummaryCard, TrendChartCard } from "./L3SpiderSummarySections"

export function L3SpiderSummaryView({ date, onDrill, selectedLine, onSelectLine, lineGroups }) {
  const query = useL3SpiderDailySummary(date)
  const trendQuery = useL3SpiderTrend()
  const data = query.data
  const h = data?.headline
  const hasData = Boolean((h && h.totalRows > 0) || data?.runStats?.totalRows > 0)

  // 오늘 Warning 또는 High Risk가 있는 라인만 활성으로 취급합니다.
  const activeLineOptions = useMemo(
    () => sortLineNames([
      ...new Set(
        (data?.matrix?.cells ?? [])
          .filter((cell) => (cell.highRisk ?? 0) + (cell.warning ?? 0) > 0)
          .map((cell) => cell.line),
      ),
    ]),
    [data?.matrix?.cells],
  )
  // 전체 알려진 라인 (lineGroups 기반, end_fab 마지막)
  const allLineOptions = useMemo(() => {
    const fromGroups = sortLineNames([...new Set((lineGroups ?? []).map((g) => g.lineName))])
    const base = fromGroups.length ? fromGroups : []
    const baseSet = new Set(base)
    const extras = activeLineOptions.filter((l) => !baseSet.has(l))
    return extras.length ? sortLineNames([...base, ...extras]) : base.length ? base : activeLineOptions
  }, [lineGroups, activeLineOptions])

  // 선택된 라인 — 활성/비활성 모두 허용 (트렌드 필터링 등)
  const activeLine = selectedLine ?? null

  // 라인별 이상감지 롤업 — 모든 알려진 라인 포함
  const lineSummary = useMemo(() => {
    const totals = new Map()
    for (const c of data?.matrix?.cells ?? []) {
      const cur = totals.get(c.line) ?? { hr: 0, wn: 0 }
      cur.hr += c.highRisk ?? 0
      cur.wn += c.warning ?? 0
      totals.set(c.line, cur)
    }
    const activeSet = new Set(activeLineOptions)
    return allLineOptions.map((line) => ({
      line,
      hr: totals.get(line)?.hr ?? 0,
      wn: totals.get(line)?.wn ?? 0,
      active: activeSet.has(line),
    }))
  }, [data?.matrix?.cells, allLineOptions, activeLineOptions])

  // 트렌드 차트용 line_name 목록 (트렌드 데이터에 등장하는 라인, end_fab 마지막 정렬)
  const trendLineNames = useMemo(
    () => sortLineNames([...new Set((trendQuery.data?.points ?? []).map((p) => p.lineName))]),
    [trendQuery.data?.points],
  )

  // 유저 지정 순서 (드래그로 변경, null = 기본 정렬) — 로그인 사용자별 localStorage 영속
  const { user } = useAuth()
  const storageKey = user?.email ? `l3spider:lineOrder:${user.email}` : null

  const [customLineOrder, setCustomLineOrder] = useState(null)
  const [isDetailMaximized, setIsDetailMaximized] = useState(false)

  // 사용자 확인 후 저장된 순서 복원 (사용자 변경 시 재실행)
  useEffect(() => {
    if (!storageKey) return
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) setCustomLineOrder(JSON.parse(saved))
    } catch {
      // localStorage 접근 실패 시 기본 정렬을 유지한다.
    }
  }, [storageKey])

  // 순서 변경 시 저장 (null 리셋은 저장하지 않음 — 별도로 removeItem)
  useEffect(() => {
    if (!storageKey || customLineOrder === null) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(customLineOrder))
    } catch {
      // 저장 실패는 화면 동작을 막지 않는다.
    }
  }, [storageKey, customLineOrder])

  function handleReorder(fromIdx, toIdx) {
    const names = lineSummary.map((r) => r.line)
    const next = customLineOrder ? [...customLineOrder] : [...names]
    const [moved] = next.splice(fromIdx, 1)
    next.splice(toIdx, 0, moved)
    setCustomLineOrder(next)
  }

  function resetLineOrder() {
    setCustomLineOrder(null)
    if (storageKey) localStorage.removeItem(storageKey)
  }

  const orderedLineSummary = useMemo(() => {
    if (!customLineOrder) return lineSummary
    const map = new Map(lineSummary.map((r) => [r.line, r]))
    const ordered = customLineOrder.map((name) => map.get(name)).filter(Boolean)
    const extras = lineSummary.filter((r) => !customLineOrder.includes(r.line))
    return [...ordered, ...extras]
  }, [lineSummary, customLineOrder])

  const runStatsMap = useMemo(() => {
    const map = {}
    const entries = data?.runStats?.byLineName ?? data?.runStats?.byLine ?? []
    for (const entry of entries) {
      map[entry.lineName ?? entry.lineId] = entry.stepSeqCount
    }
    return map
  }, [data?.runStats?.byLine, data?.runStats?.byLineName])

  if (!date || query.isLoading || query.error || !hasData) {
    let message
    if (!date && (trendQuery.isLoading || !lineGroups)) {
      message = (
        <span className="inline-flex items-center gap-2">
          <Loader2 className="size-4 animate-spin" /> 데이터를 불러오는 중입니다.
        </span>
      )
    } else if (!date) {
      message = "날짜를 선택하면 해당 날짜 전체의 이상감지 요약을 조회합니다."
    } else if (query.isLoading) {
      message = (
        <span className="inline-flex items-center gap-2">
          <Loader2 className="size-4 animate-spin" /> 요약을 불러오는 중입니다.
        </span>
      )
    } else if (query.error) {
      message = <span className="text-destructive">{query.error.message || "요약을 불러오지 못했습니다."}</span>
    } else {
      message = (
        <span className="inline-flex flex-col items-center gap-2 text-center">
          <Inbox className="size-6" aria-hidden="true" />
          {date} 날짜에 데이터가 없습니다.
        </span>
      )
    }
    return (
      <main className="flex min-h-0 flex-1 min-w-0 overflow-hidden px-5 pb-5 pt-3">
        <Card className="flex min-h-0 flex-1 rounded-lg">
          <CardContent className="flex min-h-0 flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
            {message}
          </CardContent>
        </Card>
      </main>
    )
  }

  return (
    <main className="flex min-h-0 flex-1 min-w-0 overflow-hidden px-5 pb-5 pt-3">
      <div className="grid h-full min-h-0 flex-1 min-w-0 grid-cols-[420px_minmax(0,1fr)] grid-rows-[minmax(0,4fr)_minmax(0,5fr)] gap-4 overflow-hidden">
        {isDetailMaximized ? (
          <ProcessEdsSummaryCard
            className="col-span-2 row-span-2"
            matrix={data.matrix}
            selectedLine={activeLine}
            onDrill={onDrill}
            isMaximized={isDetailMaximized}
            onToggleMaximized={() => setIsDetailMaximized(false)}
          />
        ) : (
          <>
            <Card className="row-span-2 flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg py-0 gap-0">
              <div className="flex h-10 shrink-0 items-center gap-2 border-b bg-muted/50 px-4">
                <CardTitle className="text-[15px]">라인별 이상감지 요약</CardTitle>
                <Badge variant="outline" className="text-xs">{formatNumber(allLineOptions.length)}개</Badge>
                {customLineOrder && (
                  <button
                    type="button"
                    onClick={resetLineOrder}
                    className="text-[13px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                  >
                    순서초기화
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => onSelectLine?.(null)}
                  disabled={!activeLine}
                  className={cn(
                    "ml-auto text-[13px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline",
                    !activeLine && "invisible pointer-events-none",
                  )}
                >
                  해제
                </button>
              </div>
              <CardContent className="min-h-0 flex-1 p-0">
                <LineTable rows={orderedLineSummary} selectedLine={activeLine} onSelectLine={onSelectLine} onReorder={handleReorder} runStatsMap={runStatsMap} />
              </CardContent>
              <LineSummaryTotals headline={h} runStats={data?.runStats} />
            </Card>

            <TrendChartCard
              trendPoints={trendQuery.data?.points ?? []}
              allLineNames={trendLineNames}
              focusLine={activeLine ?? undefined}
            />

            <ProcessEdsSummaryCard
              matrix={data.matrix}
              selectedLine={activeLine}
              onDrill={onDrill}
              isMaximized={isDetailMaximized}
              onToggleMaximized={() => setIsDetailMaximized(true)}
            />
          </>
        )}
      </div>
    </main>
  )
}
