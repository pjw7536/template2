// src/routes/layouts/ProtectedAppLayout.jsx
import { useEffect } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppShell } from "@/components/layout"
import { NAVIGATION_CONFIG } from "@/lib/config/navigation-config"
import { useLineOptionsQuery } from "@/features/line-dashboard"

export function ProtectedAppLayout() {
  const location = useLocation()
  const { data: lineOptions = [], isError, error } = useLineOptionsQuery()
  const isVocRoute = typeof location?.pathname === "string" && location.pathname.includes("/qna")

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  return (
    <RequireAuth>
      <AppShell
        lineOptions={lineOptions}
        navigation={NAVIGATION_CONFIG}
        contentMaxWidthClass={isVocRoute ? "max-w-screen-2xl" : undefined}
        mainOverflowClass={isVocRoute ? "overflow-hidden" : undefined}
      >
        <Outlet />
      </AppShell>
    </RequireAuth>
  )
}
