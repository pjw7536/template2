// src/routes/layouts/ProtectedAppLayout.jsx
import { useEffect } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppLayout } from "@/components/layout"
import { NAVIGATION_CONFIG } from "@/lib/config/navigation-config"
import {
  LineDashboardShell,
  LineDashboardSidebar,
  useLineOptionsQuery,
} from "@/features/line-dashboard"
import { ChatWidget } from "@/features/assistant"

export function ProtectedAppLayout() {
  const location = useLocation()
  const pathname = typeof location?.pathname === "string" ? location.pathname : ""
  const normalizedPath = pathname.toLowerCase()
  const isLineDashboardRoute = normalizedPath.startsWith("/esop_dashboard")
  const isVocRoute = typeof pathname === "string" && (/\/voc(\/|$)|\/qna(\/|$)/).test(pathname)
  const contentMaxWidthClass = isVocRoute ? "max-w-screen-2xl" : undefined
  const mainOverflowClass = isVocRoute ? "overflow-hidden" : undefined

  const {
    data: lineOptions = [],
    isError,
    error,
  } = useLineOptionsQuery({ enabled: isLineDashboardRoute })

  const navigation = isLineDashboardRoute ? NAVIGATION_CONFIG : null
  const sidebarLineOptions = isLineDashboardRoute ? lineOptions : []
  const sidebar = isLineDashboardRoute ? (
    <LineDashboardSidebar lineOptions={sidebarLineOptions} navigation={navigation} />
  ) : null

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  return (
    <RequireAuth>
      {isLineDashboardRoute ? (
        <LineDashboardShell
          sidebar={sidebar}
          contentMaxWidthClass={contentMaxWidthClass}
          mainOverflowClass={mainOverflowClass}
        >
          <Outlet />
        </LineDashboardShell>
      ) : (
        <AppLayout
          contentMaxWidthClass={contentMaxWidthClass}
          mainOverflowClass={mainOverflowClass}
        >
          <Outlet />
        </AppLayout>
      )}
      <ChatWidget />
    </RequireAuth>
  )
}
