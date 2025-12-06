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
    caseSensitive: false,
    element: <LineDashboardEntryPage />,
  },
  {
    path: "ESOP_Dashboard/:lineId",
    caseSensitive: false,
    element: <LineDashboardLandingPage />,
  },
  {
    path: "ESOP_Dashboard/status/:lineId",
    caseSensitive: false,
    element: <LineDashboardStatusPage />,
  },
  {
    path: "ESOP_Dashboard/history/:lineId",
    caseSensitive: false,
    element: <LineDashboardHistoryPage />,
  },
  {
    path: "ESOP_Dashboard/settings/:lineId",
    caseSensitive: false,
    element: <LineDashboardSettingsPage />,
  },
  {
    path: "ESOP_Dashboard/overview",
    caseSensitive: false,
    element: <LineDashboardOverviewPage />,
  },
]
