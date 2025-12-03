// src/features/line-dashboard/routes.jsx
// 라인 대시보드에서 제공하는 페이지 라우트 정의를 모아둡니다.
import {
  LineDashboardEntryPage,
  LineDashboardHistoryPage,
  LineDashboardLandingPage,
  LineDashboardOverviewPage,
  LineDashboardSettingsPage,
  LineDashboardStatusPage,
} from "./pages"

export const lineDashboardRoutes = [
  {
    path: "ESOP_Dashboard",
    element: <LineDashboardEntryPage />,
  },
  {
    path: "ESOP_Dashboard/:lineId",
    element: <LineDashboardLandingPage />,
  },
  {
    path: "ESOP_Dashboard/:lineId/status",
    element: <LineDashboardStatusPage />,
  },
  {
    path: "ESOP_Dashboard/:lineId/history",
    element: <LineDashboardHistoryPage />,
  },
  {
    path: "ESOP_Dashboard/:lineId/settings",
    element: <LineDashboardSettingsPage />,
  },
  {
    path: "ESOP_Dashboard/:lineId/overview",
    element: <LineDashboardOverviewPage />,
  },
]
