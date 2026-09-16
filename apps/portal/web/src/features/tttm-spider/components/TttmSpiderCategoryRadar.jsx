// 파일 경로: src/features/tttm-spider/components/TttmSpiderCategoryRadar.jsx
// 카테고리/스텝 레이더 (top→sub 드릴다운 지원). 축·칩 클릭 시 onSelect.
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// keys: string[], values: {k:health}, labels: {k:label}, counts?: {k:n}
export function TttmSpiderCategoryRadar({
  keys, values, labels, counts, selected, onSelect, onBack, title, hint,
}) {
  const list = keys ?? []
  const data = list.map((k) => ({
    key: k,
    category: (labels && labels[k]) || k,
    health: Number(values?.[k] ?? 100),
  }))

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{title ?? "카테고리 건강도 레이더"}</CardTitle>
          {onBack ? <Button variant="ghost" size="sm" onClick={onBack}>← 상위</Button> : null}
        </div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-sm text-muted-foreground">표시할 항목이 없습니다.</p>
        ) : (
          <>
            <div className="h-72 w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={data} outerRadius="72%">
                  <PolarGrid stroke="var(--border)" />
                  <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                  <Radar name="health" dataKey="health" stroke="var(--chart-1)" fill="var(--chart-1)" fillOpacity={0.35} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {data.map((d) => {
                const n = counts?.[d.key]
                return (
                  <button
                    key={d.key}
                    type="button"
                    onClick={() => onSelect && onSelect(d.key)}
                    className={`rounded-md border px-2 py-0.5 text-xs ${
                      selected === d.key ? "border-chart-1 text-chart-1" : "border-border text-muted-foreground"
                    }`}
                  >
                    {d.category}{n ? ` (${n})` : ""} · {d.health.toFixed(0)}
                  </button>
                )
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
