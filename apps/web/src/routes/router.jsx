// src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { ProtectedAppLayout } from "./layouts/ProtectedAppLayout"

import { LoginPage } from "@/features/auth"
import { NotFoundPage } from "@/features/errors"
import { HomePage } from "@/features/home"
import {
  LineDashboardHistoryPage,
  LineDashboardLandingPage,
  LineDashboardOverviewPage,
  LineDashboardSettingsPage,
  LineDashboardStatusPage,
} from "@/features/line-dashboard"
import { ModelsPage } from "@/features/models"

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
