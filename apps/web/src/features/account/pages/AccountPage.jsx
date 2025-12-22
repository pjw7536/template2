import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/lib/auth"

import { AccessListCard } from "../components/AccessListCard"
import { AccountProfileCard } from "../components/AccountProfileCard"
import { AffiliationHistoryCard } from "../components/AffiliationHistoryCard"
import { AffiliationStatusCard } from "../components/AffiliationStatusCard"
import { MailboxAccessCard } from "../components/MailboxAccessCard"
import { ManageableGroupsCard } from "../components/ManageableGroupsCard"
import { useAccountOverview } from "../hooks/useAccountData"

export default function AccountPage() {
  const { user } = useAuth()
  const { data, isLoading, error } = useAccountOverview()

  const pageTitle = user?.username ? `내 계정 · ${user.username}` : "내 계정"
  const profile = data?.user
  const affiliation = data?.affiliation
  const reconfirm = data?.affiliationReconfirm
  const history = data?.affiliationHistory || []
  const manageableGroups = data?.manageableGroups?.groups || []
  const mailboxAccess = data?.mailboxAccess || []

  return (
    <div className="h-full min-h-0">
      <div className="grid min-h-0 gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-foreground">{pageTitle}</h1>
          <p className="text-sm text-muted-foreground">
            계정 소속, 접근 권한, 승인 히스토리, 메일함 접근 현황을 한 번에 확인합니다.
          </p>
        </div>

        {error ? (
          <div className="rounded-lg border bg-card p-6">
            <p className="text-destructive text-sm">
              {error?.message || "계정 정보를 불러오지 못했습니다."}
            </p>
          </div>
        ) : isLoading ? (
          <div className="grid min-h-0 grid-cols-1 gap-4 md:grid-cols-2">
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-72 w-full md:col-span-2" />
            <Skeleton className="h-96 w-full md:col-span-2" />
            <Skeleton className="h-96 w-full md:col-span-2" />
          </div>
        ) : (
          <div className="grid min-h-0 grid-cols-1 gap-4 md:grid-cols-2">
            <AccountProfileCard profile={profile} />
            <AffiliationStatusCard affiliation={affiliation} reconfirm={reconfirm} />
            <AccessListCard data={affiliation} />
            <ManageableGroupsCard groups={manageableGroups} />
            <div className="md:col-span-2">
              <MailboxAccessCard mailboxes={mailboxAccess} />
            </div>
            <div className="md:col-span-2">
              <AffiliationHistoryCard history={history} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
