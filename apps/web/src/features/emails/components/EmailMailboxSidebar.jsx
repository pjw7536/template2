import { Mail } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export function EmailMailboxSidebar({
  mailboxes = [],
  activeMailbox = "",
  currentUserSdwtProd = "",
  onSelectMailbox,
  isLoading = false,
  errorMessage = "",
}) {
  return (
    <aside
      className="grid h-full w-64 shrink-0 grid-rows-[auto_1fr] rounded-xl border bg-card/60 shadow-sm"
      aria-label="메일함 목록"
    >
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-semibold leading-tight">메일함</p>
          </div>
          <p className="truncate text-xs text-muted-foreground">user_sdwt_prod</p>
        </div>
        {activeMailbox ? (
          <span className="truncate text-xs font-semibold text-foreground">{activeMailbox}</span>
        ) : null}
      </div>

      <div className="min-h-0 overflow-y-auto p-2">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            메일함을 불러오는 중입니다...
          </div>
        ) : errorMessage ? (
          <div className="flex h-full items-center justify-center p-4 text-center text-sm text-destructive">
            {errorMessage}
          </div>
        ) : mailboxes.length === 0 ? (
          <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
            접근 가능한 메일함이 없습니다.
          </div>
        ) : (
          <div className="space-y-1">
            {mailboxes.map((mailbox) => {
              const isActive = mailbox === activeMailbox
              const isSelf = mailbox === currentUserSdwtProd

              return (
                <button
                  key={mailbox}
                  type="button"
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition",
                    isActive
                      ? "bg-primary/10 font-semibold text-primary"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                  )}
                  onClick={() => onSelectMailbox?.(mailbox)}
                  aria-current={isActive ? "true" : undefined}
                >
                  <span className="truncate">{mailbox}</span>
                  {isSelf ? (
                    <Badge variant="secondary" className="shrink-0 text-[10px]">
                      내 소속
                    </Badge>
                  ) : null}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </aside>
  )
}

