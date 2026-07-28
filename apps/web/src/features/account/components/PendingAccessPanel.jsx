import {
  Ban,
  Check,
  Eye,
  MoreHorizontal,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  UserPlus,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
  PERMISSION_PAGE_SIZE,
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
  pagination,
  onPageChange,
}) {
  const columns = [
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
      header: "최근 결정",
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
        headerClassName: "sticky right-0 z-20 min-w-44 bg-muted/30 text-right",
        cellClassName: "sticky right-0 z-10 min-w-44 bg-card text-right group-hover:bg-muted/40",
      },
    },
  ]
  const errorMessage = error?.message === "forbidden"
    ? "권한 관리 권한이 없습니다."
    : error
      ? "사용자 목록을 불러오지 못했습니다."
      : ""

  return (
    <AccountDataTable
      data={rows}
      columns={columns}
      getRowId={(row) => String(row.user.id)}
      isLoading={isLoading}
      isFetching={isFetching}
      error={errorMessage}
      emptyMessage="표시할 사용자가 없습니다."
      onRetry={onRetry}
      pagination={{
        page: pagination?.page || 1,
        pageSize: pagination?.pageSize || PERMISSION_PAGE_SIZE,
        total: pagination?.total || 0,
        totalPages: pagination?.totalPages || 1,
        onPageChange,
      }}
      className="h-full rounded-none border-0"
      tableClassName="min-w-[1100px]"
      ariaLabel="권한 범위별 접근 사용자 목록"
    />
  )
}

export function PendingAccessPanel({
  query,
  scope,
  scopeOptions,
  onScopeChange,
  onDecision,
  onPageChange,
  isMutating,
}) {
  const scopeLabel = scopeOptions.find((option) => option.value === scope)?.label || scope

  return (
    <Card className="grid min-w-0 grid-rows-[auto_auto] overflow-hidden py-0 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:gap-0">
      <CardHeader className="border-b px-4 py-3 xl:grid-rows-[auto] xl:content-start xl:pb-3!">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">승인 대기 요청</CardTitle>
            <CardDescription>
              {scopeLabel} · {formatPermissionCount(query.data?.pagination?.total)}건
            </CardDescription>
          </div>
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
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="grid min-w-0 grid-rows-[auto] p-0 xl:min-h-0 xl:grid-rows-[minmax(0,1fr)]">
        <AccessUsersTable
          rows={query.data?.results || []}
          isLoading={query.isPending}
          isFetching={query.isFetching}
          error={query.error}
          onDecision={onDecision}
          isMutating={isMutating}
          onRetry={query.refetch}
          pagination={query.data?.pagination}
          onPageChange={onPageChange}
        />
      </CardContent>
    </Card>
  )
}
