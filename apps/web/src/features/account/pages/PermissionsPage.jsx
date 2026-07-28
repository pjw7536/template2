import { useMemo, useState } from "react"
import { Clock3, History, RefreshCw, ShieldCheck, SlidersHorizontal, Users } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { hasScopeRole, isScopeAccessBypass } from "@/lib/access/scopeAccess"
import { useAuth } from "@/lib/auth"

import { AccessAuditPanel } from "../components/AccessAuditPanel"
import { AccessPolicyPanel } from "../components/AccessPolicyPanel"
import { PendingAccessPanel } from "../components/PendingAccessPanel"
import { PermissionDecisionDialog } from "../components/PermissionDecisionDialog"
import {
  PermissionDesktopSummary,
  PermissionSummaryTile,
} from "../components/PermissionSummary"
import { ScopePermissionMatrix } from "../components/ScopePermissionMatrix"
import {
  useAccessAuditLogs,
  useAccessMatrix,
  useAccessPolicyRules,
  useAccessUserDecision,
  useAccessUsers,
} from "../hooks/useAccountData"
import {
  buildAccessScopeOptions,
  formatPermissionCount,
  getPermissionMutationErrorMessage,
  PERMISSION_PAGE_SIZE,
} from "../utils/permissionDisplay"


const EMPTY_MATRIX_FILTERS = {
  search: "",
  department: "",
}

export default function PermissionsPage() {
  const { user, isLoading } = useAuth()
  const isPortalAdmin = hasScopeRole(user, "portal")
  const [activeTab, setActiveTab] = useState("matrix")
  const [pendingPage, setPendingPage] = useState(1)
  const [pendingScope, setPendingScope] = useState("portal")
  const [auditPage, setAuditPage] = useState(1)
  const [auditScope, setAuditScope] = useState("all")
  const [policyScope, setPolicyScope] = useState("portal")
  const [decision, setDecision] = useState(null)
  const [decisionError, setDecisionError] = useState("")
  const [matrixFilters, setMatrixFilters] = useState({ ...EMPTY_MATRIX_FILTERS })
  const [matrixFilterDraft, setMatrixFilterDraft] = useState({ ...EMPTY_MATRIX_FILTERS })
  const [pendingMatrixCell, setPendingMatrixCell] = useState("")

  const pendingQuery = useAccessUsers({
    page: pendingPage,
    pageSize: PERMISSION_PAGE_SIZE,
    status: "pending",
    scope: pendingScope,
    enabled: isPortalAdmin,
  })
  const policyQuery = useAccessPolicyRules({ scope: policyScope, enabled: isPortalAdmin })
  const auditQuery = useAccessAuditLogs({
    page: auditPage,
    pageSize: PERMISSION_PAGE_SIZE,
    scope: auditScope === "all" ? "" : auditScope,
    enabled: isPortalAdmin && activeTab === "audit",
  })
  const matrixQuery = useAccessMatrix({
    pageSize: PERMISSION_PAGE_SIZE,
    search: matrixFilters.search,
    department: matrixFilters.department,
    enabled: isPortalAdmin,
  })
  const decisionMutation = useAccessUserDecision()
  const matrixRows = matrixQuery.data?.results || []
  const matrixTotal = matrixQuery.data?.pagination?.total ?? 0
  const matrixLoadedTotal = matrixRows.length
  const portalPolicyAllowed = matrixRows.filter(
    (row) => row.accesses?.portal?.source === "policy_department",
  ).length
  const pendingTotal = pendingQuery.data?.pagination?.total ?? 0
  const policyTotal = policyQuery.data?.results?.length ?? 0
  const accessScopeOptions = useMemo(
    () => buildAccessScopeOptions(matrixQuery.data?.scopes),
    [matrixQuery.data?.scopes],
  )
  const auditScopeOptions = [{ value: "all", label: "전체 권한 범위" }, ...accessScopeOptions]
  const pendingScopeOption = accessScopeOptions.find((option) => option.value === pendingScope)
  const pendingDecisionScope = pendingScope === "portal"
    ? null
    : {
        key: pendingScope,
        name: pendingScopeOption?.label || pendingScope,
      }
  const policyScopeLabel = accessScopeOptions.find((option) => option.value === policyScope)?.label || policyScope
  const hasAppliedMatrixFilters = Boolean(matrixFilters.search || matrixFilters.department)
  const isMatrixReplacing = matrixQuery.isFetching && !matrixQuery.isFetchingNextPage
  const isRefreshing =
    pendingQuery.isFetching || policyQuery.isFetching || auditQuery.isFetching || matrixQuery.isFetching

  const handleDecisionOpen = (row, action, label, scope = null) => {
    if (decisionMutation.isPending) return
    setDecisionError("")
    setDecision({
      row,
      action,
      label,
      role: row.access?.role || "user",
      scope,
    })
  }

  const handleDecisionSubmit = async (payload) => {
    if (decisionMutation.isPending) return
    setDecisionError("")
    try {
      await decisionMutation.mutateAsync(payload)
      setDecision(null)
      toast.success("사용자 권한을 변경했습니다.")
    } catch (error) {
      const message = getPermissionMutationErrorMessage(error, "사용자 권한을 변경하지 못했습니다.")
      setDecisionError(message)
      toast.error(message)
    }
  }

  const handleApplyMatrixFilters = () => {
    setMatrixFilters({
      search: matrixFilterDraft.search.trim(),
      department: matrixFilterDraft.department.trim(),
    })
  }

  const handleResetMatrixFilters = () => {
    setMatrixFilterDraft({ ...EMPTY_MATRIX_FILTERS })
    setMatrixFilters({ ...EMPTY_MATRIX_FILTERS })
  }

  const handleMatrixAccessChange = async ({ user: targetUser, scope, access, nextValue }) => {
    if (decisionMutation.isPending || isScopeAccessBypass(access)) return

    let action = ""
    if (nextValue === "denied") {
      action = "revoke"
    } else if (["user", "admin"].includes(nextValue)) {
      const underlyingAllowed = access?.blockedByPortal && access?.underlyingAccess?.allowed
      action = access?.allowed || underlyingAllowed ? "change_role" : "grant"
    } else if (nextValue === "inherit") {
      action = "reset_to_policy"
    } else {
      return
    }

    const cellKey = `${targetUser.id}:${scope.key}`
    setPendingMatrixCell(cellKey)
    try {
      await decisionMutation.mutateAsync({
        userId: targetUser.id,
        scope: scope.key,
        action,
        role: ["user", "admin"].includes(nextValue) ? nextValue : undefined,
        reason: "권한 매트릭스에서 수동 변경",
      })
      toast.success(`${scope.name} 권한을 변경했습니다.`)
    } catch (error) {
      toast.error(
        getPermissionMutationErrorMessage(
          error,
          `${scope.name} 권한을 변경하지 못했습니다.`,
        ),
      )
    } finally {
      setPendingMatrixCell("")
    }
  }

  const handleRefresh = () => {
    matrixQuery.refetch()
    pendingQuery.refetch()
    policyQuery.refetch()
    if (activeTab === "audit") auditQuery.refetch()
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-y-auto xl:overflow-hidden">
      <section className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">권한 관리</h2>
            <Badge variant="outline">Portal + Scopes</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Portal과 앱·기능의 접근 상태 및 일반 사용자·관리자 역할을 한 곳에서 관리합니다.
          </p>
        </div>
        <Button variant="outline" onClick={handleRefresh} disabled={!isPortalAdmin || isRefreshing}>
          <RefreshCw className={isRefreshing ? "size-4 animate-spin" : "size-4"} />
          새로고침
        </Button>
      </section>

      <div className="min-w-0 xl:min-h-0 xl:flex-1 xl:overflow-hidden">
        {isLoading ? (
          <Skeleton className="h-full min-h-48 w-full" />
        ) : !isPortalAdmin ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">접근 불가</CardTitle>
              <CardDescription>권한 관리 권한이 없습니다.</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <div className="grid min-w-0 gap-4 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:overflow-hidden">
            <section className="grid shrink-0 grid-cols-2 gap-3 xl:hidden">
              <PermissionSummaryTile
                icon={Users}
                label={hasAppliedMatrixFilters ? "필터 결과" : "전체 인원"}
                value={matrixTotal}
                detail={`불러온 사용자 ${formatPermissionCount(matrixLoadedTotal)}명`}
                tone="secondary"
                isLoading={isMatrixReplacing}
              />
              <PermissionSummaryTile
                icon={Clock3}
                label="승인 대기"
                value={pendingTotal}
                detail="처리 필요 요청"
                tone="destructive"
                isLoading={pendingQuery.isFetching}
              />
              <PermissionSummaryTile
                icon={ShieldCheck}
                label="자동 허용"
                value={portalPolicyAllowed}
                detail="불러온 사용자 기준"
                tone="primary"
                isLoading={isMatrixReplacing}
              />
              <PermissionSummaryTile
                icon={SlidersHorizontal}
                label="자동 규칙"
                value={policyTotal}
                detail={`${policyScopeLabel} · 사용/미사용`}
                isLoading={policyQuery.isFetching}
              />
            </section>

            <section className="hidden shrink-0 overflow-hidden rounded-lg border bg-card xl:grid xl:grid-cols-4">
              <PermissionDesktopSummary
                icon={Users}
                label={hasAppliedMatrixFilters ? "필터 결과" : "전체 사용자"}
                value={matrixTotal}
                detail={`불러온 사용자 ${formatPermissionCount(matrixLoadedTotal)}명`}
                tone="secondary"
                isLoading={isMatrixReplacing}
              />
              <PermissionDesktopSummary
                icon={Clock3}
                label="승인 대기"
                value={pendingTotal}
                detail="처리할 접근 요청"
                tone="destructive"
                isLoading={pendingQuery.isFetching}
              />
              <PermissionDesktopSummary
                icon={ShieldCheck}
                label="불러온 사용자 자동 허용"
                value={portalPolicyAllowed}
                detail="자동 접근 규칙 기준"
                tone="primary"
                isLoading={isMatrixReplacing}
              />
              <PermissionDesktopSummary
                icon={SlidersHorizontal}
                label="자동 접근 규칙"
                value={policyTotal}
                detail={`${policyScopeLabel} · 사용/미사용`}
                isLoading={policyQuery.isFetching}
              />
            </section>

            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="min-w-0 gap-4 xl:h-full xl:min-h-0 xl:overflow-hidden"
            >
              <div className="min-w-0 shrink-0 overflow-x-auto pb-1">
                <TabsList className="grid w-full shrink-0 grid-cols-4 xl:inline-flex xl:w-max">
                  <TabsTrigger value="matrix">
                    <SlidersHorizontal className="hidden size-4 xl:block" />
                    <span className="xl:hidden">매트릭스</span>
                    <span className="hidden xl:inline">권한 매트릭스</span>
                  </TabsTrigger>
                  <TabsTrigger value="pending">
                    <Clock3 className="hidden size-4 xl:block" />
                    승인 대기
                    <Badge
                      variant={pendingTotal > 0 ? "destructive" : "secondary"}
                      className="hidden min-w-5 justify-center px-1.5 tabular-nums xl:inline-flex"
                    >
                      {formatPermissionCount(pendingTotal)}
                    </Badge>
                  </TabsTrigger>
                  <TabsTrigger value="policies">
                    <SlidersHorizontal className="hidden size-4 xl:block" />
                    <span className="xl:hidden">자동 규칙</span>
                    <span className="hidden xl:inline">자동 접근 규칙</span>
                    <Badge
                      variant="outline"
                      className="hidden min-w-5 justify-center px-1.5 tabular-nums xl:inline-flex"
                    >
                      {formatPermissionCount(policyTotal)}
                    </Badge>
                  </TabsTrigger>
                  <TabsTrigger value="audit">
                    <History className="hidden size-4 xl:block" />
                    변경 이력
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="matrix" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <ScopePermissionMatrix
                  query={matrixQuery}
                  filters={matrixFilters}
                  filterDraft={matrixFilterDraft}
                  setFilterDraft={setMatrixFilterDraft}
                  onApplyFilters={handleApplyMatrixFilters}
                  onResetFilters={handleResetMatrixFilters}
                  onAccessChange={handleMatrixAccessChange}
                  pendingCell={pendingMatrixCell}
                  isMutating={decisionMutation.isPending}
                />
              </TabsContent>

              <TabsContent value="pending" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <PendingAccessPanel
                  query={pendingQuery}
                  scope={pendingScope}
                  scopeOptions={accessScopeOptions}
                  onScopeChange={(value) => {
                    setPendingScope(value)
                    setPendingPage(1)
                  }}
                  onDecision={(row, action, label) => {
                    handleDecisionOpen(row, action, label, pendingDecisionScope)
                  }}
                  onPageChange={setPendingPage}
                  isMutating={decisionMutation.isPending}
                />
              </TabsContent>
              <TabsContent value="policies" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <AccessPolicyPanel
                  key={policyScope}
                  query={policyQuery}
                  scope={policyScope}
                  scopeOptions={accessScopeOptions}
                  onScopeChange={setPolicyScope}
                />
              </TabsContent>
              <TabsContent value="audit" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <AccessAuditPanel
                  query={auditQuery}
                  scope={auditScope}
                  scopeOptions={auditScopeOptions}
                  onScopeChange={(value) => {
                    setAuditScope(value)
                    setAuditPage(1)
                  }}
                  onPageChange={setAuditPage}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>

      <PermissionDecisionDialog
        decision={decision}
        onOpenChange={(open) => {
          if (!open) setDecision(null)
        }}
        onSubmit={handleDecisionSubmit}
        isSubmitting={decisionMutation.isPending}
        errorMessage={decisionError}
      />
    </div>
  )
}
