// src/routes/pages/LineDashboardStatusPage.jsx
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
