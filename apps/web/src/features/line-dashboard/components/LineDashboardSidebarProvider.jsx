// src/features/line-dashboard/components/LineDashboardSidebarProvider.jsx
import { useLocation } from "react-router-dom"

import { SidebarProvider } from "@/components/ui/sidebar"

export function LineDashboardSidebarProvider({ children }) {
  const { pathname } = useLocation()
  const defaultOpen = pathname !== "/"

  return (
    <SidebarProvider key={pathname} defaultOpen={defaultOpen}>
      {children}
    </SidebarProvider>
  )
}
