// src/routes/pages/LineDashboardSettingsPage.jsx
import { useParams } from "react-router-dom"

import { LineSettingsPage } from "@/features/line-dashboard/components"

export function LineDashboardSettingsPage() {
  const { lineId = "" } = useParams()

  return (
    <div className="h-[calc(100vh-5rem)] px-2">
      <LineSettingsPage lineId={lineId} />
    </div>
  )
}
