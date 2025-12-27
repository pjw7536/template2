// src/features/line-dashboard/components/LineDashboardShell.jsx
import { AppLayout } from "@/components/layout"

import { LineDashboardHeader } from "./LineDashboardHeader"

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
    <AppLayout
      sidebar={sidebar}
      header={headerNode}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
      paddingClassName={paddingClassName}
      innerClassName={innerClassName}
    >
      {children}
    </AppLayout>
  )
}
