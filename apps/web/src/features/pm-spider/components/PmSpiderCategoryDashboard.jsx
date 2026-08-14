import { useMemo, useState } from "react"
import { Activity, Waves } from "lucide-react"

import { usePmSpiderMeta } from "../hooks/usePmSpiderQueries"
import { OesStepDetail } from "./PmSpiderOesDetail"
import {
  RankPanel,
  RankingControlPanel,
  TraceDetailWithLegend,
  buildRecipeMeta,
  buildRecipeMetaSummary,
  getRankModeLabel,
} from "./PmSpiderRankingTrace"

export function PmSpiderCategoryDashboard({
  categories,
  meta,
  selectedCategoryId,
  onSelectedCategoryChange,
  isFetching,
}) {
  const refPmDates = null

  // selectedCategoryId는 "ag" | "process"이며, legacy "ag-trace"는 "ag"로 처리합니다.
  const activeType = useMemo(() => {
    const raw = selectedCategoryId || "ag"
    if (raw === "ag" || raw === "process") return raw
    return raw.startsWith("process") ? "process" : "ag"
  }, [selectedCategoryId])

  const traceCategory = categories.find((c) => c.type === activeType && c.kind === "trace")
  const oesCategory   = categories.find((c) => c.type === activeType && c.kind === "oes")

  const [selectedTraceKeys, setSelectedTraceKeys] = useState([])
  const [selectedOesSteps,  setSelectedOesSteps]  = useState([])
  const [rankKind,      setRankKind]      = useState("trace")
  const [rankMode,      setRankMode]      = useState("p3")
  const [traceSearch,   setTraceSearch]   = useState("")
  const [oesSearch,     setOesSearch]     = useState("")

  const handleTypeChange = (type) => {
    onSelectedCategoryChange?.(type)
    setSelectedTraceKeys([])
    setSelectedOesSteps([])
    setTraceSearch("")
    setOesSearch("")
  }

  const toggleTraceKey = (key) =>
    setSelectedTraceKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  const toggleOesStep = (step) =>
    setSelectedOesSteps((prev) =>
      prev.includes(step) ? prev.filter((s) => s !== step) : [...prev, step]
    )

  const activeRankCategory = rankKind === "trace" ? traceCategory : oesCategory
  const activeRankKeys = rankKind === "trace" ? selectedTraceKeys : selectedOesSteps
  const activeRankSearch = rankKind === "trace" ? traceSearch : oesSearch
  const activeRankIcon = rankKind === "trace" ? Activity : Waves
  const ActiveRankIcon = activeRankIcon
  const activeRankLabel = rankKind === "trace" ? "TRACE" : "OES"
  const handleRankSelect = rankKind === "trace" ? toggleTraceKey : toggleOesStep
  const handleRankClear = rankKind === "trace" ? () => setSelectedTraceKeys([]) : () => setSelectedOesSteps([])
  const handleRankSearchChange = rankKind === "trace" ? setTraceSearch : setOesSearch
  const rankMetaSelection = activeRankCategory?.payload
    ? { ...activeRankCategory.payload, traceDataSource: rankKind === "oes" ? "oes" : "trace" }
    : {}
  const rankMetaQuery = usePmSpiderMeta(rankMetaSelection)
  const activeRankMeta = rankMetaQuery.data || meta
  const activeRecipeMeta = buildRecipeMeta(activeRankMeta)
  const activeRankMetaSummary = buildRecipeMetaSummary(activeRecipeMeta)
  const activeRankHeaderSummary = `${activeRankLabel} RANKING - ${getRankModeLabel(rankMode)} - ${activeRankMetaSummary}`

  if (!categories.length) {
    return (
      <div className="flex min-h-96 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        PM Spider category 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)]">
        <section className="grid min-w-0 content-start gap-3">
          <RankingControlPanel
            activeType={activeType}
            activeKind={rankKind}
            activeMode={rankMode}
            onTypeChange={handleTypeChange}
            onKindChange={setRankKind}
            onModeChange={setRankMode}
          />
          <div className="flex flex-col gap-1.5">
            <div className="flex min-w-0 items-center gap-1.5 px-0.5">
              <ActiveRankIcon className="size-3 shrink-0 text-muted-foreground" />
              <div
                className="min-w-0 overflow-x-auto whitespace-nowrap text-[11px] font-semibold"
                title={activeRankHeaderSummary}
              >
                <span className="uppercase tracking-wider text-muted-foreground">{activeRankLabel} RANKING</span>
                <span className="mx-1.5 text-muted-foreground">-</span>
                <span className="text-foreground">{getRankModeLabel(rankMode)}</span>
                <span className="mx-1.5 text-muted-foreground">-</span>
                <span className="text-muted-foreground">{activeRankMetaSummary}</span>
              </div>
            </div>
            <RankPanel
              panelType={rankMode}
              category={activeRankCategory}
              selectedKeys={activeRankKeys}
              onSelectRow={handleRankSelect}
              onClearAll={handleRankClear}
              search={activeRankSearch}
              onSearchChange={handleRankSearchChange}
            />
          </div>
        </section>

        <section className="min-w-0">
          <div className="flex min-w-0 flex-col gap-3">
            {selectedTraceKeys.map((key) => (
              <TraceDetailWithLegend
                key={key}
                category={traceCategory}
                selectedKey={key}
                refPmDates={refPmDates}
                onClose={() => toggleTraceKey(key)}
              />
            ))}

            {selectedOesSteps.map((step) => (
              <OesStepDetail
                key={step}
                category={oesCategory}
                selectedStep={step}
                refPmDates={refPmDates}
                onRemove={toggleOesStep}
              />
            ))}

            {!selectedTraceKeys.length && !selectedOesSteps.length && (
              <div className="flex min-h-[320px] items-center justify-center rounded-lg border border-dashed bg-card text-sm text-muted-foreground">
                랭킹에서 항목을 선택하면 상세 차트가 표시됩니다
              </div>
            )}
          </div>
        </section>
      </div>

      {isFetching && (
        <div className="pointer-events-none fixed bottom-4 right-4 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground shadow-sm">
          PM Spider 데이터 갱신 중...
        </div>
      )}
    </div>
  )
}
