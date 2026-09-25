import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { hasScopeAccess } from "@/lib/access/scopeAccess"
import { useAuth } from "@/lib/auth"

import { AffiliationCard } from "../components/AffiliationCard"
import { AffiliationHistoryCard } from "../components/AffiliationHistoryCard"
import { ManageableGroupsCard } from "../components/ManageableGroupsCard"
import { useAccountOverview, useAffiliation } from "../hooks/useAccountData"
import { buildAccountSummaryModel } from "../utils/accountOverview"

function SummaryMetric({ label, value, description, badge }) {
  return (
    <div className="min-w-0 rounded-lg border bg-background/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
      </div>
      <p className="mt-2 truncate text-lg font-semibold text-foreground" title={value || "미지정"}>
        {value || "미지정"}
      </p>
      {description ? (
        <p className="mt-1 truncate text-xs text-muted-foreground" title={description}>
          {description}
        </p>
      ) : null}
    </div>
  )
}

function AccountSummaryPanel({ pageTitle, profile, summary }) {
  const latestRequest = summary?.latestRequest

  return (
    <Card className="shrink-0 overflow-hidden border-primary/20 bg-card py-0">
      <CardContent className="grid gap-5 px-5 pb-3 pt-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">{pageTitle}</h2>
              <Badge variant={summary?.needsReconfirm ? "destructive" : "secondary"}>
                {summary?.needsReconfirm ? "소속 재확인 필요" : "소속 정상"}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              계정 식별 정보, 현재 소속, 변경 요청 상태를 한 곳에서 확인합니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {profile?.isSuperuser ? <Badge variant="secondary">슈퍼유저</Badge> : null}
            {profile?.isStaff ? <Badge variant="outline">스태프</Badge> : null}
            <Badge variant={summary?.pendingRequests > 0 ? "destructive" : "secondary"}>
              대기 {summary?.pendingRequests || 0}건
            </Badge>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SummaryMetric label="사용자" value={profile?.username || "미지정"} description={profile?.knoxId || "Knox ID 미지정"} />
          <SummaryMetric label="멤버 권한" value={summary?.roleLabel} description="명시적으로 부여된 권한" />
          <SummaryMetric label="현재 소속" value={summary?.affiliationLabel} description="Department / Line / user_sdwt_prod" />
          <SummaryMetric
            label="최근 요청"
            value={summary?.latestRequestValue}
            description={summary?.latestRequestDescription}
            badge={summary?.requestStatus}
          />
        </div>

        {latestRequest?.status === "REJECTED" && latestRequest.rejectionReason ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            거절 사유: {latestRequest.rejectionReason}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export default function AccountPage() {
  const { user } = useAuth()
  const hasPortalAccess = hasScopeAccess(user, "portal")
  const {
    data: overviewData,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAccountOverview({ enabled: hasPortalAccess })
  const {
    data: affiliationData,
    isLoading: affiliationLoading,
    error: affiliationError,
  } = useAffiliation()

  const pageTitle = user?.username ? `내 계정 · ${user.username}` : "내 계정"
  const profile = overviewData?.user
  const affiliation = overviewData?.affiliation
  const reconfirm = overviewData?.affiliationReconfirm
  const history = overviewData?.affiliationHistory || []
  const manageableGroups = overviewData?.manageableGroups?.groups || []
  const accountSummary =
    overviewData?.accountSummary ||
    buildAccountSummaryModel({
      affiliation,
      reconfirm,
      history,
    })

  const affiliationContent = affiliationLoading ? (
    <Skeleton className="h-80 w-full" />
  ) : affiliationError ? (
    <div className="rounded-lg border bg-card p-4" role="alert">
      <p className="text-sm text-destructive">
        {affiliationError?.message || "소속 정보를 불러오지 못했습니다."}
      </p>
    </div>
  ) : (
    <AffiliationCard data={affiliationData} />
  )

  if (!hasPortalAccess) {
    return (
      <div className="flex w-full flex-col gap-4">
        <section className="space-y-1">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">계정 및 소속</h2>
          <p className="text-sm text-muted-foreground">
            등록된 소속을 확인합니다. 접근 권한은 관리자가 별도로 부여합니다.
          </p>
        </section>
        <div className="min-w-0">{affiliationContent}</div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-4 overflow-hidden py-4">
      {overviewError ? (
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-destructive">
            {overviewError?.message || "계정 정보를 불러오지 못했습니다."}
          </p>
        </div>
      ) : overviewLoading ? (
        <div className="flex h-full min-h-0 w-full flex-col gap-4 overflow-hidden">
          <Skeleton className="h-56 w-full shrink-0" />
          <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto lg:grid-cols-3 lg:overflow-hidden">
            <Skeleton className="h-full min-h-0 w-full" />
            <Skeleton className="h-full min-h-0 w-full" />
            <Skeleton className="h-full min-h-0 w-full" />
          </section>
        </div>
      ) : (
        <>
          <section className="shrink-0">
            <AccountSummaryPanel
              pageTitle={pageTitle}
              profile={profile}
              summary={accountSummary}
            />
          </section>

          <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto lg:grid-cols-3 lg:overflow-hidden">
            <div className="h-full min-h-0 min-w-0 overflow-hidden">
              {affiliationContent}
            </div>
            <div className="h-full min-h-0 min-w-0 overflow-hidden">
              <ManageableGroupsCard groups={manageableGroups} />
            </div>
            <div className="h-full min-h-0 min-w-0 overflow-hidden">
              <AffiliationHistoryCard history={history} />
            </div>
          </section>
        </>
      )}
    </div>
  )
}
