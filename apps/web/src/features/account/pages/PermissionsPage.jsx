import { useCallback, useMemo, useRef, useState } from "react"
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
import { DataScopeDialog } from "../components/DataScopeDialog"
import { PendingAccessPanel } from "../components/PendingAccessPanel"
import { PermissionDecisionDialog } from "../components/PermissionDecisionDialog"
import {
  PermissionDesktopSummary,
  PermissionSummaryTile,
} from "../components/PermissionSummary"
import { ScopePermissionMatrix } from "../components/ScopePermissionMatrix"
import {
  useAccessAuditLogs,
  useBulkApprovePendingAccessRequests,
  useAccessMatrix,
  useAccessPolicyRules,
  useAccessUserDecision,
  useApplyAllUserAccess,
  usePendingAccessRequests,
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
  manualGrantOnly: false,
}

const PERMISSION_VALUE_LABELS = {
  inherit: "자동 규칙",
  user: "일반",
  admin: "관리자",
  denied: "접근 차단",
}

export default function PermissionsPage() {
  const { user, isLoading } = useAuth()
  const isPortalAdmin = hasScopeRole(user, "portal")
  const [activeTab, setActiveTab] = useState("matrix")
  const [pendingScope, setPendingScope] = useState("all")
  const [auditPage, setAuditPage] = useState(1)
  const [auditScope, setAuditScope] = useState("all")
  const [decision, setDecision] = useState(null)
  const [decisionError, setDecisionError] = useState("")
  const [dataScopeSelection, setDataScopeSelection] = useState(null)
  const [matrixFilters, setMatrixFilters] = useState({ ...EMPTY_MATRIX_FILTERS })
  const [matrixFilterDraft, setMatrixFilterDraft] = useState({ ...EMPTY_MATRIX_FILTERS })
  const [pendingMatrixCell, setPendingMatrixCell] = useState("")

  const pendingQuery = usePendingAccessRequests({
    pageSize: PERMISSION_PAGE_SIZE,
    scope: pendingScope,
    enabled: isPortalAdmin,
  })
  const policyQuery = useAccessPolicyRules({ scope: "all", enabled: isPortalAdmin })
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
    manualGrantOnly: matrixFilters.manualGrantOnly,
    enabled: isPortalAdmin,
  })
  const decisionMutation = useAccessUserDecision()
  const bulkApprovalMutation = useBulkApprovePendingAccessRequests()
  const applyAllAccessMutation = useApplyAllUserAccess()
  const matrixMutationInFlightRef = useRef(false)
  const matrixRows = matrixQuery.data?.results || []
  const matrixTotal = matrixQuery.data?.pagination?.total ?? 0
  const matrixLoadedTotal = matrixRows.length
  const portalPolicyAllowed = matrixRows.filter(
    (row) => row.accesses?.portal?.source === "policy_department",
  ).length
  const pendingTotal = pendingQuery.data?.summary?.total ?? 0
  const policyTotal = policyQuery.data?.results?.length ?? 0
  const accessScopeOptions = useMemo(
    () => buildAccessScopeOptions(matrixQuery.data?.scopes),
    [matrixQuery.data?.scopes],
  )
  const pendingScopeOptions = useMemo(() => {
    const counts = new Map(
      (pendingQuery.data?.scopeCounts || []).map((row) => [
        row.scope?.key,
        Number(row.total) || 0,
      ]),
    )
    const optionsByValue = new Map(
      accessScopeOptions.map((option) => [
        option.value,
        { ...option, count: counts.get(option.value) || 0 },
      ]),
    )
    for (const row of pendingQuery.data?.scopeCounts || []) {
      const key = row.scope?.key
      if (!key || optionsByValue.has(key)) continue
      optionsByValue.set(key, {
        value: key,
        label: row.scope?.name || key,
        count: Number(row.total) || 0,
      })
    }
    return [
      { value: "all", label: "전체 요청", count: pendingTotal },
      ...optionsByValue.values(),
    ]
  }, [accessScopeOptions, pendingQuery.data?.scopeCounts, pendingTotal])
  const auditScopeOptions = [{ value: "all", label: "전체 권한 범위" }, ...accessScopeOptions]
  const hasAppliedMatrixFilters = Boolean(
    matrixFilters.search
    || matrixFilters.department
    || matrixFilters.manualGrantOnly
  )
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
    if (decisionMutation.isPending || applyAllAccessMutation.isPending) return
    setDecisionError("")
    const matrixCellKey = decision?.matrixCellKey || ""
    if (matrixCellKey) {
      matrixMutationInFlightRef.current = true
      setPendingMatrixCell(matrixCellKey)
    }
    try {
      if (decision?.action === "apply_all") {
        const result = await applyAllAccessMutation.mutateAsync({
          userId: payload.userId,
          value: decision.nextValue,
          reason: payload.reason,
        })
        const updated = Number(result?.summary?.updated) || 0
        const userLabel = decision.row.user.displayName
          || decision.row.user.knoxId
          || decision.row.user.id
        const permissionLabel = PERMISSION_VALUE_LABELS[decision.nextValue]
          || decision.nextValue
        toast.success(
          `${userLabel}님의 모든 권한을 변경했습니다. (${permissionLabel}, ${updated}건 변경)`,
        )
      } else {
        await decisionMutation.mutateAsync(payload)
        toast.success("사용자 권한을 변경했습니다.")
      }
      setDecision(null)
    } catch (error) {
      const message = getPermissionMutationErrorMessage(error, "사용자 권한을 변경하지 못했습니다.")
      setDecisionError(message)
      toast.error(message)
    } finally {
      if (matrixCellKey) {
        matrixMutationInFlightRef.current = false
        setPendingMatrixCell("")
      }
    }
  }

  const handleBulkApprove = async (requestIds) => {
    const result = await bulkApprovalMutation.mutateAsync({ requestIds })
    const approved = Number(result?.summary?.approved) || 0
    const failed = Number(result?.summary?.failed) || 0
    if (failed > 0) {
      toast.warning(`${approved}건을 승인했고 ${failed}건은 이미 처리되었거나 찾을 수 없습니다.`)
    } else {
      toast.success(`${approved}건의 권한 요청을 승인했습니다.`)
    }
    return result
  }

  const handleApplyMatrixFilters = () => {
    setMatrixFilters({
      search: matrixFilterDraft.search.trim(),
      department: matrixFilterDraft.department.trim(),
      manualGrantOnly: matrixFilterDraft.manualGrantOnly,
    })
  }

  const handleResetMatrixFilters = () => {
    setMatrixFilterDraft({ ...EMPTY_MATRIX_FILTERS })
    setMatrixFilters({ ...EMPTY_MATRIX_FILTERS })
  }

  const handleManualGrantOnlyChange = (manualGrantOnly) => {
    setMatrixFilterDraft((current) => ({ ...current, manualGrantOnly }))
    setMatrixFilters((current) => ({ ...current, manualGrantOnly }))
  }

  const handleApplyAllAccess = ({ user: targetUser, nextValue }) => {
    if (
      !targetUser?.id
      || matrixMutationInFlightRef.current
      || applyAllAccessMutation.isPending
    ) {
      return
    }
    setDecisionError("")
    setDecision({
      row: { user: targetUser },
      action: "apply_all",
      label: "모든 앱·기능 권한 변경",
      nextValue,
      description: `${PERMISSION_VALUE_LABELS[nextValue] || nextValue} 권한을 모든 범위에 적용합니다.`,
    })
  }

  const handleMatrixAccessChange = useCallback(({
    user: targetUser,
    scope,
    access,
    nextValue,
  }) => {
    if (matrixMutationInFlightRef.current || isScopeAccessBypass(access)) return

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

    setDecisionError("")
    setDecision({
      row: { user: targetUser },
      action,
      label: `${scope.name} 권한 변경`,
      role: ["user", "admin"].includes(nextValue) ? nextValue : undefined,
      scope,
      matrixCellKey: `${targetUser.id}:${scope.key}`,
    })
  }, [])

  const handleRefresh = () => {
    matrixQuery.refetch()
    pendingQuery.refetch()
    policyQuery.refetch()
    if (activeTab === "audit") auditQuery.refetch()
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
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

      <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
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
          <div className="grid h-full min-h-0 min-w-0 grid-rows-[min-content_minmax(0,1fr)] gap-4 overflow-hidden">
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
                detail="전체 범위 · 사용/미사용"
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
                detail="전체 범위 · 사용/미사용"
                isLoading={policyQuery.isFetching}
              />
            </section>

            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="h-full min-h-0 min-w-0 gap-4 overflow-hidden"
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

              <TabsContent value="matrix" className="min-h-0 min-w-0 overflow-hidden">
                <ScopePermissionMatrix
                  query={matrixQuery}
                  filters={matrixFilters}
                  filterDraft={matrixFilterDraft}
                  setFilterDraft={setMatrixFilterDraft}
                  onApplyFilters={handleApplyMatrixFilters}
                  onResetFilters={handleResetMatrixFilters}
                  onManualGrantOnlyChange={handleManualGrantOnlyChange}
                  onAccessChange={handleMatrixAccessChange}
                  onApplyAllAccess={handleApplyAllAccess}
                  onDataScopeChange={setDataScopeSelection}
                  isApplyingAll={applyAllAccessMutation.isPending}
                  pendingCell={pendingMatrixCell}
                />
              </TabsContent>

              <TabsContent value="pending" className="min-h-0 min-w-0 overflow-hidden">
                <PendingAccessPanel
                  query={pendingQuery}
                  scope={pendingScope}
                  scopeOptions={pendingScopeOptions}
                  onScopeChange={setPendingScope}
                  onDecision={(row, action, label) => {
                    const rowScope = row.scope?.key === "portal"
                      ? null
                      : {
                          key: row.scope?.key,
                          name: row.scope?.name || row.scope?.key,
                        }
                    handleDecisionOpen(row, action, label, rowScope)
                  }}
                  onBulkApprove={handleBulkApprove}
                  isMutating={decisionMutation.isPending || bulkApprovalMutation.isPending}
                  isBulkApproving={bulkApprovalMutation.isPending}
                />
              </TabsContent>
              <TabsContent value="policies" className="min-h-0 min-w-0 overflow-hidden">
                <AccessPolicyPanel
                  query={policyQuery}
                  scopeOptions={accessScopeOptions}
                />
              </TabsContent>
              <TabsContent value="audit" className="min-h-0 min-w-0 overflow-hidden">
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
        isSubmitting={decisionMutation.isPending || applyAllAccessMutation.isPending}
        errorMessage={decisionError}
      />
      <DataScopeDialog
        selection={dataScopeSelection}
        onOpenChange={(open) => {
          if (!open) setDataScopeSelection(null)
        }}
      />
    </div>
  )
}
