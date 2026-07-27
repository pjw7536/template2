// 파일 경로: src/features/tttm-spider/components/TttmSpiderDashboard.jsx
// 선택된 (ref,comp) entries + dataType → 챔버 칩 + 카드 + 레이더 드릴다운 + 센서 상세.
import { useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { TttmSpiderCategoryRadar } from "./TttmSpiderCategoryRadar"
import { TttmSpiderChamberCard } from "./TttmSpiderChamberCard"
import { TttmSpiderChamberChips } from "./TttmSpiderChamberChips"
import { TttmSpiderSensorDetail } from "./TttmSpiderSensorDetail"
import { TttmSpiderSensorTable } from "./TttmSpiderSensorTable"
import { fetchTttmDashboardData, tttmSpiderQueryKeys } from "../api"
import { buildDashboardPayload } from "../utils/selection"

const DATA_TYPE_OPTIONS = [
  { value: "trace", label: "TRACE" },
  { value: "oes", label: "OES" },
]

// entries: [{ key, ref, comp, label }]
export function TttmSpiderDashboard({ entries, dataType, onDataTypeChange, initialSelectedKey }) {
  const [selectedKey, setSelectedKey] = useState(initialSelectedKey ?? "")
  const [radarLevel, setRadarLevel] = useState({ type: "top" })
  const [subKey, setSubKey] = useState("")
  const [selectedSensor, setSelectedSensor] = useState(null)
  const isOes = dataType === "oes"

  const resetDrill = () => { setRadarLevel({ type: "top" }); setSubKey(""); setSelectedSensor(null) }

  const results = useQueries({
    queries: entries.map((item) => ({
      queryKey: tttmSpiderQueryKeys.dashboardData(`${item.key}::${dataType}`),
      queryFn: () => fetchTttmDashboardData(buildDashboardPayload({
        ref: item.ref, comp: item.comp, dataType, stage: "P3", traceRecipeId: item.recipe,
      })),
      staleTime: 60 * 1000, gcTime: 5 * 60 * 1000, retry: false,
    })),
  })

  const items = entries.map((item, i) => {
    const q = results[i]
    const bundle = q?.data?.bundle
    const chamber = bundle?.chambers?.[0]
    let status = "loading"
    if (q?.isError) status = q.error?.status === 404 ? "notfound" : "error"
    else if (chamber) status = "ok"
    return { key: item.key, label: item.label, ref: item.ref, comp: item.comp, status,
      index: item.index, name: item.name, refName: item.refName, compName: item.compName,
      score: chamber?.score, grade: chamber?.grade, chamber, meta: bundle?.meta }
  })

  const effectiveKey = items.some((i) => i.key === selectedKey)
    ? selectedKey : items.find((i) => i.status === "ok")?.key ?? ""
  const selected = items.find((i) => i.key === effectiveKey)
  const chamber = selected?.chamber
  const meta = selected?.meta

  const sensorCountByCat = useMemo(() => {
    const m = {}
    for (const s of chamber?.sensors ?? []) m[s.category] = (m[s.category] ?? 0) + 1
    return m
  }, [chamber])

  const radarProps = useMemo(() => {
    if (!chamber) return null
    if (radarLevel.type === "top") {
      const keys = meta?.category_order ?? []
      const counts = {}
      if (!isOes) for (const top of keys) {
        counts[top] = (meta?.category_tree?.[top] ?? []).reduce((n, leaf) => n + (sensorCountByCat[leaf] ?? 0), 0)
      }
      return { keys, values: chamber.radar ?? {}, labels: meta?.category_label ?? {}, counts,
        title: isOes ? "STEP별 건강도" : "카테고리 건강도 레이더",
        hint: isOes ? "STEP 클릭 → 화학종 계열" : "카테고리 클릭 → 하위 계열", onBack: null }
    }
    const parent = radarLevel.parent
    if (isOes) {
      return { keys: meta?.oes_species_order ?? [], values: chamber.step_category_radar?.[parent] ?? {},
        labels: meta?.oes_species_label ?? {}, counts: {}, title: `${parent} · 화학종 계열`,
        hint: "계열 클릭 → 대표 파장", onBack: () => { setRadarLevel({ type: "top" }); setSubKey("") } }
    }
    const kids = meta?.category_tree?.[parent] ?? []
    const counts = {}
    for (const leaf of kids) counts[leaf] = sensorCountByCat[leaf] ?? 0
    return { keys: kids, values: chamber.radar_leaf ?? {}, labels: meta?.leaf_label ?? {}, counts,
      title: `${(meta?.category_label ?? {})[parent] ?? parent} · 하위 계열`,
      hint: "계열 클릭 → 센서 랭킹 필터", onBack: () => { setRadarLevel({ type: "top" }); setSubKey("") } }
  }, [chamber, meta, radarLevel, isOes, sensorCountByCat])

  const onRadarSelect = (key) => {
    if (radarLevel.type === "top") { setRadarLevel({ type: "sub", parent: key }); setSubKey(""); setSelectedSensor(null) }
    else { setSubKey(key); setSelectedSensor(null) }
  }

  const oesWlPicks = isOes && radarLevel.type === "sub" && subKey
    ? (chamber?.step_category_wavelengths?.[radarLevel.parent]?.[subKey] ?? []) : []

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        비교 {items.length}개 분할 · 칩을 눌러 각 <span className="font-mono">REF vs COMP</span> 상세를 확인하세요
      </p>
      <div className="flex items-center justify-between gap-2">
        <TttmSpiderChamberChips items={items} selectedKey={effectiveKey}
          onSelect={(k) => { setSelectedKey(k); resetDrill() }} onRemove={() => {}} onClear={() => {}} hideActions />
        <div className="w-32 shrink-0">
          <Select value={dataType} onValueChange={(v) => { onDataTypeChange(v); resetDrill() }}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {DATA_TYPE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {selected && selected.status === "notfound" ? (
        <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          선택한 REF/COMP 조합에 계산된 결과가 없습니다. (재계산이 필요할 수 있습니다)
        </div>
      ) : null}

      {chamber ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm font-medium">
            <span className="text-foreground">{selected.label}</span>
            <span className="text-muted-foreground"> — </span>
            <span className="font-mono text-chart-1">REF {selected.refName}</span>
            <span className="text-muted-foreground"> vs </span>
            <span className="font-mono text-destructive">{selected.compName}</span>
          </p>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <TttmSpiderChamberCard chamber={chamber} />
            <div className="lg:col-span-2">
              {radarProps ? (
                <TttmSpiderCategoryRadar keys={radarProps.keys} values={radarProps.values} labels={radarProps.labels}
                  counts={radarProps.counts} selected={subKey} onSelect={onRadarSelect}
                  onBack={radarProps.onBack} title={radarProps.title} hint={radarProps.hint} />
              ) : null}
            </div>
          </div>

          {isOes ? (
            oesWlPicks.length ? (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="mb-2 text-sm font-medium text-foreground">{radarLevel.parent} · {subKey} 대표 파장</p>
                <div className="flex flex-wrap gap-1">
                  {oesWlPicks.map((p) => (
                    <span key={p.wavelength} className="rounded-md border border-border px-2 py-0.5 font-mono text-xs text-muted-foreground">
                      {Number(p.wavelength).toFixed(1)}nm · Δ{Number(p.delta_spectrum).toFixed(3)}
                    </span>
                  ))}
                </div>
              </div>
            ) : null
          ) : (
            <>
              <TttmSpiderSensorTable sensors={chamber.sensors}
                selectedCategory={radarLevel.type === "sub" ? subKey : ""}
                onClearCategory={() => setSubKey("")} onSelectSensor={setSelectedSensor}
                selectedSensorKey={selectedSensor?.sensor} />
              {selectedSensor ? (
                <TttmSpiderSensorDetail refSel={selected.ref} comp={selected.comp} dataType={dataType}
                  sensorKey={selectedSensor.sensor} onClose={() => setSelectedSensor(null)} />
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}
