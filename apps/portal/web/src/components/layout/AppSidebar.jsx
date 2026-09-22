import { NavUser } from "@/components/common"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

export function AppSidebar({ header, nav, secondary, className, ...props }) {
  return (
    <Sidebar
      collapsible="icon"
      aria-label="App navigation"
      className={cn("md:top-14 md:h-[calc(100svh-4rem)]", className)}
      {...props}
    >
      {header ? <SidebarHeader>{header}</SidebarHeader> : null}
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
