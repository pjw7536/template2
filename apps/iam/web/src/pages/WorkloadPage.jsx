import { useEffect, useState } from "react"

import { NativeSelect } from "@/components/NativeSelect"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/table"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { DEFAULT_WEIGHTS, METRICS, scorePerPerson, workloadTotal } from "@/lib/workload"
import { loadLineHeadcount, workloadMonth } from "@/lib/workloadApi"

const integer = new Intl.NumberFormat("ko-KR")
const score = new Intl.NumberFormat("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const absent = "—"

function currentMonth() {
  const formatter = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit" })
  return formatter.format(new Date())
}

function displayScore(value) {
  return value == null ? absent : score.format(value)
}

export default function WorkloadPage({ org }) {
  const [month, setMonth] = useState(currentMonth)
  const [teamId, setTeamId] = useState("")

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-4">
      <h2 className="shrink-0 text-xl font-semibold">업무 부하</h2>
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <Label htmlFor="workload-month">기준월</Label>
        <Input id="workload-month" type="month" value={month} min="1000-01" max="9999-12"
          className="w-44" onChange={({ target }) => setMonth(target.value)} />
      </div>
      {/^[1-9]\d{3}-(0[1-9]|1[0-2])$/.test(month) ? (
        <MonthlyWorkload key={month} month={month} org={org} teamId={teamId} setTeamId={setTeamId} />
      ) : <p className="text-sm text-muted-foreground">비교할 기준월을 선택하세요.</p>}
    </div>
  )
}

function MonthlyWorkload({ month, org, teamId, setTeamId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState("")
  const [attempt, setAttempt] = useState(0)
  const [editor, setEditor] = useState(null)
  const [order, setOrder] = useState("descending")

  useEffect(() => {
    const controller = new AbortController()
    workloadMonth(month, { signal: controller.signal })
      .then((payload) => {
        if (!controller.signal.aborted) setData(payload)
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message)
      })
    return () => controller.abort()
  }, [month, attempt])

  function reload() {
    setEditor(null)
    setData(null)
    setError("")
    setAttempt((value) => value + 1)
  }

  async function save(changes) {
    const payload = await workloadMonth(month, {
      data: { revision: data.revision, weights: data.weights ?? DEFAULT_WEIGHTS, records: data.records, ...changes },
    })
    setData(payload)
    setEditor(null)
  }

  if (error) return <div role="alert" className="flex items-center gap-3 text-sm text-destructive">
    {error}<Button variant="outline" size="sm" onClick={reload}>다시 불러오기</Button>
  </div>
  if (!data) return <Skeleton className="h-24 w-full" aria-label="업무 부하 불러오는 중" />

  const weights = data.weights ?? DEFAULT_WEIGHTS
  const teamNames = new Map(org.teams.map(({ id, name }) => [id, name]))
  for (const record of data.records) {
    if (!teamNames.has(record.teamId)) teamNames.set(record.teamId, record.team)
  }
  const selectedTeamId = teamNames.has(teamId) ? teamId : teamNames.keys().next().value
  const team = org.teams.find(({ id }) => id === selectedTeamId)
  const records = new Map(data.records.filter((record) => record.teamId === selectedTeamId)
    .map((record) => [record.lineId, record]))
  const lines = new Map((team?.lines ?? []).map((line) => [line.id, line]))
  const keys = new Set([...lines.keys(), ...records.keys()])
  const rows = Array.from(keys, (id) => {
    const line = lines.get(id)
    const record = records.get(id)
    const total = record ? workloadTotal(record, weights) : null
    return {
      id, line, record, total, teamId: selectedTeamId,
      label: line?.name ?? record.line,
      perPerson: record ? scorePerPerson(total, record.headcount) : null,
    }
  })
  rows.sort((a, b) => {
    if (a.perPerson == null || b.perPerson == null) {
      if (a.perPerson != null) return -1
      if (b.perPerson != null) return 1
      return a.label.localeCompare(b.label, "ko")
    }
    return (order === "descending" ? b.perPerson - a.perPerson : a.perPerson - b.perPerson)
      || a.label.localeCompare(b.label, "ko")
  })

  return (
    <>
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <Label htmlFor="workload-team">팀</Label>
        <NativeSelect id="workload-team" value={selectedTeamId ?? ""} disabled={!teamNames.size}
          onChange={({ target }) => setTeamId(target.value)}>
          {!teamNames.size && <option value="">팀 없음</option>}
          {[...teamNames].map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </NativeSelect>
        <Button variant="outline" onClick={(event) => setEditor({ kind: "weights", trigger: event.currentTarget })}>가중치 설정</Button>
        <span className="text-xs text-muted-foreground">
          {data.weights ? "이 달의 공통 가중치" : "초기 가중치"} · {METRICS.map(({ key, label }) => `${label} ${weights[key]}`).join(" · ")}
        </span>
      </div>
      <Card className="min-h-0 min-w-0 flex-1 gap-0 overflow-hidden py-0">
        <Table stickyHeader className="w-max min-w-full [&_th]:text-center [&_td]:text-center" aria-label="라인별 업무 부하 비교">
          <TableHeader>
            <TableRow className="h-12 [&>th]:bg-muted [&>th]:text-xs [&>th]:text-muted-foreground [&>th]:shadow-[inset_0_-1px_0_var(--border)]">
              <TableHead>라인</TableHead>
              <TableHead>기준 배치 인원</TableHead>
              {METRICS.map(({ key, label, unit }) => <TableHead key={key}>{label} ({unit})</TableHead>)}
              <TableHead>월 전체 클릭 수</TableHead>
              <TableHead>월 전체 WF Move</TableHead>
              <TableHead>공정 난이도</TableHead>
              <TableHead>1인 평균 근무시간</TableHead>
              <TableHead>SCI 점수</TableHead>
              <TableHead className="border-l">총 부하</TableHead>
              <TableHead aria-sort={order}>
                <Button type="button" variant="ghost" size="sm" className="relative px-5 text-xs"
                  onClick={() => setOrder((value) => value === "descending" ? "ascending" : "descending")}>
                  1인당 업무부하
                  <span aria-hidden="true" className="absolute right-1.5">{order === "descending" ? "↓" : "↑"}</span>
                </Button>
              </TableHead>
              <TableHead>관리</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => <WorkloadRow key={row.id} row={row}
              onEdit={(event) => setEditor({ kind: "line", row, trigger: event.currentTarget })} />)}
            {!rows.length && <TableRow><TableCell colSpan={16} className="py-6 text-center text-muted-foreground">
              이 팀에 표시할 라인이 없습니다.
            </TableCell></TableRow>}
          </TableBody>
        </Table>
      </Card>
      {editor?.kind === "weights" && <WeightsEditor weights={weights} trigger={editor.trigger} onClose={() => setEditor(null)}
        onSave={(next) => save({ weights: next })} onReload={reload} />}
      {editor?.kind === "line" && <LineEditor row={editor.row} trigger={editor.trigger} onClose={() => setEditor(null)} onReload={reload}
        onSave={(record) => save({ records: [
          ...data.records.filter(({ teamId, lineId }) => teamId !== record.teamId || lineId !== record.lineId), record,
        ] })} />}
    </>
  )
}

function WorkloadRow({ row, onEdit }) {
  const { record } = row
  return (
    <TableRow className="h-12 tabular-nums">
      <TableCell className="font-medium">{row.label}</TableCell>
      <TableCell>{record ? `${integer.format(record.headcount)}명` : absent}</TableCell>
      {METRICS.map(({ key }) => <TableCell key={key}>{record ? integer.format(record[key]) : absent}</TableCell>)}
      <TableCell>{record?.totalClicks == null ? absent : integer.format(record.totalClicks)}</TableCell>
      <TableCell>{record?.totalWfMoves == null ? absent : integer.format(record.totalWfMoves)}</TableCell>
      <TableCell>{record?.difficulty || absent}</TableCell>
      <TableCell>{record?.averageHours == null ? absent : `${integer.format(record.averageHours)}시간`}</TableCell>
      <TableCell>{record?.sciScore ?? absent}</TableCell>
      <TableCell className="border-l">{displayScore(row.total)}</TableCell>
      <TableCell className="font-semibold">{displayScore(row.perPerson)}</TableCell>
      <TableCell><Button variant="outline" size="sm" className="min-w-14" onClick={onEdit}
        aria-label={`${row.label} ${record ? "수정" : "입력"}`}>{record ? "수정" : "입력"}</Button></TableCell>
    </TableRow>
  )
}

function EditDialog({ title, description, trigger, onClose, onReload, submit, children }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    setBusy(true)
    setError(null)
    try {
      await submit(fields)
    } catch (failure) {
      setError(failure)
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose() }}>
      <DialogContent showCloseButton={!busy} onCloseAutoFocus={(event) => {
        if (trigger.isConnected) {
          event.preventDefault()
          trigger.focus()
        }
      }}>
        <DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <fieldset disabled={busy} className="flex min-w-0 flex-col gap-3">{children}</fieldset>
          {error && <div role="alert" className="text-sm text-destructive">{error.message}</div>}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={busy} onClick={onClose}>취소</Button>
            {error?.status === 409 && <Button type="button" variant="outline" onClick={onReload}>다시 불러오기</Button>}
            <Button type="submit" disabled={busy || error?.status === 409}>{busy ? "저장 중…" : "저장"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function NumberField({ name, label, value = "", step = 1, max = 1_000_000, required = true, onChange }) {
  const inputValue = onChange ? { value, onChange } : { defaultValue: value }
  return <div className="flex min-w-0 flex-col gap-1.5">
    <Label htmlFor={`workload-field-${name}`}>{label}</Label>
    <Input id={`workload-field-${name}`} name={name} type="number" min={0} max={max}
      step={step} required={required} {...inputValue} />
  </div>
}

function WeightsEditor({ weights, onSave, ...dialog }) {
  async function submit(fields) {
    const next = Object.fromEntries(METRICS.map(({ key }) => [key, Number(fields.get(key))]))
    if (!Object.values(next).some(Boolean)) throw new Error("가중치를 하나 이상 0보다 크게 입력하세요.")
    await onSave(next)
  }

  return (
    <EditDialog {...dialog} title="공통 가중치" description="선택한 월의 모든 라인에 같은 가중치를 적용합니다."
      submit={submit}>
      <div className="grid grid-cols-2 gap-3">
        {METRICS.map(({ key, label, unit }) => <NumberField key={key} name={key}
          label={`${label} (1${unit}당)`} value={weights[key]} step="any" max={1000} />)}
      </div>
    </EditDialog>
  )
}

function LineEditor({ row, onSave, ...dialog }) {
  const { record, line } = row
  const [headcount, setHeadcount] = useState(record?.headcount ?? "")
  const [lookup, setLookup] = useState("")

  useEffect(() => {
    if (record || !line) return undefined
    let active = true
    loadLineHeadcount(line)
      .then((count) => {
        if (active) setHeadcount((current) => current === "" ? count : current)
      })
      .catch(() => { if (active) setLookup("조직 인원을 조회할 수 없습니다. 배치 인원을 직접 입력하세요.") })
    return () => { active = false }
  }, [line, record])

  async function submit(fields) {
    const hours = fields.get("averageHours")
    const sciScore = fields.get("sciScore")
    const totalClicks = fields.get("totalClicks")
    const totalWfMoves = fields.get("totalWfMoves")
    const metrics = Object.fromEntries(METRICS.map(({ key }) => [key, Number(fields.get(key))]))
    await onSave({
      ...record,
      teamId: record?.teamId ?? row.teamId, team: record?.team ?? line.team,
      lineId: row.id, line: record?.line ?? line.name,
      headcount: Number(fields.get("headcount")),
      ...metrics,
      difficulty: fields.get("difficulty"),
      averageHours: hours === "" ? null : Number(hours),
      sciScore: sciScore === "" ? null : Number(sciScore),
      totalClicks: totalClicks === "" ? null : Number(totalClicks),
      totalWfMoves: totalWfMoves === "" ? null : Number(totalWfMoves),
      notes: fields.get("notes").trim(),
    })
  }

  return (
    <EditDialog {...dialog} title={`${row.label} 업무 수치`} description="기준월의 배치 인원과 발생 건수를 입력하세요."
      submit={submit}>
      <div className="grid grid-cols-2 gap-3">
        <NumberField name="headcount" label="기준 배치 인원 (명)" value={headcount}
          onChange={({ target }) => setHeadcount(target.value)} />
        <NumberField name="averageHours" label="1인 평균 근무시간 (시간)" value={record?.averageHours ?? ""}
          step={0.1} max={744} required={false} />
        {METRICS.map(({ key, label, unit }) => <NumberField key={key} name={key} label={`${label} (${unit})`}
          value={record?.[key] ?? ""} />)}
        <NumberField name="totalClicks" label="월 전체 클릭 수" value={record?.totalClicks ?? ""}
          max={Number.MAX_SAFE_INTEGER} required={false} />
        <NumberField name="totalWfMoves" label="월 전체 WF Move" value={record?.totalWfMoves ?? ""}
          max={Number.MAX_SAFE_INTEGER} required={false} />
        <NumberField name="sciScore" label="SCI 점수 (회사생활 만족도)" value={record?.sciScore ?? ""}
          step="any" max={Number.MAX_SAFE_INTEGER} required={false} />
      </div>
      {lookup && <p role="status" className="text-xs text-muted-foreground">{lookup}</p>}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="workload-difficulty">공정 난이도</Label>
        <NativeSelect id="workload-difficulty" name="difficulty" defaultValue={record?.difficulty ?? ""}>
          <option value="">미입력</option>
          {["낮음", "보통", "높음"].map((value) => <option key={value}>{value}</option>)}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="workload-notes">재배치 참고사항</Label>
        <textarea id="workload-notes" name="notes" rows={3} maxLength={1000} defaultValue={record?.notes ?? ""}
          className="rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" />
      </div>
    </EditDialog>
  )
}
