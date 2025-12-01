// src/features/line-dashboard/routes.jsx
// 라인 대시보드에서 제공하는 페이지 라우트 정의를 모아둡니다.
import {
  LineDashboardHistoryPage,
  LineDashboardLandingPage,
  LineDashboardOverviewPage,
  LineDashboardSettingsPage,
  LineDashboardStatusPage,
} from "./pages"

export const lineDashboardRoutes = [
  {
    path: ":lineId/ESOP_Dashboard",
    element: <LineDashboardLandingPage />,
  },
  {
    path: ":lineId/ESOP_Dashboard/status",
    element: <LineDashboardStatusPage />,
  },
  {
    path: ":lineId/ESOP_Dashboard/history",
    element: <LineDashboardHistoryPage />,
  },
  {
    path: ":lineId/ESOP_Dashboard/settings",
    element: <LineDashboardSettingsPage />,
  },
  {
    path: ":lineId/ESOP_Dashboard/overview",
    element: <LineDashboardOverviewPage />,
  },
]
