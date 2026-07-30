// 파일 경로: src/features/tttm-spider/components/TttmSpiderLotwfSelector.jsx
// lotwf 선택 패널(카드 꽉 채움, 내부 스크롤). 날짜 범위는 카드/전역 datepicker에서 이미 필터되어 items로 들어온다.
// - 드래그로 여러 행 선택/해제. - REF·COMP 동일 설비면 COMP선택=빨강/REF선택=파랑 배지·테두리.
import { useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { lotwfKey } from "../utils/selection"

export function TttmSpiderLotwfSelector({
  title, tone, side, items, compSelected, refSelected, onToggle, onToggleMany, loading, emptyText,
}) {
  const [recipe, setRecipe] = useState("__all__")
  const [lotSearch, setLotSearch] = useState("")
  const dragRef = useRef(null) // "select" | "deselect" | null

  useEffect(() => {
    const up = () => { dragRef.current = null }
    window.addEventListener("mouseup", up)
    return () => window.removeEventListener("mouseup", up)
  }, [])

  const recipes = useMemo(() => [...new Set(items.map((i) => i.recipe_id))].sort(), [items])
  const filtered = useMemo(
    () => items.filter((i) =>
      (recipe === "__all__" || i.recipe_id === recipe)
      && (!lotSearch || String(i.lot_id).toLowerCase().includes(lotSearch.toLowerCase()))),
    [items, recipe, lotSearch],
  )
  const compSet = useMemo(() => new Set((compSelected ?? []).map(lotwfKey)), [compSelected])
  const refSet = useMemo(() => new Set((refSelected ?? []).map(lotwfKey)), [refSelected])
  const activeSet = side === "ref" ? refSet : compSet
  const selInFiltered = filtered.filter((i) => activeSet.has(lotwfKey(i))).length

  const applyDrag = (l, activeOn) => {
    const mode = dragRef.current
    if (mode === "select" && !activeOn) onToggle(l)
    else if (mode === "deselect" && activeOn) onToggle(l)
  }
  const startDrag = (l, activeOn, e) => {
    e.preventDefault()
    dragRef.current = activeOn ? "deselect" : "select"
    applyDrag(l, activeOn)
  }

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col gap-0 overflow-hidden rounded-lg py-0">
      <div className="flex min-h-11 shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-muted/50 px-4 py-2">
        <CardTitle className={`text-[15px] ${tone}`}>{title}</CardTitle>
        {items.length ? (
          <div className="flex flex-wrap items-center gap-2">
              <div className="w-24">
                <Select value={recipe} onValueChange={setRecipe}>
                  <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">recipe: 전체</SelectItem>
                    {recipes.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Input className="h-8 w-24" placeholder="lot 검색" value={lotSearch} onChange={(e) => setLotSearch(e.target.value)} />
              <Button variant="ghost" size="sm" onClick={() => onToggleMany(filtered, true)}>전체선택</Button>
              <Button variant="ghost" size="sm" onClick={() => onToggleMany(filtered, false)}>해제</Button>
              <span className="font-mono text-xs text-muted-foreground">{selInFiltered}/{filtered.length} · 전체 {items.length}</span>
            </div>
        ) : null}
      </div>
      <CardContent className="flex min-h-0 flex-1 flex-col overflow-hidden p-3">
        {loading ? (
          <p className="text-sm text-muted-foreground">불러오는 중…</p>
        ) : !items.length ? (
          <p className="text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          <div className="flex min-h-0 flex-1 select-none flex-col gap-1 overflow-auto pr-1">
            {filtered.map((l) => {
              const k = lotwfKey(l)
              const compOn = compSet.has(k)
              const refOn = refSet.has(k)
              const activeOn = side === "ref" ? refOn : compOn
              const border = compOn && refOn ? "border-chart-3"
                : compOn ? "border-destructive" : refOn ? "border-chart-1" : "border-border"
              return (
                <div key={k} role="checkbox" aria-checked={activeOn} tabIndex={0}
                  onMouseDown={(e) => startDrag(l, activeOn, e)}
                  onMouseEnter={() => { if (dragRef.current) applyDrag(l, activeOn) }}
                  onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); onToggle(l) } }}
                  className={`flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1 text-xs ${border} ${activeOn ? "bg-accent" : ""}`}>
                  <input type="checkbox" checked={activeOn} readOnly tabIndex={-1} className="pointer-events-none accent-chart-1" />
                  <span className="font-mono font-medium text-foreground">{l.eqp}·{l.chamber}·{l.lot_id}·wf{l.slot_no}</span>
                  <span className="text-muted-foreground">{l.recipe_id}</span>
                  {compOn ? <span className="rounded bg-accent px-1 text-[10px] font-semibold text-destructive">COMP</span> : null}
                  {refOn ? <span className="rounded bg-accent px-1 text-[10px] font-semibold text-chart-1">REF</span> : null}
                  <span className="ml-auto font-mono text-muted-foreground">{l.tkin_time}</span>
                  {l.is_golden ? <span className="text-chart-2">golden</span> : null}
                </div>
              )
            })}
            {filtered.length === 0 ? <p className="py-2 text-xs text-muted-foreground">필터에 맞는 lotwf가 없습니다.</p> : null}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
