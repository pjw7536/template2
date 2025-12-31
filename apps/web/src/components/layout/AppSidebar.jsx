import { NavUser } from "@/components/common"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"

export function AppSidebar({ header, nav, secondary, ...props }) {
  return (
    <Sidebar collapsible="icon" aria-label="App navigation" {...props}>
      <SidebarHeader>{header ?? null}</SidebarHeader>
      <SidebarContent>
        {nav ?? null}
        {secondary ?? null}
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
