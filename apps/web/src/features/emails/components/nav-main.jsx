import { ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "components/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"

function LeafItem({ item }) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild tooltip={item.title}>
        <Link to={item.url || "#"}>
          {item.icon && <item.icon />}
          <span>{item.title}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

function GroupItem({ item }) {
  const children = Array.isArray(item.items) ? item.items : []

  return (
    <Collapsible asChild defaultOpen={!!item.isActive} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={item.title}>
            {item.icon && <item.icon />}
            <span>{item.title}</span>
            <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <SidebarMenuSub>
            {children.map((sub) => (
              <SidebarMenuSubItem key={`${sub.title}-${sub.url || "no-url"}`}>
                <SidebarMenuSubButton asChild>
                  <Link to={sub.url || "#"}>
                    <span>{sub.title}</span>
                  </Link>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

export function NavMain({ items, label = "Emails" }) {
  const safeItems = Array.isArray(items) ? items : []

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarMenu>
        {safeItems.map((item) => {
          const hasChildren = Array.isArray(item.items) && item.items.length > 0
          if (hasChildren) {
            return <GroupItem key={`${item.title}-${item.url || "group"}`} item={item} />
          }
          return <LeafItem key={`${item.title}-${item.url || "leaf"}`} item={item} />
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}

