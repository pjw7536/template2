// src/routes/layouts/ProtectedAppLayout.jsx
import { useEffect, useState } from "react"
import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/features/auth"
import { AppShell } from "@/features/navigation"
import { getDistinctLineIds } from "@/features/line-dashboard/api/get-line-ids"

export function ProtectedAppLayout() {
  const [lineOptions, setLineOptions] = useState([])

  useEffect(() => {
    let active = true

    async function loadLineOptions() {
      try {
        const result = await getDistinctLineIds()
        if (!active) return
        if (Array.isArray(result)) {
          setLineOptions(result)
        }
      } catch (error) {
        console.warn("Failed to load line options", error)
        if (!active) return
        setLineOptions([])
      }
    }

    loadLineOptions()
    return () => {
      active = false
    }
  }, [])

  return (
    <RequireAuth>
      <AppShell lineOptions={lineOptions}>
        <Outlet />
      </AppShell>
    </RequireAuth>
  )
}
