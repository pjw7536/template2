import { useEffect } from "react"

import { AppShellLayout } from "@/components/layout"
import { TeamSwitcher } from "@/components/common"
import { buildNavigationConfig } from "@/lib/config/navigation-config"
import {
  ActiveLineProvider,
  DepartmentProvider,
  buildLineSwitcherOptions,
  useLineSwitcher,
} from "@/lib/affiliation"

import { LineDashboardHeader } from "./LineDashboardHeader"
import { NavProjects } from "./nav-projects"
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

  const navigation = buildNavigationConfig()
  const header = <LineDashboardHeader showSidebarTrigger />

  return (
    <DepartmentProvider>
      <ActiveLineProvider lineOptions={lineOptions}>
        <LineDashboardShell
          navigation={navigation}
          header={header}
          lineOptions={lineOptions}
          contentMaxWidthClass={contentMaxWidthClass}
          scrollAreaClassName={scrollAreaClassName}
        >
          {children}
        </LineDashboardShell>
      </ActiveLineProvider>
    </DepartmentProvider>
  )
}

function LineDashboardShell({
  children,
  navigation,
  header,
  lineOptions,
  contentMaxWidthClass,
  scrollAreaClassName,
}) {
  const { activeLineId, onSelect } = useLineSwitcher()
  const lineSwitcherOptions = buildLineSwitcherOptions(lineOptions)

  return (
    <AppShellLayout
      navItems={navigation.navMain}
      header={header}
      sidebarHeader={(
        <TeamSwitcher
          options={lineSwitcherOptions}
          activeId={activeLineId}
          onSelect={onSelect}
        />
      )}
      sidebarSecondary={<NavProjects projects={navigation.projects} />}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
    >
      {children}
    </AppShellLayout>
  )
}
