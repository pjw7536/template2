// src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { ProtectedAppLayout } from "./layouts/ProtectedAppLayout"

import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { errorRoutes } from "@/features/errors"
import { homeRoutes } from "@/features/home"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { modelsRoutes } from "@/features/models"
import { vocRoutes } from "@/features/voc"

export const router = createBrowserRouter([
  ...authRoutes,
  {
    path: "/",
    element: <ProtectedAppLayout />,
    children: [
      ...homeRoutes,
      ...appstoreRoutes,
      ...modelsRoutes,
      ...lineDashboardRoutes,
      ...vocRoutes,
      ...errorRoutes,
    ],
  },
  ...errorRoutes,
])
