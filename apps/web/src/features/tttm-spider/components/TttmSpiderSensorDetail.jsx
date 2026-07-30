// 파일 경로: src/features/tttm-spider/components/TttmSpiderSensorDetail.jsx
// 센서 드릴다운: REF vs COMP 원파형 / Level / Shape / Noise 탭.
import { useMemo } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

import { useTttmSensorTrace } from "../hooks/useTttmSpiderQueries"

const REF_COLOR = "var(--chart-1)"
const COMP_COLOR = "var(--destructive)"

function Empty({ children }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{children}</p>
}

// 여러 series(동일 Time 그리드 가정) → Recharts 데이터로 병합.
function WaveformChart({ series }) {
  const { data, lines } = useMemo(() => {
    if (!series?.length) return { data: [], lines: [] }
    const maxLen = Math.max(...series.map((s) => s.points.length))
    const lines = series.map((s, i) => ({
      key: `s${i}`, side: s.side, name: `${s.side}·${s.lot_id}/${s.slot_no}`,
    }))
    const data = []
    for (let i = 0; i < maxLen; i++) {
      const row = { t: series[0].points[i]?.[0] ?? i }
      series.forEach((s, j) => { if (s.points[i]) row[`s${j}`] = s.points[i][1] })
      data.push(row)
    }
    return { data, lines }
  }, [series])

  if (!data.length) return <Empty>파형 데이터가 없습니다.</Empty>
  return (
    <div className="h-72 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} tickFormatter={(v) => Number(v).toFixed(1)} />
          <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} width={48} />
          <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 12 }} />
          {lines.map((l) => (
            <Line key={l.key} type="monotone" dataKey={l.key} name={l.name}
              stroke={l.side === "comp" ? COMP_COLOR : REF_COLOR} strokeWidth={1.2}
              dot={false} isAnimationActive={false} opacity={0.75} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// jitter.parquet 의 ref/comp 웨이퍼별 값(level 또는 jitter_rms)을 strip plot 으로.
function StripPlot({ jitter, field, unit }) {
  const { ref, comp } = useMemo(() => {
    const pick = (rows) => (rows ?? []).map((r) => ({ x: 0, y: Number(r[field]) })).filter((p) => Number.isFinite(p.y))
    const r = pick(jitter?.ref).map((p) => ({ ...p, x: 0 }))
    const c = pick(jitter?.comp).map((p) => ({ ...p, x: 1 }))
    return { ref: r, comp: c }
  }, [jitter, field])

  if (!ref.length && !comp.length) return <Empty>{unit} 원본 데이터(decomp)가 없습니다.</Empty>
  return (
    <div className="h-72 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" domain={[-0.5, 1.5]} ticks={[0, 1]}
            tickFormatter={(v) => (v === 0 ? "REF" : "COMP")} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
          <YAxis type="number" dataKey="y" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} width={56} />
          <ZAxis range={[60, 60]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 12 }} />
          <Scatter name="REF" data={ref} fill={REF_COLOR} />
          <Scatter name="COMP" data={comp} fill={COMP_COLOR} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

// shape.parquet: REF tube(q50/usl/lsl) + COMP 대표 곡선(phase 0~99).
function ShapeChart({ shape }) {
  const data = useMemo(() => {
    const tube = shape?.tube
    if (!tube?.q50) return []
    const comp = shape?.comp_curves?.[0]?.values
    return tube.q50.map((q, i) => ({
      phase: i, q50: q,
      usl: tube.usl?.[i], lsl: tube.lsl?.[i],
      comp: comp?.[i],
    }))
  }, [shape])

  if (!data.length) return <Empty>Shape 궤적 데이터(decomp)가 없습니다.</Empty>
  return (
    <div className="h-72 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="phase" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
          <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} width={48} />
          <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 12 }} />
          <Line type="monotone" dataKey="usl" stroke="var(--muted-foreground)" strokeDasharray="4 3" strokeWidth={1} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="lsl" stroke="var(--muted-foreground)" strokeDasharray="4 3" strokeWidth={1} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="q50" stroke="var(--chart-2)" strokeDasharray="5 4" strokeWidth={1.4} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="comp" stroke={COMP_COLOR} strokeWidth={1.8} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function TttmSpiderSensorDetail({ refSel, comp, dataType, sensorKey, onClose }) {
  const payload = useMemo(
    () => ({ ref: refSel, comp, dataType, sensorKey }),
    [refSel, comp, dataType, sensorKey],
  )
  const traceKey = JSON.stringify(payload)
  const query = useTttmSensorTrace(payload, traceKey, Boolean(sensorKey))

  const data = query.data
  const decomp = data?.decomp

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">
            <span className="font-mono">{sensorKey}</span>
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              REF {data?.ref_label ?? ""} vs COMP {data?.comp_label ?? ""}
            </span>
          </CardTitle>
          {onClose ? (
            <button type="button" onClick={onClose} className="rounded border border-border px-2 text-xs text-muted-foreground">닫기</button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <Empty>불러오는 중…</Empty>
        ) : query.isError ? (
          <Empty>조회 실패: {query.error?.message ?? "오류"}</Empty>
        ) : (
          <Tabs defaultValue="wave">
            <TabsList>
              <TabsTrigger value="wave">REF vs COMP</TabsTrigger>
              <TabsTrigger value="level">Level</TabsTrigger>
              <TabsTrigger value="shape">Shape</TabsTrigger>
              <TabsTrigger value="noise">Noise</TabsTrigger>
            </TabsList>
            <TabsContent value="wave">
              <WaveformChart series={data?.series} />
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="text-chart-1">REF</span> · <span className="text-destructive">COMP</span> 원파형 (line = lot/slot)
              </p>
            </TabsContent>
            <TabsContent value="level"><StripPlot jitter={decomp?.jitter} field="level" unit="Level" /></TabsContent>
            <TabsContent value="shape"><ShapeChart shape={decomp?.shape} /></TabsContent>
            <TabsContent value="noise"><StripPlot jitter={decomp?.jitter} field="jitter_rms" unit="Noise" /></TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  )
}
