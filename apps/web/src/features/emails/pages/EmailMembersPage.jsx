import { useSearchParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AccessListCard, MailboxAccessCard, useAccountOverview } from "@/features/account"

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
  const {
    data: accountOverview,
    isLoading: accountLoading,
    isError: isAccountError,
    error: accountError,
  } = useAccountOverview()

  const safeMembers = Array.isArray(members) ? members : []
  const affiliation = accountOverview?.affiliation
  const mailboxAccess = accountOverview?.mailboxAccess || []

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-foreground">Members</h1>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {hasMailbox ? `메일함: ${mailboxParam}` : "왼쪽에서 메일함(SDWT)을 선택하세요."}
          </p>
          <Badge variant="secondary">{safeMembers.length}명</Badge>
        </div>
      </div>

      <div className="grid gap-4">
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
          <div className="overflow-hidden rounded-lg border bg-card">
            <EmailMailboxMembersDatatable key={mailboxParam} data={safeMembers} />
          </div>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {isAccountError ? (
          <div className="rounded-lg border bg-card p-6 md:col-span-2">
            <p className="text-sm text-destructive">
              {accountError?.message || "메일함 접근 정보를 불러오지 못했습니다."}
            </p>
          </div>
        ) : accountLoading ? (
          <>
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-72 w-full" />
          </>
        ) : (
          <>
            <AccessListCard data={affiliation} />
            <MailboxAccessCard mailboxes={mailboxAccess} />
          </>
        )}
      </div>
    </div>
  )
}
