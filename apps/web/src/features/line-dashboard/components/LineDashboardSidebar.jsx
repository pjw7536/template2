// src/features/line-dashboard/components/LineDashboardSidebar.jsx
import { NavProjects } from "./nav-projects"
import { TeamSwitcher } from "./team-switcher"
import { NavMain } from "./nav-main"
import { NavUser } from "@/components/common"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"

export function LineDashboardSidebar({ lineOptions, navigation, ...props }) {
  const navMain = Array.isArray(navigation?.navMain) ? navigation.navMain : []
  const projects = Array.isArray(navigation?.projects) ? navigation.projects : []
  const teamOptions = Array.isArray(lineOptions)
    ? lineOptions
      .map((lineId) => (typeof lineId === "string" ? lineId.trim() : ""))
      .filter(Boolean)
      .map((lineId) => ({ id: lineId, label: lineId, lineId }))
    : []

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher options={teamOptions} />
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
  )
}
