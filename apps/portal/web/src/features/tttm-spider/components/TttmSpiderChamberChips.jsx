// 파일 경로: src/features/tttm-spider/components/TttmSpiderChamberChips.jsx
// 조회된 COMP 챔버들을 칩으로 나열. 클릭 → 상세 선택, ×로 제거.
import { Button } from "@/components/ui/button"

function toneClasses(grade, selected) {
  const base = selected ? "border-chart-1" : "border-border"
  if (grade === "심각") return `${base} text-destructive`
  if (grade === "주의") return `${base} text-chart-4`
  if (grade === "정상") return `${base} text-chart-2`
  return `${base} text-muted-foreground`
}

export function TttmSpiderChamberChips({ items, selectedKey, onSelect, onRemove, onClear, hideActions }) {
  if (!items.length) {
    return (
      <p className="text-sm text-muted-foreground">
        선택된 COMP 챔버가 없습니다.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      {hideActions ? null : (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">챔버 {items.length}개</span>
          <Button variant="ghost" size="sm" onClick={onClear}>목록 비우기</Button>
        </div>
      )}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
        {items.map((it) => {
          const selected = it.key === selectedKey
          const status = it.status // "loading" | "ok" | "notfound" | "error"
          return (
            <button
              key={it.key}
              type="button"
              onClick={() => onSelect(it.key)}
              className={`relative flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5 text-left ${toneClasses(it.grade, selected)}`}
            >
              <span className="min-w-0 flex-1 truncate font-mono text-sm font-medium text-foreground">
                {it.label}
              </span>
              {status === "loading" ? (
                <span className="text-xs text-muted-foreground">조회 중…</span>
              ) : status === "ok" ? (
                <span className="font-mono text-xl font-bold tabular-nums">
                  {Number(it.score ?? 0).toFixed(0)}
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">
                  {status === "notfound" ? "데이터 없음" : "오류"}
                </span>
              )}
              {hideActions ? null : (
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); onRemove(it.key) }}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onRemove(it.key) } }}
                  className="ml-1 rounded border border-border px-1 text-xs text-muted-foreground hover:text-destructive"
                  aria-label="제거"
                >
                  ×
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
