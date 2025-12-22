// src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { AuthAutoLoginGate } from "@/lib/auth"
import { ProtectedAppLayout } from "./layouts/ProtectedAppLayout"

import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { RouteErrorPage, errorRoutes } from "@/features/errors"
import { homeRoutes } from "@/features/home"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { modelsRoutes } from "@/features/models"
import { TimelineLayout, timelineRoutes } from "@/features/timeline"
import { vocRoutes } from "@/features/voc"
import { AssistantLayout, assistantRoutes } from "@/features/assistant"
import { emailsRoutes } from "@/features/emails"
import { accountRoutes } from "@/features/account"

const protectedFeatureRoutes = [
  ...modelsRoutes,
  ...lineDashboardRoutes,
  ...appstoreRoutes,
  ...emailsRoutes,
  ...vocRoutes,
  ...accountRoutes,
]

const protectedAppRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <ProtectedAppLayout />,
      children: protectedFeatureRoutes,
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

const assistantProtectedRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <AssistantLayout />,
      children: assistantRoutes,
    },
  ],
}

export const router = createBrowserRouter([
  {
    path: "/",
    errorElement: <RouteErrorPage />,
    children: [
      ...homeRoutes,
      ...authRoutes,
      protectedAppRoutes,
      timelineProtectedRoutes,
      assistantProtectedRoutes,
      ...errorRoutes,
    ],
  },
])
