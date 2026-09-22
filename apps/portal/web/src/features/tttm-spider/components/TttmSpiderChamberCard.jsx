// 파일 경로: src/features/tttm-spider/components/TttmSpiderChamberCard.jsx
// 챔버 종합 health/등급 카드입니다.
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

function gradeBadgeVariant(grade) {
  if (grade === "심각") return "destructive"
  if (grade === "주의") return "default"
  return "secondary"
}

function healthTone(grade) {
  if (grade === "심각") return "text-destructive"
  if (grade === "주의") return "text-chart-4"
  return "text-chart-2"
}

export function TttmSpiderChamberCard({ chamber }) {
  if (!chamber) return null
  const grade = chamber.grade ?? "정상"
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-col gap-1">
            <CardTitle className="text-base">{chamber.name}</CardTitle>
            <CardDescription>챔버 종합 건강도</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {chamber.self_compare ? <Badge variant="outline">자가비교</Badge> : null}
            {chamber.recipe_mixed_warning ? <Badge variant="outline">recipe 혼재</Badge> : null}
            <Badge variant={gradeBadgeVariant(grade)}>{grade}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className={`text-4xl font-bold tabular-nums ${healthTone(grade)}`}>
            {Number(chamber.score ?? 0).toFixed(1)}
          </span>
          <span className="text-sm text-muted-foreground">/ 100</span>
        </div>
        {chamber.worst_category ? (
          <p className="mt-2 text-xs text-muted-foreground">
            최저 카테고리: <span className="text-foreground">{chamber.worst_category}</span>
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
