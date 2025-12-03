// src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { AuthAutoLoginGate } from "@/lib/auth"
import { ProtectedAppLayout } from "./layouts/ProtectedAppLayout"

import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { errorRoutes } from "@/features/errors"
import { homeRoutes } from "@/features/home"
import { landingRoutes } from "@/features/landing"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { modelsRoutes } from "@/features/models"
import { vocRoutes } from "@/features/voc"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AuthAutoLoginGate />,
    children: [
      ...landingRoutes,
      ...authRoutes,
      ...appstoreRoutes,
      {
        path: "/",
        element: <ProtectedAppLayout />,
        children: [
          ...homeRoutes,
          ...modelsRoutes,
          ...lineDashboardRoutes,
          ...vocRoutes,
          ...errorRoutes,
        ],
      },
      ...errorRoutes,
    ],
  },
])
