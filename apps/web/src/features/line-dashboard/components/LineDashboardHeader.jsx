// src/features/line-dashboard/components/LineDashboardHeader.jsx
import { ThemeControls } from "@/components/common"
import { SidebarHeaderBar } from "@/components/layout"

import { LineDashboardBreadcrumb } from "./LineDashboardBreadcrumb"

export function LineDashboardHeader({ showSidebarTrigger = true }) {
  return (
    <SidebarHeaderBar showSidebarTrigger={showSidebarTrigger} right={<ThemeControls />}>
      <LineDashboardBreadcrumb />
    </SidebarHeaderBar>
  )
}
