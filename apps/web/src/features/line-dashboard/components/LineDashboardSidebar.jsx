// src/features/line-dashboard/components/LineDashboardSidebar.jsx
import { NavProjects } from "./nav-projects"
import { TeamSwitcher } from "./team-switcher"
import { ActiveLineProvider } from "./active-line-context"
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
