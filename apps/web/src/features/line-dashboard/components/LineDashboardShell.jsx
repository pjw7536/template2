// src/features/line-dashboard/components/LineDashboardShell.jsx
import { SidebarInset } from "@/components/ui/sidebar"

import { LineDashboardHeader } from "./LineDashboardHeader"
import { LineDashboardSidebarProvider } from "./LineDashboardSidebarProvider"

export function LineDashboardShell({
  sidebar,
  children,
  contentMaxWidthClass = "max-w-10xl",
  mainOverflowClass = "overflow-auto",
  header,
}) {
  const headerNode = header ?? (
    <LineDashboardHeader showSidebarTrigger={Boolean(sidebar)} />
  )

  return (
    <LineDashboardSidebarProvider>
      {sidebar ?? null}
      <SidebarInset>
        {headerNode}
        <main
          className={[
            "flex-1 min-h-0 min-w-0 px-4 pb-6 pt-2",
            mainOverflowClass,
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <div
            className={[
              "mx-auto flex h-full w-full flex-col gap-4",
              contentMaxWidthClass,
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {children}
          </div>
        </main>
      </SidebarInset>
    </LineDashboardSidebarProvider>
  )
}
