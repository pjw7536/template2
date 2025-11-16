// src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { ProtectedAppLayout } from "./layouts/ProtectedAppLayout"
import { HomePage } from "./pages/HomePage"
import { LineDashboardLandingPage } from "./pages/LineDashboardLandingPage"
import { LineDashboardOverviewPage } from "./pages/LineDashboardOverviewPage"
import { LineDashboardHistoryPage } from "./pages/LineDashboardHistoryPage"
import { LineDashboardSettingsPage } from "./pages/LineDashboardSettingsPage"
import { LineDashboardStatusPage } from "./pages/LineDashboardStatusPage"
import { LoginPage } from "./pages/LoginPage"
import { ModelsPage } from "./pages/ModelsPage"
import { NotFoundPage } from "./pages/NotFoundPage"

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />, 
  },
  {
    path: "/",
    element: <ProtectedAppLayout />, 
    children: [
      { index: true, element: <HomePage /> },
      { path: "models", element: <ModelsPage /> },
      { path: ":lineId/ESOP_Dashboard", element: <LineDashboardLandingPage /> },
      { path: ":lineId/ESOP_Dashboard/status", element: <LineDashboardStatusPage /> },
      { path: ":lineId/ESOP_Dashboard/history", element: <LineDashboardHistoryPage /> },
      { path: ":lineId/ESOP_Dashboard/settings", element: <LineDashboardSettingsPage /> },
      { path: ":lineId/ESOP_Dashboard/overview", element: <LineDashboardOverviewPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
])
