// src/features/line-dashboard/pages/LineDashboardLandingPage.jsx
// 라인별 대시보드로 진입했을 때 기본 소개를 보여주는 페이지입니다.
import { useParams } from "react-router-dom"

export function LineDashboardLandingPage() {
  const { lineId = "" } = useParams()
  return (
    <section className="grid gap-4">
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight">ESOP Dashboard · {lineId}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Select a view from the sidebar to explore the latest E-SOP metrics for this production line.
        </p>
      </div>
    </section>
  )
}
