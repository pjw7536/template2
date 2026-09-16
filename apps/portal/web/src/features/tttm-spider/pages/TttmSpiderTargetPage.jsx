// 파일 경로: src/features/tttm-spider/pages/TttmSpiderTargetPage.jsx
// 3열(열 드래그 리사이즈): 1열 설비선택(행 모델·카드별 datepicker) · 2열 선택카드 lotwf · 3열 Score Summary.
// 셀 = {eqp,chamber,from,to}. 날짜 범위 안의 lotwf만 표시. 전역 datepicker는 새 카드 기본 범위.
import { useId, useRef, useState } from "react"
import { useNavigate, useOutletContext } from "react-router-dom"
import { useQueries } from "@tanstack/react-query"

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

import { TttmSpiderLotwfSelector } from "../components/TttmSpiderLotwfSelector"
import { fetchTttmChambers, fetchTttmDashboardData, fetchTttmLotwf, tttmSpiderQueryKeys } from "../api"
import { useTttmChambers, useTttmEqps, useTttmGolden, useTttmLotwf } from "../hooks/useTttmSpiderQueries"
import { buildDashboardPayload, buildEntriesFromRows, lotwfKey } from "../utils/selection"

const gradeTone = (g) => (g === "심각" ? "text-destructive" : g === "주의" ? "text-chart-4" : "text-chart-2")
const toggleByKey = (arr, item, keyFn) => {
  const k = keyFn(item)
  return arr.some((x) => keyFn(x) === k) ? arr.filter((x) => keyFn(x) !== k) : [...arr, item]
}

// 빈 셀 직접 입력: EQP 자동완성 + 챔버 드롭다운(선택된 eqp의 챔버). PM 미선택=전체 챔버.
function CellInput({ tone, label, eqpOptions, onFill }) {
  const [eqp, setEqp] = useState("")
  const [chamber, setChamber] = useState("__all__")
  const listId = useId()
  const chambers = useTttmChambers(eqp, Boolean(eqp)).data ?? []
  const fill = () => { if (eqp) { onFill(eqp.trim(), chamber === "__all__" ? "" : chamber); setEqp(""); setChamber("__all__") } }
  return (
    <div className="flex h-full min-h-[112px] flex-col justify-center gap-1.5 rounded-md border border-dashed border-border p-2">
      <span className={`text-xs font-semibold ${tone}`}>{label}</span>
      <Input list={listId} className="h-8 text-xs" placeholder="EQP 입력 (예시: ELXX301)" value={eqp}
        onChange={(e) => { setEqp(e.target.value); setChamber("__all__") }} onKeyDown={(e) => { if (e.key === "Enter") fill() }} />
      <datalist id={listId}>{(eqpOptions ?? []).map((x) => <option key={x} value={x} />)}</datalist>
      <div className="flex gap-1">
        <Select value={chamber} onValueChange={setChamber} disabled={!eqp}>
          <SelectTrigger className="h-8 flex-1 text-xs"><SelectValue placeholder="Chamber" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Chamber</SelectItem>
            {chambers.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button className="h-8 shrink-0 px-3" onClick={fill} disabled={!eqp}>+</Button>
      </div>
    </div>
  )
}

function ChamberCard({ side, label, target, active, count, onClick, onRemove, onDateChange, onFill, eqpOptions }) {
  const isComp = side === "comp"
  if (!target) return <CellInput tone={isComp ? "text-destructive" : "text-chart-1"} label={label} eqpOptions={eqpOptions} onFill={onFill} />
  const stop = (e) => e.stopPropagation()
  return (
    <div role="button" tabIndex={0} onClick={onClick} onKeyDown={(e) => { if (e.key === "Enter") onClick() }}
      className={`flex h-full min-h-[112px] flex-col justify-center gap-1.5 rounded-md border px-2.5 py-2 ${active ? "ring-2 ring-chart-1" : ""} ${
        isComp ? "border-destructive/50" : "border-chart-1/50"}`}>
      <div className="flex items-center gap-1.5">
        <span className={`rounded px-1.5 py-0.5 font-mono text-[11px] ${isComp ? "text-destructive" : "text-chart-1"} bg-accent`}>{label}</span>
        <span className="ml-auto shrink-0 text-xs text-muted-foreground">{count}매</span>
        <button type="button" onClick={(e) => { e.stopPropagation(); onRemove() }}
          className="shrink-0 rounded border border-border px-1.5 text-xs text-muted-foreground hover:text-destructive" aria-label={`${label} 삭제`}>×</button>
      </div>
      <span className="break-all font-mono text-sm leading-tight text-foreground">{target.eqp}·{target.chamber}</span>
      <div className="flex items-center gap-1" onClick={stop} onMouseDown={stop} onKeyDown={stop} role="presentation">
        <Input type="date" className="h-7 min-w-0 flex-1 px-1 text-[11px]" value={target.from || ""} onChange={(e) => onDateChange("from", e.target.value)} title="시작" />
        <span className="text-[11px] text-muted-foreground">~</span>
        <Input type="date" className="h-7 min-w-0 flex-1 px-1 text-[11px]" value={target.to || ""} onChange={(e) => onDateChange("to", e.target.value)} title="끝" />
      </div>
    </div>
  )
}

export function TttmSpiderTargetPage() {
  const { selection, patch } = useOutletContext()
  const navigate = useNavigate()
  const goldenEqp = useTttmGolden(null, true).data?.[0]?.eqp
  const eqpOptions = useTttmEqps().data ?? []
  const [active, setActive] = useState(null) // {side, index}
  // 조회 기간 기본값: 최근 7일(-7일 ~ 오늘)
  const [gFrom, setGFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10)
  })
  const [gTo, setGTo] = useState(() => new Date().toISOString().slice(0, 10))

  // 열 너비 드래그 리사이즈 (CSS 변수 + ref; inline style 미사용).
  const gridRef = useRef(null)
  const w1 = useRef(560)
  const w3 = useRef(420)
  const setVar = (name, v) => gridRef.current && gridRef.current.style.setProperty(name, `${v}px`)
  const startResize = (which) => (e) => {
    e.preventDefault()
    const startX = e.clientX
    const base = which === 1 ? w1.current : w3.current
    const move = (ev) => {
      const dx = ev.clientX - startX
      if (which === 1) { const nw = Math.max(320, Math.min(880, base + dx)); w1.current = nw; setVar("--tc1", nw) }
      else { const nw = Math.max(280, Math.min(720, base - dx)); w3.current = nw; setVar("--tc3", nw) }
    }
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up) }
    window.addEventListener("mousemove", move)
    window.addEventListener("mouseup", up)
  }
  const nudge = (which, d) => {
    if (which === 1) { const nw = Math.max(320, Math.min(880, w1.current + d)); w1.current = nw; setVar("--tc1", nw) }
    else { const nw = Math.max(280, Math.min(720, w3.current + d)); w3.current = nw; setVar("--tc3", nw) }
  }

  const activeCell = active ? selection.rows[active.index]?.[active.side] : null
  const activeField = active?.side === "ref" ? "refLotwf" : "compLotwf"
  const activeQ = useTttmLotwf(activeCell?.eqp, activeCell?.chamber, Boolean(activeCell))
  const activeItems = (activeQ.data ?? []).filter((l) =>
    (!activeCell?.from || l.date >= activeCell.from) && (!activeCell?.to || l.date <= activeCell.to))
  const countFor = (field, cell) => selection[field].filter((l) => l.eqp === cell.eqp && l.chamber === cell.chamber).length

  const chambersOf = async (eqp, chamber) => (chamber ? [chamber] : (await fetchTttmChambers(eqp).then((d) => d?.items ?? [])))

  // 빈 셀 직접 입력으로 채우기. PM 미입력이면 그 셀엔 첫 챔버, 나머지 챔버는 새 행/빈 셀로.
  // 채우면 그 챔버의 lotwf(계산에 사용된 집합)를 기간 내에서 자동 선택 → 즉시 계산값 조회.
  const fillCell = async (side, index, eqp, chamber) => {
    const chs = await chambersOf(eqp, chamber)
    if (!chs.length) return
    const other = side === "comp" ? "ref" : "comp"
    const field = side === "comp" ? "compLotwf" : "refLotwf"
    patch((s) => {
      const rows = s.rows.map((r) => ({ ...r }))
      if (rows[index]) rows[index][side] = { eqp, chamber: chs[0], from: gFrom, to: gTo }
      for (const ch of chs.slice(1)) {
        if (rows.some((r) => r[side] && r[side].eqp === eqp && r[side].chamber === ch)) continue
        const cell = { eqp, chamber: ch, from: gFrom, to: gTo }
        const emptyIdx = rows.findIndex((r) => !r[side])
        if (emptyIdx >= 0) rows[emptyIdx][side] = cell
        else rows.push({ [side]: cell, [other]: null })
      }
      return { rows }
    })
    setActive({ side, index })
    // 사용된 lotwf 자동 선택(기간 내 전체).
    const lists = await Promise.all(chs.map((ch) => fetchTttmLotwf(eqp, ch).then((d) => d?.items ?? [])))
    const inRange = lists.flat().filter((l) => (!gFrom || l.date >= gFrom) && (!gTo || l.date <= gTo))
    patch((s) => {
      const have = new Set(s[field].map(lotwfKey))
      return { [field]: [...s[field], ...inRange.filter((l) => !have.has(lotwfKey(l)))] }
    })
  }
  const addRow = () => patch((s) => ({ rows: [...s.rows, { comp: null, ref: null }] }))

  const updateCellDate = (index, side, field, value) => patch((s) => ({
    rows: s.rows.map((r, j) => (j === index ? { ...r, [side]: { ...r[side], [field]: value } } : r)),
  }))

  const fillRefFromFirst = () => patch((s) => {
    const first = s.rows.find((r) => r.ref)?.ref
    if (!first) return {}
    return { rows: s.rows.map((r) => ({ ...r, ref: { ...first } })) }
  })

  const removeCard = (i, side) => {
    const removed = selection.rows[i]?.[side]
    if (!removed) return
    const field = side === "comp" ? "compLotwf" : "refLotwf"
    patch((s) => {
      const rows = s.rows.map((r, j) => (j === i ? { ...r, [side]: null } : r)).filter((r) => r.comp || r.ref)
      const stillUsed = rows.some((r) => r[side] && r[side].eqp === removed.eqp && r[side].chamber === removed.chamber)
      const lotwf = stillUsed ? s[field] : s[field].filter((l) => !(l.eqp === removed.eqp && l.chamber === removed.chamber))
      return { rows: rows.length ? rows : [{ comp: null, ref: null }], [field]: lotwf }
    })
    if (active && active.side === side && active.index === i) setActive(null)
  }
  const removeRow = (i) => {
    const row = selection.rows[i]
    patch((s) => {
      const rows = s.rows.filter((_, j) => j !== i)
      const compUsed = new Set(rows.filter((r) => r.comp).map((r) => `${r.comp.eqp}|${r.comp.chamber}`))
      const refUsed = new Set(rows.filter((r) => r.ref).map((r) => `${r.ref.eqp}|${r.ref.chamber}`))
      const compLotwf = row.comp && !compUsed.has(`${row.comp.eqp}|${row.comp.chamber}`)
        ? s.compLotwf.filter((l) => !(l.eqp === row.comp.eqp && l.chamber === row.comp.chamber)) : s.compLotwf
      const refLotwf = row.ref && !refUsed.has(`${row.ref.eqp}|${row.ref.chamber}`)
        ? s.refLotwf.filter((l) => !(l.eqp === row.ref.eqp && l.chamber === row.ref.chamber)) : s.refLotwf
      return { rows: rows.length ? rows : [{ comp: null, ref: null }], compLotwf, refLotwf }
    })
    setActive(null)
  }
  const clearAll = () => { patch({ rows: [{ comp: null, ref: null }], compLotwf: [], refLotwf: [] }); setActive(null) }

  const toggle = (field, l) => patch((s) => ({ [field]: toggleByKey(s[field], l, lotwfKey) }))
  const toggleMany = (field, list, checked) => patch((s) => {
    if (checked) {
      const have = new Set(s[field].map(lotwfKey))
      return { [field]: [...s[field], ...list.filter((l) => !have.has(lotwfKey(l)))] }
    }
    const keys = new Set(list.map(lotwfKey))
    return { [field]: s[field].filter((l) => !keys.has(lotwfKey(l))) }
  })

  const applyAuto = async (mode) => {
    const compRows = selection.rows.filter((r) => r.comp)
    patch((s) => ({
      rows: s.rows.map((r) => (r.comp
        ? { ...r, ref: mode === "self" ? { eqp: r.comp.eqp, chamber: r.comp.chamber, from: "", to: "" } : (goldenEqp ? { eqp: goldenEqp, chamber: r.comp.chamber, from: "", to: "" } : r.ref) }
        : r)),
    }))
    const refTargets = compRows.map((r) => (mode === "self" ? { eqp: r.comp.eqp, chamber: r.comp.chamber } : { eqp: goldenEqp, chamber: r.comp.chamber })).filter((t) => t.eqp)
    const lists = await Promise.all(refTargets.map((t) => fetchTttmLotwf(t.eqp, t.chamber).then((d) => d?.items ?? [])))
    const all = lists.flat()
    const compRecipes = new Set(selection.compLotwf.map((l) => l.recipe_id))
    const recipeOk = (l) => (compRecipes.size ? compRecipes.has(l.recipe_id) : true)
    let suggested
    if (mode === "self") {
      const minDate = {}
      for (const l of all) { const k = `${l.eqp}|${l.chamber}`; if (!minDate[k] || l.date < minDate[k]) minDate[k] = l.date }
      suggested = all.filter((l) => l.date === minDate[`${l.eqp}|${l.chamber}`] && recipeOk(l))
    } else {
      suggested = all.filter(recipeOk)
    }
    patch({ refLotwf: suggested })
  }

  const { entries } = buildEntriesFromRows(selection.rows, selection.compLotwf, selection.refLotwf)
  const rowReady = (row) => Boolean(row.comp && row.ref
    && countFor("compLotwf", row.comp) > 0 && countFor("refLotwf", row.ref) > 0)
  const readyCount = selection.rows.filter(rowReady).length
  const hasAnyCell = selection.rows.some((r) => r.comp || r.ref)
  const canScore = entries.length > 0 && readyCount === entries.length && entries.length === selection.rows.filter((r) => r.comp && r.ref).length

  const summaryResults = useQueries({
    queries: entries.map((e) => ({
      queryKey: tttmSpiderQueryKeys.dashboardData(`${e.key}::${selection.dataType}`),
      queryFn: () => fetchTttmDashboardData(buildDashboardPayload({
        ref: e.ref, comp: e.comp, dataType: selection.dataType, stage: "P3", traceRecipeId: e.recipe,
      })),
      enabled: entries.length > 0,
      staleTime: 60 * 1000, gcTime: 5 * 60 * 1000, retry: false,
    })),
  })
  const goDetail = (key) => { patch({ focusKey: key }); navigate("score") }
  const anyExists = summaryResults.some((q) => Boolean(q?.data?.bundle))
  const isActive = (side, i) => active && active.side === side && active.index === i

  return (
    <div ref={gridRef}
      className="grid h-full min-h-0 min-w-0 grid-cols-1 gap-3 overflow-hidden p-4 xl:grid-cols-[var(--tc1,560px)_6px_minmax(0,1fr)_6px_var(--tc3,420px)]">
      {/* 1열: 설비 선택 */}
      <Card className="flex h-full min-h-0 flex-col gap-0 overflow-hidden rounded-lg py-0">
        <div className="flex min-h-11 shrink-0 items-center gap-2 border-b bg-muted/50 px-4 py-2">
          <CardTitle className="text-[15px]">설비 선택</CardTitle>
        </div>
        <div className="flex shrink-0 flex-col gap-2 border-b p-3">
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-sm font-medium text-muted-foreground">DATE</span>
            <Input type="date" className="h-8 w-32 px-1 text-xs" value={gFrom} onChange={(e) => setGFrom(e.target.value)} title="시작" />
            <span className="text-muted-foreground">~</span>
            <Input type="date" className="h-8 w-32 px-1 text-xs" value={gTo} onChange={(e) => setGTo(e.target.value)} title="끝" />
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Button variant="outline" size="sm" onClick={addRow}>+ 행 추가</Button>
            <Button variant="outline" size="sm" onClick={() => applyAuto("self")} disabled={!selection.rows.some((r) => r.comp)}>자설비자동</Button>
            <Button variant="outline" size="sm" onClick={() => applyAuto("other")} disabled={!selection.rows.some((r) => r.comp) || !goldenEqp}>타설비자동</Button>
            <Button variant="outline" size="sm" onClick={fillRefFromFirst} disabled={!selection.rows.some((r) => r.ref)}>첫REF로 채우기</Button>
            <Button variant="ghost" size="sm" onClick={clearAll} disabled={!hasAnyCell}>전체 삭제</Button>
          </div>
        </div>
        <CardContent className="min-h-0 flex-1 overflow-auto p-3">
          <div className="flex flex-col gap-3">
            {selection.rows.map((row, i) => {
              const ready = rowReady(row)
              return (
                <div key={i} className={`flex items-stretch gap-2 rounded-lg border p-3 ${ready ? "border-chart-2" : "border-border"}`}>
                  <div className="flex shrink-0 flex-col items-center gap-1">
                    <button type="button" className="rounded-full border border-border px-1.5 text-xs leading-none text-muted-foreground hover:border-destructive hover:text-destructive"
                      onClick={() => removeRow(i)} aria-label="행 삭제" title="행 전체 삭제">×</button>
                    <span className="font-mono text-[11px] text-muted-foreground">#{i + 1}</span>
                    {ready ? <span className="text-[11px] font-semibold text-chart-2" title="준비됨">✓</span> : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <ChamberCard side="comp" label={`COMP${i + 1}`} target={row.comp} active={isActive("comp", i)}
                      count={row.comp ? countFor("compLotwf", row.comp) : 0}
                      onClick={() => row.comp && setActive({ side: "comp", index: i })} onRemove={() => removeCard(i, "comp")}
                      onFill={(e, c) => fillCell("comp", i, e, c)} eqpOptions={eqpOptions}
                      onDateChange={(f, v) => updateCellDate(i, "comp", f, v)} />
                  </div>
                  <span className="self-center shrink-0 text-muted-foreground">↔</span>
                  <div className="min-w-0 flex-1">
                    <ChamberCard side="ref" label={`REF${i + 1}`} target={row.ref} active={isActive("ref", i)}
                      count={row.ref ? countFor("refLotwf", row.ref) : 0}
                      onClick={() => row.ref && setActive({ side: "ref", index: i })} onRemove={() => removeCard(i, "ref")}
                      onFill={(e, c) => fillCell("ref", i, e, c)} eqpOptions={eqpOptions}
                      onDateChange={(f, v) => updateCellDate(i, "ref", f, v)} />
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* 리사이즈 핸들 1 */}
      <button type="button" aria-label="열 너비 조절" onMouseDown={startResize(1)}
        onKeyDown={(e) => { if (e.key === "ArrowLeft") nudge(1, -20); else if (e.key === "ArrowRight") nudge(1, 20) }}
        className="hidden w-full cursor-col-resize rounded bg-border hover:bg-chart-1 xl:block" />

      {/* 2열: 선택 카드 lotwf */}
      <div className="min-h-0 min-w-0">
        {activeCell ? (
          <TttmSpiderLotwfSelector
            key={`${active.side}|${active.index}|${activeCell.eqp}|${activeCell.chamber}`}
            title={`${active.side === "ref" ? "REF" : "COMP"} · ${activeCell.eqp}·${activeCell.chamber} · lotwf`}
            tone={active.side === "ref" ? "text-chart-1" : "text-destructive"}
            side={active.side} items={activeItems} loading={activeQ.isLoading}
            compSelected={selection.compLotwf} refSelected={selection.refLotwf}
            onToggle={(l) => toggle(activeField, l)} onToggleMany={(list, ch) => toggleMany(activeField, list, ch)}
            emptyText="이 기간/챔버에 lotwf가 없습니다." />
        ) : (
          <Card className="flex h-full min-h-0 flex-col overflow-hidden">
            <CardContent className="flex min-h-0 flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
              좌측에서 카드를 선택하면 그 챔버의 lotwf가 여기 나옵니다.
            </CardContent>
          </Card>
        )}
      </div>

      {/* 리사이즈 핸들 2 */}
      <button type="button" aria-label="열 너비 조절" onMouseDown={startResize(2)}
        onKeyDown={(e) => { if (e.key === "ArrowLeft") nudge(2, 20); else if (e.key === "ArrowRight") nudge(2, -20) }}
        className="hidden w-full cursor-col-resize rounded bg-border hover:bg-chart-1 xl:block" />

      {/* 3열: Score Summary */}
      <Card className="flex h-full min-h-0 flex-col gap-0 overflow-hidden rounded-lg py-0">
        <div className="flex min-h-11 shrink-0 items-center justify-between gap-2 border-b bg-muted/50 px-4 py-2">
          <CardTitle className="text-[15px]">Score Summary</CardTitle>
          <div className="flex overflow-hidden rounded-md border border-border">
            {["trace", "oes"].map((dt) => (
              <button key={dt} type="button" onClick={() => patch({ dataType: dt })}
                className={`px-2 py-0.5 text-xs ${selection.dataType === dt ? "bg-accent text-chart-1" : "text-muted-foreground"}`}>{dt.toUpperCase()}</button>
            ))}
          </div>
        </div>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-3">
          <p className="text-xs text-muted-foreground">{entries.length}개 조합 · 준비 {readyCount}행 · 카드 클릭 → 상세</p>
          <p className="text-[11px] text-muted-foreground">이미 계산된 값 조회 · lotwf(사용된 목록)를 바꾸면 재계산 필요</p>
          <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-auto pr-1">
            {entries.length === 0 ? (
              <p className="text-xs text-muted-foreground">각 행의 COMP·REF lotwf를 선택하면 여기에 결과가 나옵니다.</p>
            ) : entries.map((e, i) => {
              const q = summaryResults[i]
              const chamber = q?.data?.bundle?.chambers?.[0]
              const status = q?.isError ? (q.error?.status === 404 ? "notfound" : "error") : chamber ? "ok" : "loading"
              return (
                <button key={e.key} type="button" onClick={() => goDetail(e.key)}
                  className="rounded-md border border-border p-2 text-left hover:border-chart-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-foreground">{e.label}</p>
                    {status === "ok" ? <span className={`font-mono text-lg font-bold ${gradeTone(chamber.grade)}`}>{Number(chamber.score).toFixed(0)}</span>
                      : status === "loading" ? <span className="text-[11px] text-muted-foreground">계산중…</span>
                        : status === "notfound" ? <span className="text-[11px] text-muted-foreground">결과 없음</span>
                          : <span className="text-[11px] text-destructive">오류</span>}
                  </div>
                  <p className="truncate font-mono text-[11px] text-muted-foreground">
                    <span className="text-chart-1">REF {e.refName}</span> vs <span className="text-destructive">{e.compName}</span>
                  </p>
                  {status === "ok" ? <p className={`text-[11px] ${gradeTone(chamber.grade)}`}>{chamber.grade} · 상세 보기 →</p>
                    : status === "notfound" ? <p className="text-[11px] text-muted-foreground">계산된 결과 없음 (재계산 필요)</p> : null}
                </button>
              )
            })}
          </div>
          <div className="flex shrink-0 gap-2">
            <Button className="flex-1" disabled={!canScore} onClick={() => navigate("score")}>전체 상세 →</Button>
            <Button variant="outline" disabled={!anyExists}
              onClick={() => window.alert("재계산 요청은 알고리즘 서버 연동 후 지원됩니다(스텁).")}>재계산</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
