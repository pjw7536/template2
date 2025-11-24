// src/features/line-dashboard/pages/LineDashboardHistoryPage.jsx
// 과거 지표를 LineHistoryDashboard 컴포넌트로 감싸는 페이지입니다.
import { useMemo } from "react"
import { useParams, useSearchParams } from "react-router-dom"

import { LineHistoryDashboard } from "@/features/line-dashboard/components"

export function LineDashboardHistoryPage() {
  const { lineId = "" } = useParams()
  const [searchParams] = useSearchParams()

  const initialRangeDays = useMemo(() => {
    const rangeParam = searchParams.get("rangeDays") ?? searchParams.get("range")
    const parsed = Number.parseInt(rangeParam ?? "", 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined
  }, [searchParams])

  return (
    <div className="h-[calc(100vh-5rem)] px-2">
      <LineHistoryDashboard lineId={lineId} initialRangeDays={initialRangeDays} />
    </div>
  )
}
