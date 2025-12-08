// src/features/line-dashboard/components/LineDashboardHeader.jsx
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { ThemeColorSelector, ThemeToggle } from "@/components/common"

import { LineDashboardBreadcrumb } from "./LineDashboardBreadcrumb"

export function LineDashboardHeader({ showSidebarTrigger = true }) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between gap-2 px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
      <div className="flex items-center gap-2">
        {showSidebarTrigger ? (
          <>
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          </>
        ) : null}
        <LineDashboardBreadcrumb />
      </div>
      <div className="flex items-center">
        <ThemeToggle />
        <ThemeColorSelector />
      </div>
    </header>
  )
}
