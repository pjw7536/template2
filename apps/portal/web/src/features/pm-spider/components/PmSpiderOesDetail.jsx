import { useEffect, useState } from "react"
import { AlertTriangle, Waves, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { usePmSpiderDetailResult } from "../hooks/usePmSpiderQueries"
import { formatNumber } from "../utils/format"
import { CanvasHeatmap } from "./CanvasHeatmap"
import { CanvasLineChart } from "./CanvasLineChart"

function ChartCloseButton({ onClick, label = "차트 닫기" }) {
  if (!onClick) return null

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      onClick={onClick}
      className="size-7 text-muted-foreground hover:text-foreground"
      aria-label={label}
      title={label}
    >
      <X className="size-3.5" aria-hidden="true" />
    </Button>
  )
}


function formatWavelengthValue(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return ""
  if (Number.isInteger(numeric)) return String(numeric)
  return numeric.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")
}

function nearestWavelength(value, wavelengths) {
  const numeric = Number(value)
  const candidates = Array.isArray(wavelengths)
    ? wavelengths.map(Number).filter(Number.isFinite)
    : []
  if (!Number.isFinite(numeric) || !candidates.length) return null
  return candidates.reduce((nearest, candidate) => (
    Math.abs(candidate - numeric) < Math.abs(nearest - numeric) ? candidate : nearest
  ), candidates[0])
}

function WavelengthInput({ value, wavelengths, onSelect, className }) {
  const [draft, setDraft] = useState(formatWavelengthValue(value))

  useEffect(() => {
    setDraft(formatWavelengthValue(value))
  }, [value])

  const commit = () => {
    const snapped = nearestWavelength(draft, wavelengths)
    if (snapped == null) {
      setDraft(formatWavelengthValue(value))
      return
    }
    onSelect?.(snapped)
    setDraft(formatWavelengthValue(snapped))
  }

  return (
    <label className={cn("flex items-center gap-1 text-[10px] text-muted-foreground", className)}>
      <span className="shrink-0">wavelength</span>
      <Input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur()
          }
        }}
        inputMode="decimal"
        className="h-7 w-20 px-2 text-right text-[11px]"
        aria-label="OES wavelength 직접 입력"
      />
      <span className="shrink-0">nm</span>
    </label>
  )
}

function debugValue(value) {
  if (value == null || value === "") return "-"
  if (Array.isArray(value)) return value.length ? value.join(", ") : "[]"
  if (typeof value === "number") return Number.isFinite(value) ? formatNumber(value, 4) : "-"
  return String(value)
}

function OesDebugLine({ label, value }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words font-mono text-foreground">{debugValue(value)}</dd>
    </div>
  )
}

function OesEmptyDebugPanel({ category, selectedStep, detailResult, queryError }) {
  const oes = detailResult?.oes ?? {}
  const filters = detailResult?.filters ?? category?.payload ?? {}
  const warnings = Array.isArray(detailResult?.warnings) ? detailResult.warnings : []
  const stepRows = Array.isArray(oes?.stepRows) ? oes.stepRows : []
  const availableSteps = stepRows.map((row) => String(row.step ?? "")).filter(Boolean)
  const selectedStepText = String(selectedStep ?? "")
  const hasSelectedStep = availableSteps.includes(selectedStepText)
  const heatmap = oes?.heatmap ?? {}
  const queryMessage = queryError?.message || queryError?.response?.data?.error || ""
  const diagnosis = []

  if (!detailResult) diagnosis.push("detail API 응답이 아직 없습니다. Network 탭에서 compare 요청 실패 여부를 확인하세요.")
  if (Number(oes?.scoreFileCount || 0) === 0) diagnosis.push("OES score 파일을 읽지 못했습니다. result/score_data partition을 확인하세요.")
  if (Number(oes?.fileCount || 0) === 0) diagnosis.push("OES raw 파일 후보가 0개입니다. data 경로, dt/PM 시점, ppid/recipe_id, OES plain/Hive layout을 확인하세요.")
  if (Number(oes?.fileCount || 0) > 0 && Number(oes?.rowCount || 0) === 0) diagnosis.push("raw 파일은 읽었지만 선택 step/filter 후 남은 row가 없습니다. raw의 rcp_step/step_seq와 선택 step 값이 같은지 확인하세요.")
  if (stepRows.length > 0 && !hasSelectedStep) diagnosis.push("선택 step이 score step 목록에 없습니다. 랭킹 row의 step 문자열과 raw rcp_step 값의 대소문자/공백을 확인하세요.")
  if (Number(oes?.rowCount || 0) > 0 && (!heatmap?.width || !heatmap?.height)) diagnosis.push("row는 있지만 heatmap matrix가 비었습니다. wavelength/value 컬럼 변환 또는 traj_phase/time 컬럼을 확인하세요.")
  if (warnings.length) diagnosis.push("backend warnings가 있습니다. 아래 warning 메시지를 먼저 확인하세요.")
  if (queryMessage) diagnosis.push("detail API 요청 오류가 있습니다. 아래 query error를 확인하세요.")
  if (!diagnosis.length) diagnosis.push("count상 명확한 원인이 없습니다. Network response의 oes.detailRows, oes.heatmap 원문을 확인하세요.")

  const visibleStepRows = stepRows.slice(0, 12)

  return (
    <div className="grid w-full gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-left">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
        <div className="grid gap-1">
          <p className="text-sm font-semibold text-foreground">
            step <span className="font-mono">{selectedStepText}</span> intensity 데이터가 없습니다
          </p>
          <p className="text-xs text-muted-foreground">
            score/raw 조회 결과와 선택 조건을 아래에 표시합니다.
          </p>
        </div>
      </div>

      <div className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <p className="font-semibold text-foreground">원인 후보</p>
        <ul className="grid gap-1 text-muted-foreground">
          {diagnosis.map((message) => (
            <li key={message}>- {message}</li>
          ))}
        </ul>
      </div>

      <dl className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <OesDebugLine label="lineId" value={filters.lineId} />
        <OesDebugLine label="eqpId" value={filters.eqpId} />
        <OesDebugLine label="fdcBin" value={filters.fdcBin} />
        <OesDebugLine label="pmTimestamp" value={filters.pmTimestamp} />
        <OesDebugLine label="type" value={filters.type} />
        <OesDebugLine label="ppid" value={filters.ppid} />
        <OesDebugLine label="recipeId" value={filters.recipeId} />
        <OesDebugLine label="selectedStep" value={selectedStepText} />
        <OesDebugLine label="oesDataSource" value={filters.oesDataSource || "oes"} />
      </dl>

      <dl className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <OesDebugLine label="scoreFileCount" value={oes.scoreFileCount} />
        <OesDebugLine label="rawFileCount" value={oes.fileCount} />
        <OesDebugLine label="rowCount" value={oes.rowCount} />
        <OesDebugLine label="summaryRows" value={Array.isArray(oes.summaryRows) ? oes.summaryRows.length : 0} />
        <OesDebugLine label="stepRows" value={stepRows.length} />
        <OesDebugLine label="detailRows" value={Array.isArray(oes.detailRows) ? oes.detailRows.length : 0} />
        <OesDebugLine label="heatmap" value={`${heatmap?.width || 0} x ${heatmap?.height || 0}`} />
        <OesDebugLine label="wavelengthCount" value={Array.isArray(heatmap?.wavelengths) ? heatmap.wavelengths.length : 0} />
        <OesDebugLine label="sourcePointCount" value={heatmap?.sourcePointCount} />
      </dl>

      <div className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <p className="font-semibold text-foreground">사용 가능한 score step 후보</p>
        {visibleStepRows.length ? (
          <div className="grid gap-1">
            {visibleStepRows.map((row) => (
              <div
                key={`${row.step}-${row.minScore}-${row.maxScore}`}
                className={cn(
                  "grid grid-cols-[80px_1fr] gap-2 rounded px-1 py-0.5",
                  String(row.step) === selectedStepText && "bg-accent text-accent-foreground",
                )}
              >
                <span className="font-mono">{debugValue(row.step)}</span>
                <span className="text-muted-foreground">
                  wavelengths {debugValue(row.wavelengthCount)} · score {debugValue(row.minScore)} ~ {debugValue(row.maxScore)}
                </span>
              </div>
            ))}
            {stepRows.length > visibleStepRows.length ? (
              <p className="text-muted-foreground">외 {stepRows.length - visibleStepRows.length}개 step 생략</p>
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground">score step 후보가 없습니다.</p>
        )}
      </div>

      {warnings.length || queryMessage ? (
        <div className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
          <p className="font-semibold text-foreground">warnings / query error</p>
          {queryMessage ? <p className="break-words text-destructive">{queryMessage}</p> : null}
          {warnings.map((warning) => (
            <p key={warning} className="break-words text-muted-foreground">{warning}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}


function OesWavelengthLineChart({
  category,
  selectedStep,
  selectedWl,
  wavelengths,
  refPmDates,
  spectrumChart,
  onWavelengthChange,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState("시계열")
  const detailQuery = usePmSpiderDetailResult(
    category,
    { step: selectedStep, wavelength: selectedWl },
    refPmDates,
    { step: selectedStep, wavelength: selectedWl },
    {
      includeOesHeatmap: false,
      includeOesSpectrum: activeTab === "스펙트럼",
    },
  )
  const lineChart = detailQuery.data?.oes?.lineChart
  const fallbackSpectrum = detailQuery.data?.oes?.spectrumChart
  const activeSpectrum = spectrumChart?.series?.length ? spectrumChart : fallbackSpectrum
  const TABS = ["시계열", "스펙트럼"]

  return (
    <Card className="rounded-lg py-0">
      <CardContent className="p-3">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold">
              OES · <span className="text-primary">{selectedWl != null ? `${formatWavelengthValue(selectedWl)} nm` : "전체"}</span>
            </p>
            <WavelengthInput
              value={selectedWl}
              wavelengths={wavelengths}
              onSelect={onWavelengthChange}
            />
            <div className="flex gap-1">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "rounded px-2 py-0.5 text-[10px] transition-colors",
                    activeTab === tab ? "bg-primary text-primary-foreground" : "border bg-background hover:bg-muted",
                  )}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
          <ChartCloseButton onClick={onClose} label="OES wavelength 차트 닫기" />
        </div>

        {activeTab === "시계열" && (
          detailQuery.isFetching && !lineChart ? (
            <div className="flex min-h-[180px] items-center justify-center rounded-lg border text-sm text-muted-foreground">
              <Waves className="mr-2 size-4 animate-pulse" /> wavelength trajectory 조회 중...
            </div>
          ) : (
            <CanvasLineChart
              chart={lineChart}
              height={180}
              emptyLabel={`${selectedWl} nm trajectory 데이터가 없습니다`}
            />
          )
        )}

        {activeTab === "스펙트럼" && (
          detailQuery.isFetching && !activeSpectrum?.series?.length ? (
            <div className="flex min-h-[180px] items-center justify-center rounded-lg border text-sm text-muted-foreground">
              <Waves className="mr-2 size-4 animate-pulse" /> spectrum 조회 중...
            </div>
          ) : (
            <CanvasLineChart
              chart={activeSpectrum}
              height={180}
              emptyLabel="스펙트럼 데이터가 없습니다"
            />
          )
        )}
      </CardContent>
    </Card>
  )
}

// ── OES intensity 히트맵 (REF / COMP / OOB) ─────────────────
function OesIntensityHeatmaps({
  category,
  heatmap,
  spectrumChart,
  selectedStep,
  refPmDates,
  detailResult,
  queryError,
  isLoading,
  onClose,
}) {
  const [selectedWl, setSelectedWl] = useState(null)
  const wavelengths = Array.isArray(heatmap?.wavelengths) ? heatmap.wavelengths : []

  if (!selectedStep) {
    return (
      <div className="flex min-h-[180px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        랭킹에서 rcp_step을 선택하면 intensity heatmap이 표시됩니다
      </div>
    )
  }
  if (isLoading) {
    return (
      <Card className="relative rounded-lg py-0">
        <div className="absolute right-2 top-2 z-10">
          <ChartCloseButton onClick={onClose} label={`OES step ${selectedStep} 차트 닫기`} />
        </div>
        <CardContent className="flex min-h-[180px] items-center justify-center p-3 text-sm text-muted-foreground">
          <Waves className="mr-2 size-4 animate-pulse" /> OES intensity 조회 중...
        </CardContent>
      </Card>
    )
  }
  if (!heatmap?.width || !heatmap?.height) {
    return (
      <Card className="relative rounded-lg border-dashed py-0">
        <div className="absolute right-2 top-2 z-10">
          <ChartCloseButton onClick={onClose} label={`OES step ${selectedStep} 차트 닫기`} />
        </div>
        <CardContent className="p-3 text-sm text-muted-foreground">
          <OesEmptyDebugPanel
            category={category}
            selectedStep={selectedStep}
            detailResult={detailResult}
            queryError={queryError}
          />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <Card className="rounded-lg py-0">
        <CardContent className="p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold">
              OES Intensity Heatmap · step <span className="text-primary">{selectedStep}</span>
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <WavelengthInput
                value={selectedWl}
                wavelengths={wavelengths}
                onSelect={setSelectedWl}
              />
              <p className="text-[10px] text-muted-foreground">
                클릭/입력 → wavelength 선택 · x = wavelength · y = time(0→1)
              </p>
              <ChartCloseButton onClick={onClose} label={`OES step ${selectedStep} 차트 닫기`} />
            </div>
          </div>
          <CanvasHeatmap
            heatmap={heatmap}
            selectedWavelength={selectedWl}
            onSelectWavelength={setSelectedWl}
          />
        </CardContent>
      </Card>

      {selectedWl != null && (
        <OesWavelengthLineChart
          category={category}
          selectedStep={selectedStep}
          selectedWl={selectedWl}
          wavelengths={wavelengths}
          refPmDates={refPmDates}
          spectrumChart={spectrumChart}
          onWavelengthChange={setSelectedWl}
          onClose={() => setSelectedWl(null)}
        />
      )}
    </div>
  )
}

// ── OES step 개별 쿼리 + 히트맵 래퍼 ──────────────────────────
function OesStepDetail({ category, selectedStep, refPmDates, onRemove }) {
  const stepCell    = { step: selectedStep }
  const detailQuery = usePmSpiderDetailResult(
    category,
    stepCell,
    refPmDates,
    stepCell,
    {
      includeOesHeatmap: true,
      includeOesSpectrum: false,
      heatmapXBins: 1200,
      limit: 50,
    },
  )
  const heatmap = detailQuery.data?.oes?.heatmap
  const spectrumChart = detailQuery.data?.oes?.spectrumChart

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {category?.label ?? ""} · OES · step {selectedStep}
        </span>
      </div>
      <OesIntensityHeatmaps
        key={selectedStep}
        category={category}
        heatmap={heatmap}
        spectrumChart={spectrumChart}
        selectedStep={selectedStep}
        refPmDates={refPmDates}
        detailResult={detailQuery.data}
        queryError={detailQuery.error}
        isLoading={detailQuery.isFetching && !detailQuery.data}
        onClose={() => onRemove(selectedStep)}
      />
    </div>
  )
}

// ──────────────────────────────────────────────────────────────
// 메인 내보내기
// ──────────────────────────────────────────────────────────────

export { OesStepDetail }
