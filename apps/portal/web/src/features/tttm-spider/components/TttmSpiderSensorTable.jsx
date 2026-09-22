// 파일 경로: src/features/tttm-spider/components/TttmSpiderSensorTable.jsx
// 센서 랭킹 테이블(own_score 내림차순)입니다. 선택 카테고리로 필터링.
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

function gradeBadgeVariant(grade) {
  if (grade === "심각") return "destructive"
  if (grade === "주의") return "default"
  return "secondary"
}

export function TttmSpiderSensorTable({ sensors, selectedCategory, onClearCategory, onSelectSensor, selectedSensorKey }) {
  const rows = (sensors ?? []).filter(
    (s) => !selectedCategory || String(s.category) === String(selectedCategory),
  )
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">센서 랭킹 (own_score)</CardTitle>
          {selectedCategory ? (
            <div className="flex items-center gap-2">
              <Badge variant="outline">{selectedCategory}</Badge>
              <Button variant="ghost" size="sm" onClick={onClearCategory}>전체</Button>
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">표시할 센서가 없습니다.</p>
        ) : (
          <div className="max-h-96 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>센서</TableHead>
                  <TableHead>카테고리</TableHead>
                  <TableHead className="text-right">own_score</TableHead>
                  <TableHead>주요 축</TableHead>
                  <TableHead>등급</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((s) => (
                  <TableRow
                    key={s.sensor}
                    onClick={() => onSelectSensor && onSelectSensor(s)}
                    className={`cursor-pointer ${selectedSensorKey === s.sensor ? "bg-accent" : ""}`}
                  >
                    <TableCell className="font-medium">{s.sensor}</TableCell>
                    <TableCell className="text-muted-foreground">{s.category}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {Number(s.deviation ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{s.dominant_axis ?? "-"}</TableCell>
                    <TableCell>
                      <Badge variant={gradeBadgeVariant(s.grade)}>{s.grade ?? "정상"}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
