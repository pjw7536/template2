// src/features/line-dashboard/pages/LineDashboardStatusPage.jsx
// 라인 별 현재 상태를 요약할 페이지입니다.
import { useParams } from "react-router-dom"

import { LineDashboardPage } from "../components/LineDashboardPage"

export function LineDashboardStatusPage() {
  const { lineId = "" } = useParams()

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <LineDashboardPage lineId={lineId} />
    </div>
  )
}
