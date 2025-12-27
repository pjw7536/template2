import { useEffect, useMemo } from "react"

import { AppLayout, AppSidebar } from "@/components/layout"
import { buildNavigationConfig } from "@/lib/config/navigation-config"

import { LineDashboardHeader } from "./LineDashboardHeader"
import { NavMain } from "./nav-main"
import { NavProjects } from "./nav-projects"
import { TeamSwitcher } from "./team-switcher"
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

  const lineSwitcherOptions = useMemo(() => {
    if (!Array.isArray(lineOptions)) return []
    return lineOptions
      .map((lineId) => (typeof lineId === "string" ? lineId.trim() : ""))
      .filter(Boolean)
      .map((lineId) => ({ id: lineId, label: lineId, lineId }))
  }, [lineOptions])

  const navigation = buildNavigationConfig()
  const nav = <NavMain items={navigation.navMain} />
  const sidebar = (
    <AppSidebar
      header={<TeamSwitcher options={lineSwitcherOptions} />}
      nav={nav}
      secondary={<NavProjects projects={navigation.projects} />}
    />
  )
  const header = <LineDashboardHeader showSidebarTrigger={Boolean(sidebar)} />

  return (
    <ActiveLineProvider lineOptions={lineOptions}>
      <AppLayout
        sidebar={sidebar}
        header={header}
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        {children}
      </AppLayout>
    </ActiveLineProvider>
  )
}
