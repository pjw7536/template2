// src/features/line-dashboard/components/LineDashboardShell.jsx
import { SidebarInset } from "@/components/ui/sidebar"
import { ContentLayout } from "@/components/layout"

import { LineDashboardHeader } from "./LineDashboardHeader"
import { LineDashboardSidebarProvider } from "./LineDashboardSidebarProvider"

export function LineDashboardShell({
  sidebar,
  children,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "px-4 pb-3",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
  header,
}) {
  const headerNode = header ?? (
    <LineDashboardHeader showSidebarTrigger={Boolean(sidebar)} />
  )

  return (
    <LineDashboardSidebarProvider>
      {sidebar ?? null}
      <SidebarInset className="h-screen">
        <header className="h-16 shrink-0 bg-background">
          <div className="h-full">{headerNode}</div>
        </header>
        <main className="flex-1 min-h-0 min-w-0 overflow-hidden">
          <ContentLayout
            contentMaxWidthClass={contentMaxWidthClass}
            scrollAreaClassName={scrollAreaClassName}
            paddingClassName={paddingClassName}
            innerClassName={innerClassName}
          >
            {children}
          </ContentLayout>
        </main>
      </SidebarInset>
    </LineDashboardSidebarProvider>
  )
}
