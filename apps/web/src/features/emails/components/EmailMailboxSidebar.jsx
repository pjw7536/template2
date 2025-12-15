import { Mail, Users } from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarRail,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import { NavUser } from "@/features/line-dashboard"

import { NavMain } from "./nav-main"
import { SdwtSwitcher } from "./SdwtSwitcher"
import { buildMailboxUrl, buildMembersUrl, normalizeMailbox } from "../utils/mailbox"

export function EmailMailboxSidebar({
  mailboxes = [],
  activeMailbox = "",
  onSelectMailbox,
  isLoading = false,
  errorMessage = "",
  ...props
}) {
  const safeMailboxes = Array.isArray(mailboxes) ? mailboxes : []
  const trimmedActiveMailbox = normalizeMailbox(activeMailbox)

  const normalizedMailboxes = safeMailboxes.map(normalizeMailbox).filter(Boolean)
  const uniqueMailboxes = Array.from(new Set(normalizedMailboxes))

  const navMain = [
    {
      title: "Inbox",
      url: buildMailboxUrl(trimmedActiveMailbox),
      icon: Mail,
      isActive: true,
    },
    {
      title: "Members",
      url: buildMembersUrl(trimmedActiveMailbox),
      icon: Users,
    },
  ]

  return (
    <Sidebar collapsible="icon" aria-label="메일함 목록" {...props}>
      <SidebarHeader>
        <SdwtSwitcher
          mailboxes={uniqueMailboxes}
          activeMailbox={trimmedActiveMailbox}
          onSelectMailbox={onSelectMailbox}
          isLoading={isLoading}
          errorMessage={errorMessage}
        />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
