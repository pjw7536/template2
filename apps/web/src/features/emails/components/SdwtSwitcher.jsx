import { ChevronsUpDown, Plus } from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

function normalizeMailbox(value) {
  return typeof value === "string" ? value.trim() : ""
}

function getInitials(label) {
  if (!label) return "?"
  const parts = label.split(/[\s-_]+/).filter(Boolean)
  if (parts.length === 0) return label.slice(0, 2).toUpperCase()
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

export function SdwtSwitcher({
  mailboxes = [],
  activeMailbox = "",
  onSelectMailbox,
  isLoading = false,
  errorMessage = "",
}) {
  const { isMobile } = useSidebar()
  const safeMailboxes = Array.isArray(mailboxes) ? mailboxes : []
  const options = safeMailboxes.map(normalizeMailbox).filter(Boolean)
  const trimmedActiveMailbox = normalizeMailbox(activeMailbox)

  const hasOptions = options.length > 0
  const UNKNOWN_LABEL = "Unknown"
  const fallbackMailbox = hasOptions ? options[0] : UNKNOWN_LABEL
  const selectedMailbox = trimmedActiveMailbox || fallbackMailbox

  const handleSelect = (mailbox) => {
    const nextMailbox = normalizeMailbox(mailbox)
    if (!nextMailbox || nextMailbox === trimmedActiveMailbox) return
    onSelectMailbox?.(nextMailbox)
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              aria-label="메일함(SDWT) 선택"
            >
              <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg font-semibold">
                {getInitials(selectedMailbox)}
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{selectedMailbox}</span>
                <span className="truncate text-xs text-muted-foreground">SDWT mailbox</span>
              </div>
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>

          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuLabel className="text-muted-foreground text-xs">Mailboxes</DropdownMenuLabel>

            {isLoading ? (
              <DropdownMenuItem className="gap-2 p-2 opacity-70" disabled>
                <div className="flex size-6 items-center justify-center rounded-md border text-xs font-semibold">
                  …
                </div>
                <div className="flex flex-col">
                  <span>Loading</span>
                  <span className="text-muted-foreground text-xs">메일함을 불러오는 중입니다.</span>
                </div>
              </DropdownMenuItem>
            ) : errorMessage ? (
              <DropdownMenuItem className="gap-2 p-2 opacity-70" disabled>
                <div className="flex size-6 items-center justify-center rounded-md border text-xs font-semibold">
                  !
                </div>
                <div className="flex flex-col">
                  <span>Failed</span>
                  <span className="text-muted-foreground text-xs">{errorMessage}</span>
                </div>
              </DropdownMenuItem>
            ) : hasOptions ? (
              options.map((mailbox) => {
                const isActive = mailbox === trimmedActiveMailbox
                return (
                  <DropdownMenuItem
                    key={mailbox}
                    className={cn(
                      "gap-2 p-2",
                      isActive && "bg-sidebar-accent/20 focus:bg-sidebar-accent/20",
                    )}
                    onSelect={() => handleSelect(mailbox)}
                  >
                    <div className="flex size-6 items-center justify-center rounded-md border text-xs font-semibold">
                      {getInitials(mailbox)}
                    </div>
                    <div className="flex flex-col">
                      <span>{mailbox}</span>
                      <span className="text-muted-foreground text-xs">user_sdwt_prod</span>
                    </div>
                  </DropdownMenuItem>
                )
              })
            ) : (
              <DropdownMenuItem className="gap-2 p-2 opacity-70" disabled>
                <div className="flex size-6 items-center justify-center rounded-md border text-xs font-semibold">
                  {getInitials(UNKNOWN_LABEL)}
                </div>
                <div className="flex flex-col">
                  <span>{UNKNOWN_LABEL}</span>
                  <span className="text-muted-foreground text-xs">접근 가능한 메일함이 없습니다.</span>
                </div>
              </DropdownMenuItem>
            )}

            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 p-2" disabled>
              <div className="flex size-6 items-center justify-center rounded-md border bg-transparent">
                <Plus className="size-4" />
              </div>
              <div className="text-muted-foreground font-medium">Manage mailboxes</div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

