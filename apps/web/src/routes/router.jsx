// src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { AuthAutoLoginGate } from "@/lib/auth"
import { ProtectedAppLayout } from "./layouts/ProtectedAppLayout"

import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { RouteErrorPage, errorRoutes } from "@/features/errors"
import { landingRoutes } from "@/features/landing"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { modelsRoutes } from "@/features/models"
import { TimelineLayout, timelineRoutes } from "@/features/timeline"
import { vocRoutes } from "@/features/voc"

const protectedAppRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <ProtectedAppLayout />,
      children: [
        ...modelsRoutes,
        ...lineDashboardRoutes,
        ...appstoreRoutes,
        ...vocRoutes,
      ],
    },
  ],
}

const timelineProtectedRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <TimelineLayout />,
      children: timelineRoutes,
    },
  ],
}

export const router = createBrowserRouter([
  {
    path: "/",
    errorElement: <RouteErrorPage />,
    children: [
      ...landingRoutes,
      ...authRoutes,
      protectedAppRoutes,
      timelineProtectedRoutes,
      ...errorRoutes,
    ],
  },
])
