// src/features/line-dashboard/pages/LineDashboardStatusPage.jsx
// 라인 별 현재 상태를 요약할 페이지입니다.
import { useParams } from "react-router-dom"

import { LineDashboardPage } from "@/features/line-dashboard/components"

export function LineDashboardStatusPage() {
  const { lineId = "" } = useParams()

  return (
    <div className="h-[calc(100vh-5rem)] px-2">
      <LineDashboardPage lineId={lineId} />
    </div>
  )
}
