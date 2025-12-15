import { Folder, Forward, MoreHorizontal, Trash2 } from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "components/ui/dropdown-menu"

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function NavProjects({
  projects,
  label = "Mailboxes",
  onSelectProject,
  isLoading = false,
  errorMessage = "",
  emptyMessage = "접근 가능한 메일함이 없습니다.",
}) {
  const { isMobile } = useSidebar()
  const projectItems = Array.isArray(projects) ? projects : []
  const trimmedErrorMessage = typeof errorMessage === "string" ? errorMessage.trim() : ""

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>{label}</SidebarGroupLabel>

      <SidebarMenu>
        {isLoading ? (
          <SidebarMenuItem>
            <SidebarMenuButton disabled className="text-sidebar-foreground/70">
              <MoreHorizontal className="text-sidebar-foreground/70" />
              <span>메일함을 불러오는 중입니다...</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : trimmedErrorMessage ? (
          <SidebarMenuItem>
            <SidebarMenuButton disabled className="text-destructive">
              <MoreHorizontal />
              <span>{trimmedErrorMessage}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : projectItems.length === 0 ? (
          <SidebarMenuItem>
            <SidebarMenuButton disabled className="text-sidebar-foreground/70">
              <MoreHorizontal className="text-sidebar-foreground/70" />
              <span>{emptyMessage}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : (
          projectItems.map((item) => (
            <SidebarMenuItem key={item.name}>
              <SidebarMenuButton
                isActive={Boolean(item.isActive)}
                onClick={() => onSelectProject?.(item.name)}
                tooltip={item.name}
              >
                {item.icon && <item.icon />}
                <span>{item.name}</span>
              </SidebarMenuButton>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuAction showOnHover>
                    <MoreHorizontal />
                    <span className="sr-only">More</span>
                  </SidebarMenuAction>
                </DropdownMenuTrigger>

                <DropdownMenuContent
                  className="w-48 rounded-lg"
                  side={isMobile ? "bottom" : "right"}
                  align={isMobile ? "end" : "start"}
                >
                  <DropdownMenuItem onSelect={() => onSelectProject?.(item.name)}>
                    <Folder className="text-muted-foreground" />
                    <span>Open Mailbox</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled>
                    <Forward className="text-muted-foreground" />
                    <span>Share Mailbox</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem disabled>
                    <Trash2 className="text-muted-foreground" />
                    <span>Remove Mailbox</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          ))
        )}

        {projectItems.length > 0 && !isLoading && !trimmedErrorMessage ? (
          <SidebarMenuItem>
            <SidebarMenuButton className="text-sidebar-foreground/70">
              <MoreHorizontal className="text-sidebar-foreground/70" />
              <span>More</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : null}
      </SidebarMenu>
    </SidebarGroup>
  )
}
