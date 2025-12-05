// src/features/line-dashboard/pages/LineDashboardSettingsPage.jsx
// 라인 대시보드 설정 UI가 들어갈 자리입니다.
import { useParams } from "react-router-dom"

import { LineSettingsPage } from "../components/LineSettingsPage"

export function LineDashboardSettingsPage() {
  const { lineId = "" } = useParams()

  return (
    <div className="h-[calc(100vh-5rem)] px-2">
      <LineSettingsPage lineId={lineId} />
    </div>
  )
}
