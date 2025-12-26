import { useEffect } from "react"

import { NAVIGATION_CONFIG } from "@/lib/config/navigation-config"

import { LineDashboardShell } from "./LineDashboardShell"
import { LineDashboardSidebar } from "./LineDashboardSidebar"
import { ActiveLineProvider } from "./active-line-context"
import { useLineOptionsQuery } from "../hooks/useLineOptionsQuery"

export function LineDashboardLayout({
  children,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
}) {
  const {
    data: lineOptions = [],
    isError,
    error,
  } = useLineOptionsQuery()

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  const sidebar = (
    <LineDashboardSidebar lineOptions={lineOptions} navigation={NAVIGATION_CONFIG} />
  )

  return (
    <ActiveLineProvider lineOptions={lineOptions}>
      <LineDashboardShell
        sidebar={sidebar}
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        {children}
      </LineDashboardShell>
    </ActiveLineProvider>
  )
}
