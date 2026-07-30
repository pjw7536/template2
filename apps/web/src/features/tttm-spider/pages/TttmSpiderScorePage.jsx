// 파일 경로: src/features/tttm-spider/pages/TttmSpiderScorePage.jsx
// 선택된 행(rows) → (ref,comp) entries → TTTM Score 대시보드.
import { useNavigate, useOutletContext } from "react-router-dom"

import { Button } from "@/components/ui/button"

import { TttmSpiderDashboard } from "../components/TttmSpiderDashboard"
import { buildEntriesFromRows } from "../utils/selection"

export function TttmSpiderScorePage() {
  const { selection, patch } = useOutletContext()
  const navigate = useNavigate()
  const { entries } = buildEntriesFromRows(selection.rows, selection.compLotwf, selection.refLotwf)

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-foreground">TTTM Spider · Score</h1>
          <p className="text-sm text-muted-foreground">{entries.length}개 비교 (REFn vs COMPn)</p>
        </div>
        <Button variant="outline" onClick={() => navigate("..", { relative: "path" })}>← Target 선택</Button>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          선택된 비교가 없습니다. Target 선택으로 돌아가 lotwf를 선택하세요.
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <TttmSpiderDashboard
            entries={entries}
            dataType={selection.dataType}
            onDataTypeChange={(v) => patch({ dataType: v })}
            initialSelectedKey={selection.focusKey}
          />
        </div>
      )}
    </div>
  )
}
