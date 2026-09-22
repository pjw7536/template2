import {
  Ban,
  Check,
  CheckCheck,
  Eye,
  Layers3,
  LoaderCircle,
  MoreHorizontal,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  UserPlus,
} from "lucide-react"
import { useEffect, useState } from "react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { isScopeAccessBypass } from "@/lib/access/scopeAccess"

import { formatAccountDateValue } from "../utils/accountOverview"
import {
  ACCESS_ROLE_LABELS,
  ACCESS_RULE_TYPE_LABELS,
  ACCESS_SOURCE_LABELS,
  ACCESS_STATUS_LABELS,
  formatPermissionCount,
  getPermissionMutationErrorMessage,
} from "../utils/permissionDisplay"
import { AccountDataTable } from "./AccountDataTable"


function getStatusVariant(status) {
  if (status === "allowed") return "default"
  if (status === "pending") return "secondary"
  if (status === "denied") return "destructive"
  return "outline"
}

function AccessStatusBadge({ access }) {
  const status = access?.effectiveStatus || "not_requested"
  return (
    <Badge variant={getStatusVariant(status)}>
      {ACCESS_STATUS_LABELS[status] || status}
    </Badge>
  )
}

function AccessSourceMeta({ access }) {
  const source = access?.source
  const policy = access?.policy
  const policyLabel =
    policy?.matched && policy?.ruleType
      ? `${ACCESS_RULE_TYPE_LABELS[policy.ruleType] || policy.ruleType} / ${policy.value || "-"}`
      : ""

  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      <Badge variant="outline">{ACCESS_SOURCE_LABELS[source] || source || "-"}</Badge>
      {policyLabel ? (
        <span className="max-w-56 truncate text-xs text-muted-foreground" title={policyLabel}>
          {policyLabel}
        </span>
      ) : null}
    </span>
  )
}

function getUserInitials(user) {
  const label = user?.displayName || user?.username || user?.knoxId || "?"
  const parts = label.trim().split(/\s+/).filter(Boolean)
  if (parts.length > 1) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return label.slice(0, 2).toUpperCase()
}

function UserIdentity({ user }) {
  const name = user?.displayName || user?.username || user?.knoxId || "미지정"
  const identifier = user?.knoxId || user?.sabun || "-"
  return (
    <div className="flex min-w-0 items-center gap-3 whitespace-nowrap">
      <Avatar className="size-9 border">
        <AvatarFallback className="text-xs font-medium text-muted-foreground">
          {getUserInitials(user)}
        </AvatarFallback>
      </Avatar>
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="truncate font-medium">{name}</span>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="truncate text-xs text-muted-foreground">{identifier}</span>
      </span>
    </div>
  )
}

function ScopeIdentity({ scope }) {
  const label = scope?.name || scope?.key || "권한 범위"
  return (
    <div className="flex min-w-0 items-center gap-2 whitespace-nowrap">
      <Layers3 className="size-4 text-muted-foreground" />
      <span className="truncate text-sm font-medium">{label}</span>
    </div>
  )
}

function RoleIndicator({ role }) {
  const Icon = role === "admin" ? ShieldCheck : Eye
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <Icon className="size-4 text-muted-foreground" />
      <span>{ACCESS_ROLE_LABELS[role] || role || "-"}</span>
    </span>
  )
}

function UserActions({ row, onDecision, disabled = false }) {
  const access = row.access || {}
  const explicitStatus = access.explicitStatus
  const status = access.effectiveStatus
  const userLabel = row.user.displayName || row.user.knoxId || row.user.username || "사용자"

  if (isScopeAccessBypass(access)) {
    return <span className="whitespace-nowrap text-xs text-muted-foreground">슈퍼유저 권한으로 허용</span>
  }

  const primaryAction = status === "pending"
    ? { action: "approve", label: "승인", icon: Check, variant: "default" }
    : status === "allowed"
      ? { action: "change_role", label: "역할 변경", icon: SlidersHorizontal, variant: "outline" }
      : ["denied", "not_requested"].includes(status)
        ? { action: "grant", label: "직접 부여", icon: UserPlus, variant: "default" }
        : null
  const PrimaryIcon = primaryAction?.icon
  const hasMoreActions = status === "pending" || status === "allowed" || Boolean(explicitStatus)

  return (
    <>
      <div className="flex items-center justify-end gap-2 whitespace-nowrap xl:hidden">
        {status === "pending" ? (
          <>
            <Button
              size="sm"
              onClick={() => onDecision(row, "approve")}
              disabled={disabled}
              aria-label={`${userLabel} 승인`}
            >
              <Check className="size-4" />
              승인
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => onDecision(row, "reject")}
              disabled={disabled}
              aria-label={`${userLabel} 거절`}
            >
              <Ban className="size-4" />
              거절
            </Button>
          </>
        ) : null}
        {status === "allowed" ? (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDecision(row, "change_role")}
              disabled={disabled}
              aria-label={`${userLabel} 권한 변경`}
            >
              <SlidersHorizontal className="size-4" />
              권한 변경
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => onDecision(row, "revoke")}
              disabled={disabled}
              aria-label={`${userLabel} 권한 회수`}
            >
              <Ban className="size-4" />
              회수
            </Button>
          </>
        ) : null}
        {["denied", "not_requested"].includes(status) ? (
          <Button
            size="sm"
            onClick={() => onDecision(row, "grant")}
            disabled={disabled}
            aria-label={`${userLabel} 권한 직접 부여`}
          >
            <UserPlus className="size-4" />
            직접 부여
          </Button>
        ) : null}
        {explicitStatus ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onDecision(row, "reset_to_policy")}
            disabled={disabled}
            aria-label={`${userLabel} 수동 설정 해제`}
          >
            <RotateCcw className="size-4" />
            수동 설정 해제
          </Button>
        ) : null}
      </div>

      <div className="hidden items-center justify-end gap-1.5 xl:flex">
        {primaryAction ? (
          <Button
            size="sm"
            variant={primaryAction.variant}
            onClick={() => onDecision(row, primaryAction.action, primaryAction.label)}
            disabled={disabled}
            aria-label={`${userLabel} ${primaryAction.label}`}
          >
            <PrimaryIcon className="size-4" />
            {primaryAction.label}
          </Button>
        ) : null}
        {hasMoreActions ? (
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    disabled={disabled}
                    aria-label={`${userLabel} 추가 작업`}
                  >
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent side="top">추가 작업</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end">
              {status === "pending" ? (
                <DropdownMenuItem variant="destructive" onSelect={() => onDecision(row, "reject", "거절")}>
                  <Ban className="size-4" />
                  거절
                </DropdownMenuItem>
              ) : null}
              {status === "allowed" ? (
                <DropdownMenuItem variant="destructive" onSelect={() => onDecision(row, "revoke", "회수")}>
                  <Ban className="size-4" />
                  회수
                </DropdownMenuItem>
              ) : null}
              {explicitStatus ? (
                <DropdownMenuItem
                  onSelect={() => onDecision(row, "reset_to_policy", "수동 설정 해제")}
                >
                  <RotateCcw className="size-4" />
                  수동 설정 해제
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </>
  )
}

function AccessUsersTable({
  rows,
  isLoading,
  isFetching,
  error,
  onDecision,
  isMutating = false,
  onRetry,
  onLoadMore,
  scrollFooter,
  selectedRequestIds,
  onToggleRequest,
  onToggleLoaded,
}) {
  const loadedRequestIds = rows
    .map((row) => row.requestId)
    .filter((requestId) => Number.isInteger(requestId) && requestId > 0)
  const allLoadedSelected =
    loadedRequestIds.length > 0
    && loadedRequestIds.every((requestId) => selectedRequestIds.has(requestId))
  const someLoadedSelected =
    !allLoadedSelected
    && loadedRequestIds.some((requestId) => selectedRequestIds.has(requestId))
  const columns = [
    {
      id: "select",
      header: () => (
        <Checkbox
          checked={allLoadedSelected ? true : someLoadedSelected ? "indeterminate" : false}
          onCheckedChange={() => onToggleLoaded(loadedRequestIds, !allLoadedSelected)}
          disabled={isMutating || isFetching || loadedRequestIds.length === 0}
          aria-label="불러온 요청 전체 선택"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={selectedRequestIds.has(row.original.requestId)}
          onCheckedChange={(checked) => onToggleRequest(row.original.requestId, checked === true)}
          disabled={isMutating || isFetching}
          aria-label={`${row.original.user.displayName || row.original.user.knoxId || "사용자"} ${row.original.scope?.name || "권한"} 요청 선택`}
        />
      ),
      meta: {
        headerClassName: "w-12 min-w-12",
        cellClassName: "w-12 min-w-12",
      },
    },
    {
      id: "user",
      header: "사용자",
      cell: ({ row }) => <UserIdentity user={row.original.user} />,
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "scope",
      header: "신청 앱·기능",
      cell: ({ row }) => <ScopeIdentity scope={row.original.scope} />,
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "affiliation",
      header: "소속",
      cell: ({ row }) => (
        <div className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
          <span className="truncate text-sm">{row.original.user.department || "-"}</span>
          <span className="text-xs text-muted-foreground">/</span>
          <span className="truncate text-xs text-muted-foreground">
            {row.original.user.userSdwtProd || "-"}
          </span>
        </div>
      ),
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "accessStatus",
      header: "접근 상태 / 결정 기준",
      cell: ({ row }) => (
        <div className="flex min-w-0 items-center gap-2 whitespace-nowrap">
          <AccessStatusBadge access={row.original.access || {}} />
          <AccessSourceMeta access={row.original.access || {}} />
        </div>
      ),
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "accessRole",
      header: "접근 역할",
      cell: ({ row }) => <RoleIndicator role={row.original.access?.role} />,
      meta: {
        headerClassName: "min-w-36",
        cellClassName: "min-w-36",
      },
    },
    {
      id: "decidedAt",
      header: "요청일",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {formatAccountDateValue(row.original.access?.decidedAt || row.original.access?.requestedAt)}
        </span>
      ),
      meta: {
        headerClassName: "min-w-44",
        cellClassName: "min-w-44",
      },
    },
    {
      id: "actions",
      header: "작업",
      cell: ({ row }) => (
        <UserActions row={row.original} onDecision={onDecision} disabled={isMutating || isFetching} />
      ),
      meta: {
        headerClassName: "sticky right-0 z-20 min-w-44 bg-muted text-right",
        cellClassName: "sticky right-0 z-10 min-w-44 bg-card text-right group-hover:bg-muted/40",
      },
    },
  ]
  const errorMessage = error?.message === "forbidden"
    ? "권한 관리 권한이 없습니다."
    : error
      ? "승인 대기 요청을 불러오지 못했습니다."
      : ""

  return (
    <AccountDataTable
      data={rows}
      columns={columns}
      getRowId={(row) => String(row.requestId)}
      isLoading={isLoading}
      isFetching={isFetching}
      error={errorMessage}
      emptyMessage="승인 대기 요청이 없습니다."
      onRetry={onRetry}
      className="h-full rounded-none border-0 [&_[data-slot=table-container]]:h-auto [&_[data-slot=table-container]]:overflow-visible"
      tableClassName="min-w-[1340px]"
      onScrollEnd={onLoadMore}
      scrollFooter={scrollFooter}
      ariaLabel="전체 권한 승인 대기 요청 목록"
    />
  )
}

export function PendingAccessPanel({
  query,
  scope,
  scopeOptions,
  onScopeChange,
  onDecision,
  onBulkApprove,
  isMutating,
  isBulkApproving,
}) {
  const [selectedRequestIds, setSelectedRequestIds] = useState(() => new Set())
  const [isBulkDialogOpen, setIsBulkDialogOpen] = useState(false)
  const [bulkError, setBulkError] = useState("")
  const scopeLabel = scopeOptions.find((option) => option.value === scope)?.label || scope
  const rows = query.data?.results || []
  const loadedRequestIdsKey = rows
    .map((row) => row.requestId)
    .filter((requestId) => Number.isInteger(requestId) && requestId > 0)
    .join(",")
  const selectedCount = selectedRequestIds.size

  useEffect(() => {
    setSelectedRequestIds(new Set())
    setIsBulkDialogOpen(false)
    setBulkError("")
  }, [scope])

  useEffect(() => {
    const loadedRequestIds = new Set(
      loadedRequestIdsKey
        .split(",")
        .map(Number)
        .filter((requestId) => Number.isInteger(requestId) && requestId > 0),
    )
    setSelectedRequestIds((current) => {
      const next = new Set(
        [...current].filter((requestId) => loadedRequestIds.has(requestId)),
      )
      return next.size === current.size ? current : next
    })
  }, [loadedRequestIdsKey])

  const handleToggleRequest = (requestId, checked) => {
    if (!Number.isInteger(requestId) || requestId <= 0) return
    setSelectedRequestIds((current) => {
      const next = new Set(current)
      if (checked) {
        next.add(requestId)
      } else {
        next.delete(requestId)
      }
      return next
    })
  }

  const handleToggleLoaded = (requestIds, checked) => {
    setSelectedRequestIds((current) => {
      const next = new Set(current)
      for (const requestId of requestIds) {
        if (checked) {
          next.add(requestId)
        } else {
          next.delete(requestId)
        }
      }
      return next
    })
  }

  const handleLoadMore = () => {
    if (
      !query.hasNextPage
      || query.isFetchingNextPage
      || query.isFetchNextPageError
    ) {
      return
    }
    void query.fetchNextPage()
  }

  const scrollFooter = rows.length > 0 ? (
    <div
      className="flex min-h-12 items-center justify-center gap-2 border-t px-4 py-3 text-sm text-muted-foreground"
      aria-live="polite"
    >
      {query.isFetchingNextPage ? (
        <>
          <LoaderCircle className="size-4 animate-spin" />
          다음 요청을 불러오는 중...
        </>
      ) : query.isFetchNextPageError ? (
        <>
          <span className="text-destructive">다음 요청을 불러오지 못했습니다.</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void query.fetchNextPage()}
          >
            <RefreshCw className="size-4" />
            다시 시도
          </Button>
        </>
      ) : query.hasNextPage ? (
        "아래로 스크롤하면 다음 요청을 불러옵니다."
      ) : (
        `요청 ${formatPermissionCount(rows.length)}건을 모두 불러왔습니다.`
      )}
    </div>
  ) : null

  const handleBulkApprove = async () => {
    if (selectedCount === 0 || isBulkApproving) return
    setBulkError("")
    try {
      await onBulkApprove([...selectedRequestIds])
      setSelectedRequestIds(new Set())
      setIsBulkDialogOpen(false)
    } catch (error) {
      setBulkError(
        getPermissionMutationErrorMessage(
          error,
          "선택한 권한 요청을 일괄 승인하지 못했습니다.",
        ),
      )
    }
  }

  return (
    <>
      <Card className="grid h-full min-h-0 min-w-0 grid-rows-[min-content_minmax(0,1fr)] gap-0 overflow-hidden py-0">
        <CardHeader className="grid-rows-[auto] content-start border-b px-4 py-3 pb-3!">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <CardTitle className="text-base">승인 대기 요청</CardTitle>
              <CardDescription>
                {scopeLabel} · {formatPermissionCount(query.data?.pagination?.total)}건
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setBulkError("")
                  setIsBulkDialogOpen(true)
                }}
                disabled={selectedCount === 0 || isMutating || query.isFetching}
              >
                <CheckCheck className="size-4" />
                선택 {formatPermissionCount(selectedCount)}건 승인
              </Button>
              <Select
                value={scope}
                onValueChange={onScopeChange}
                disabled={isMutating || query.isFetching}
              >
                <SelectTrigger className="w-52" aria-label="승인 대기 권한 범위">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {scopeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label} ({formatPermissionCount(option.count)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid min-h-0 min-w-0 grid-rows-[minmax(0,1fr)] p-0">
          <AccessUsersTable
            rows={rows}
            isLoading={query.isPending}
            isFetching={query.isFetching && !query.isFetchingNextPage}
            error={query.isError && !query.data ? query.error : null}
            onDecision={onDecision}
            isMutating={isMutating}
            onRetry={query.refetch}
            onLoadMore={handleLoadMore}
            scrollFooter={scrollFooter}
            selectedRequestIds={selectedRequestIds}
            onToggleRequest={handleToggleRequest}
            onToggleLoaded={handleToggleLoaded}
          />
        </CardContent>
      </Card>

      <Dialog
        open={isBulkDialogOpen}
        onOpenChange={(open) => {
          if (isBulkApproving) return
          setIsBulkDialogOpen(open)
          if (!open) setBulkError("")
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>선택 요청 일괄 승인</DialogTitle>
            <DialogDescription>
              선택한 {formatPermissionCount(selectedCount)}건을 일반 사용자 권한으로 승인합니다.
              Portal과 앱·기능 요청은 각각 독립적으로 처리됩니다.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm">
            관리자 권한이 필요한 요청은 일괄 승인 후 개별적으로 역할을 변경해야 합니다.
          </div>
          {bulkError ? (
            <p className="text-sm text-destructive" role="alert">{bulkError}</p>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsBulkDialogOpen(false)}
              disabled={isBulkApproving}
            >
              취소
            </Button>
            <Button
              type="button"
              onClick={handleBulkApprove}
              disabled={selectedCount === 0 || isBulkApproving}
            >
              <CheckCheck className="size-4" />
              {isBulkApproving
                ? "승인 처리 중..."
                : `${formatPermissionCount(selectedCount)}건 승인`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
