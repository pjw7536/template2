// src/features/navigation/components/app-sidebar.jsx
"use client"

import { NAVIGATION_CONFIG } from "../config/navigation-config"
import { NavProjects } from "./nav-projects"
import { NavUser } from "./nav-user"
import { TeamSwitcher } from "./team-switcher"
import { ActiveLineProvider } from "./active-line-context"
import { NavMain } from "./nav-main"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"

export function AppSidebar({ lineOptions, ...props }) {
  const { navMain, projects } = NAVIGATION_CONFIG
  // 외부 데이터 안전 처리: null/undefined가 넘어와도 빈 배열로 대체해 안정적으로 렌더링
  const teams = Array.isArray(lineOptions) ? lineOptions : []

  return (
    <ActiveLineProvider lineOptions={teams}>
      <Sidebar collapsible="icon" {...props}>
        <SidebarHeader>
          <TeamSwitcher lines={teams} />
        </SidebarHeader>
        <SidebarContent>
          <NavMain items={navMain} />
          <NavProjects projects={projects} />
        </SidebarContent>
        <SidebarFooter>
          <NavUser />
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
    </ActiveLineProvider>
  )
}
