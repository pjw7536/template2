// src/routes/layouts/ProtectedAppLayout.jsx
import { useEffect } from "react"
import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppShell } from "@/components/layout"
import { NAVIGATION_CONFIG } from "@/lib/config/navigation-config"
import { useLineOptionsQuery } from "@/features/line-dashboard"

export function ProtectedAppLayout() {
  const { data: lineOptions = [], isError, error } = useLineOptionsQuery()

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  return (
    <RequireAuth>
      <AppShell lineOptions={lineOptions} navigation={NAVIGATION_CONFIG}>
        <Outlet />
      </AppShell>
    </RequireAuth>
  )
}
