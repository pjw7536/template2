import { useSearchParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"

import { EmailMailboxMembersDatatable } from "../components/EmailMailboxMembersDatatable"
import { useEmailMailboxMembers } from "../hooks/useEmailMailboxMembers"
import { getMailboxFromSearchParams } from "../utils/mailbox"

export function EmailMembersPage() {
  const [searchParams] = useSearchParams()
  const mailboxParam = getMailboxFromSearchParams(searchParams)
  const hasMailbox = Boolean(mailboxParam)

  const {
    members,
    isLoading,
    isError,
    error,
  } = useEmailMailboxMembers(mailboxParam, { enabled: hasMailbox })

  const safeMembers = Array.isArray(members) ? members : []

  return (
    <div className="h-full min-h-0">
      <div className="grid h-full min-h-0 grid-rows-[80px_1fr] gap-2">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground">Members</h1>
          <div className="flex justify-between">
            <p className="text-sm text-muted-foreground">
              {hasMailbox ? `메일함: ${mailboxParam}` : "왼쪽에서 메일함(SDWT)을 선택하세요."}
            </p>
            <Badge variant="secondary">{safeMembers.length}명</Badge>
          </div>
        </div>

        {!hasMailbox ? (
          <div className="rounded-lg border bg-card p-6">
            <p className="text-sm text-muted-foreground">메일함을 선택하면 멤버 목록을 보여줍니다.</p>
          </div>
        ) : isLoading ? (
          <div className="rounded-lg border bg-card p-6">
            <div className="flex items-center justify-between gap-2">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-6 w-16" />
            </div>
            <div className="mt-4 grid gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </div>
        ) : isError ? (
          <div className="rounded-lg border bg-card p-6">
            <p className="text-sm text-destructive">
              {error?.message || "멤버 목록을 불러오지 못했습니다."}
            </p>
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-3 rounded-lg border bg-card">
            <div className="min-h-0 overflow-hidden">
              <EmailMailboxMembersDatatable key={mailboxParam} data={safeMembers} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
