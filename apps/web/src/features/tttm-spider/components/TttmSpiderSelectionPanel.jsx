// 파일 경로: src/features/tttm-spider/components/TttmSpiderSelectionPanel.jsx
// REF(단일) + COMP(챔버 체크박스 다중) 선택 → "목록에 추가". multi-COMP.
import { useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { fetchTttmComboOptions, tttmSpiderQueryKeys } from "../api"
import { useTttmComboOptions } from "../hooks/useTttmSpiderQueries"
import { intersectLists, isChamberComplete } from "../utils/selection"

const TYPE_OPTIONS = [
  { value: "process", label: "PW (process)" },
  { value: "ag", label: "NPW (ag)" },
]
const DATA_TYPE_OPTIONS = [
  { value: "trace", label: "TRACE" },
  { value: "oes", label: "OES" },
]

function LabeledSelect({ label, value, placeholder, items, disabled, onChange }) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Select value={value || undefined} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {items.map((it) => {
            const val = typeof it === "string" ? it : it.value
            const lbl = typeof it === "string" ? it : it.label
            return (
              <SelectItem key={val} value={val}>
                {lbl}
              </SelectItem>
            )
          })}
        </SelectContent>
      </Select>
    </label>
  )
}

// REF 전용 단일 캐스케이드(line→eqp→chamber→date).
function RefPicker({ value, onChange }) {
  const lineQ = useTttmComboOptions({ source: "ref", level: "line" })
  const eqpQ = useTttmComboOptions({ source: "ref", level: "eqp", line: value.line, enabled: Boolean(value.line) })
  const chamberQ = useTttmComboOptions({
    source: "ref", level: "chamber", line: value.line, eqp: value.eqp, enabled: Boolean(value.line && value.eqp),
  })
  const dateQ = useTttmComboOptions({
    source: "ref", level: "date", line: value.line, eqp: value.eqp, chamber: value.chamber,
    enabled: Boolean(value.line && value.eqp && value.chamber),
  })
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      <LabeledSelect label="Line" placeholder="line" value={value.line} items={lineQ.data ?? []}
        onChange={(line) => onChange({ line, eqp: "", chamber: "", date: "" })} />
      <LabeledSelect label="EQP" placeholder="eqp" value={value.eqp} items={eqpQ.data ?? []} disabled={!value.line}
        onChange={(eqp) => onChange({ ...value, eqp, chamber: "", date: "" })} />
      <LabeledSelect label="Chamber" placeholder="chamber" value={value.chamber} items={chamberQ.data ?? []} disabled={!value.eqp}
        onChange={(chamber) => onChange({ ...value, chamber, date: "" })} />
      <LabeledSelect label="Date" placeholder="date" value={value.date} items={dateQ.data ?? []} disabled={!value.chamber}
        onChange={(date) => onChange({ ...value, date })} />
    </div>
  )
}

export function TttmSpiderSelectionPanel({ refChamber, onRefChange, dataType, onDataTypeChange, onAddToList }) {
  const [compLine, setCompLine] = useState("")
  const [compEqp, setCompEqp] = useState("")
  const [checked, setChecked] = useState([]) // 체크된 chamber 이름들
  const [compDate, setCompDate] = useState("")
  const [compType, setCompType] = useState("process")

  const lineQ = useTttmComboOptions({ source: "comp", level: "line" })
  const eqpQ = useTttmComboOptions({ source: "comp", level: "eqp", line: compLine, enabled: Boolean(compLine) })
  const chamberQ = useTttmComboOptions({
    source: "comp", level: "chamber", line: compLine, eqp: compEqp, enabled: Boolean(compLine && compEqp),
  })

  // COMP 날짜: 체크된 챔버들의 공통(교집합) 날짜만.
  const dateQueries = useQueries({
    queries: [...checked].sort().map((ch) => ({
      queryKey: tttmSpiderQueryKeys.comboOptions("comp", "date", `${compLine}|${compEqp}|${ch}`),
      queryFn: () => fetchTttmComboOptions({ source: "comp", level: "date", line: compLine, eqp: compEqp, chamber: ch }),
      enabled: Boolean(compLine && compEqp && ch),
      select: (d) => d?.items ?? [],
      staleTime: 60 * 1000,
    })),
  })
  const dateOptions = useMemo(() => {
    if (!checked.length) return []
    const lists = dateQueries.map((q) => q.data ?? [])
    if (lists.some((l) => l.length === 0)) return dateQueries.every((q) => q.isSuccess) ? intersectLists(lists) : []
    return intersectLists(lists)
  }, [dateQueries, checked])

  const toggleChamber = (ch) => {
    setChecked((prev) => (prev.includes(ch) ? prev.filter((x) => x !== ch) : [...prev, ch]))
    setCompDate("")
  }

  const refReady = isChamberComplete(refChamber)
  const canAdd = refReady && compLine && compEqp && checked.length > 0 && compDate && compType

  const handleAdd = () => {
    if (!canAdd) return
    const entries = checked.map((ch) => ({
      ref: { ...refChamber },
      comp: { line: compLine, eqp: compEqp, chamber: ch, date: compDate, type: compType },
    }))
    onAddToList(entries)
  }

  const chamberItems = chamberQ.data ?? []

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4">
      {/* REF */}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-chart-1">REF (기준 챔버)</p>
        <RefPicker value={refChamber} onChange={onRefChange} />
      </div>

      {/* COMP */}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-destructive">COMP (비교 대상 · 여러 챔버 선택)</p>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <LabeledSelect label="TYPE" placeholder="type" value={compType} items={TYPE_OPTIONS} onChange={setCompType} />
          <LabeledSelect label="Line" placeholder="line" value={compLine} items={lineQ.data ?? []}
            onChange={(v) => { setCompLine(v); setCompEqp(""); setChecked([]); setCompDate("") }} />
          <LabeledSelect label="EQP" placeholder="eqp" value={compEqp} items={eqpQ.data ?? []} disabled={!compLine}
            onChange={(v) => { setCompEqp(v); setChecked([]); setCompDate("") }} />
          <LabeledSelect label="Date" placeholder="date" value={compDate} items={dateOptions} disabled={!checked.length}
            onChange={setCompDate} />
        </div>

        {/* 챔버 체크박스 목록 */}
        <div className="rounded-md border border-border bg-background p-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              비교할 CHAMBER 선택 · {checked.length}개
            </span>
            {chamberItems.length > 0 ? (
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" onClick={() => { setChecked(chamberItems); setCompDate("") }}>전체</Button>
                <Button variant="ghost" size="sm" onClick={() => { setChecked([]); setCompDate("") }}>해제</Button>
              </div>
            ) : null}
          </div>
          {chamberItems.length === 0 ? (
            <p className="text-xs text-muted-foreground">Line/EQP를 먼저 선택하세요.</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {chamberItems.map((ch) => {
                const on = checked.includes(ch)
                return (
                  <button
                    key={ch}
                    type="button"
                    onClick={() => toggleChamber(ch)}
                    className={`rounded-md border px-2.5 py-1 text-xs ${
                      on ? "border-chart-1 bg-accent text-chart-1" : "border-border text-muted-foreground"
                    }`}
                  >
                    {ch}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* DATA TYPE + 추가 */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-40">
          <LabeledSelect label="DATA TYPE" placeholder="data type" value={dataType} items={DATA_TYPE_OPTIONS} onChange={onDataTypeChange} />
        </div>
        <Button onClick={handleAdd} disabled={!canAdd}>+ 목록에 추가</Button>
      </div>
    </div>
  )
}
