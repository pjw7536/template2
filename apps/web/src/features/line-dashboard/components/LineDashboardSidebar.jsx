import { NavProjects } from "./NavProjects"
import { TeamSwitcher, NavUser } from "@/components/common"
import { NavMain } from "@/components/layout"
import { buildLineSwitcherOptions, useLineSwitcher } from "@/lib/affiliation"
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
  const teamOptions = buildLineSwitcherOptions(lineOptions)
  const { activeLineId, onSelect } = useLineSwitcher()

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher options={teamOptions} activeId={activeLineId} onSelect={onSelect} />
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
