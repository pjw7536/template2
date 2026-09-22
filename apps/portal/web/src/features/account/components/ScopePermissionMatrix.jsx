import { Ban, Database, RefreshCw, RotateCcw, Search, ShieldCheck, UserRound } from "lucide-react"
import { memo, useState } from "react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { isScopeAccessBypass } from "@/lib/access/scopeAccess"

const USER_COLOR_CLASSES = {
  dot: "bg-chart-2",
  text: "text-chart-2",
}

function getCellValue(access) {
  if (isScopeAccessBypass(access)) return "allowed"
  if (access?.explicitStatus === "pending") return "pending"
  if (access?.explicitStatus === "denied") return "denied"
  if (access?.explicitStatus === "allowed") return "allowed"
  return "inherit"
}

function getEffectiveLabel(access) {
  if (access?.allowed) return "접근 가능"
  return "접근 불가"
}

function getAccessMeta(access) {
  if (isScopeAccessBypass(access)) return "슈퍼유저"
  if (access?.source === "portal_access_required") return "Portal 차단"
  if (access?.source === "scope_inactive") return "권한 범위 비활성"
  if (access?.source === "scope_not_found") return "권한 범위 없음"
  if (access?.explicitStatus === "pending") return "승인 대기"
  if (access?.explicitStatus === "denied") return "수동 차단"
  if (access?.explicitStatus === "allowed") return "수동 부여"
  if (access?.source === "policy_department") return "부서 자동 규칙"
  return "자동 규칙 없음"
}

function getPermissionSummaryLabel(access) {
  if (access?.allowed) return access?.role === "admin" ? "관리자" : "일반 사용자"
  if (access?.explicitStatus === "pending") return "승인 요청"
  if (access?.explicitStatus === "denied") return "접근 차단"
  return "권한 없음"
}

function getAccessDescription(access) {
  if (isScopeAccessBypass(access)) return "슈퍼유저 기본 권한으로 접근할 수 있습니다."
  if (access?.source === "portal_access_required") {
    return "Portal 접근이 차단되어 이 권한도 사용할 수 없습니다."
  }
  if (access?.source === "scope_inactive") return "현재 비활성화된 권한입니다."
  if (access?.source === "scope_not_found") return "등록되지 않은 권한입니다."
  if (access?.explicitStatus === "pending") return "관리자 승인을 기다리는 요청입니다."
  if (access?.explicitStatus === "denied") return "관리자가 직접 접근을 차단했습니다."
  if (access?.explicitStatus === "allowed") return "관리자가 직접 부여한 권한입니다."
  if (access?.source === "policy_department") return "부서 자동 규칙으로 부여된 권한입니다."
  return "자동 규칙이나 직접 부여된 권한이 없습니다."
}

function AccessStatusDetails({ access, scope }) {
  const effectiveLabel = getEffectiveLabel(access)
  const permissionLabel = getPermissionSummaryLabel(access)
  const description = getAccessDescription(access)

  return (
    <div className="grid w-full gap-3 text-xs text-popover-foreground">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-foreground" title={scope.name}>{scope.name}</div>
      </div>
      <div className="grid gap-2 rounded-md border bg-muted/30 p-3">
        <div className="flex items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 text-sm font-semibold">
            <span
              aria-hidden="true"
              className={`size-2 rounded-full ${access?.allowed ? USER_COLOR_CLASSES.dot : "bg-muted-foreground"}`}
            />
            {effectiveLabel}
          </span>
          <Badge variant="outline" className="h-5 shrink-0 px-1.5 text-[10px]">
            {permissionLabel}
          </Badge>
        </div>
        <p className="leading-5 text-muted-foreground">{description}</p>
        {scope.dataScopeType === "affiliation" ? (
          <p className="leading-5 text-muted-foreground">
            데이터 범위: {access?.dataScopeMode === "all" ? "모든 활성 소속" : "현재 소속 + 선택 소속"}
          </p>
        ) : null}
      </div>
    </div>
  )
}

const PERMISSION_CHOICE_CLASS =
  "justify-center gap-1.5 px-2 py-2 pl-2 text-xs data-[state=checked]:bg-accent data-[state=checked]:font-medium [&>span]:hidden"

const ScopePermissionCell = memo(function ScopePermissionCell({
  user,
  scope,
  access,
  isPending,
  isMutating,
  onChange,
  onApplyAllAccess,
  onDataScopeChange,
  isApplyingAll,
}) {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [draftValue, setDraftValue] = useState(null)
  const [applyToAll, setApplyToAll] = useState(false)
  const hasSuperuserBypass = isScopeAccessBypass(access)
  const isScopeUnavailable = ["scope_inactive", "scope_not_found"].includes(access?.source)
  const visibleLabel = getEffectiveLabel(access)
  const accessSummaryLabel = `${visibleLabel}, ${getPermissionSummaryLabel(access)}, ${getAccessMeta(access)}`
  const isDisabled =
    hasSuperuserBypass
    || isScopeUnavailable
    || isPending
    || isMutating
    || isApplyingAll
  const cellValue = getCellValue(access)
  const currentValue = cellValue === "allowed"
    ? access?.role === "admin" ? "admin" : "user"
    : cellValue
  const editableValue = currentValue === "pending" ? "user" : currentValue
  const selectedValue = draftValue ?? editableValue
  const statusState = access?.allowed
    ? access?.role === "admin" ? "admin" : "user"
    : "blocked"
  const statusDotClass = {
    admin: `${USER_COLOR_CLASSES.dot} shadow-sm`,
    user: `${USER_COLOR_CLASSES.dot} shadow-sm`,
    blocked: "bg-muted-foreground shadow-sm dark:bg-muted",
  }[statusState]
  const manualOverrideBorderClass =
    ["allowed", "denied"].includes(access?.explicitStatus)
      && ["admin", "user", "blocked"].includes(statusState)
      ? "border-2 border-foreground/50 dark:border-foreground"
      : ""
  const handleMenuOpenChange = (open) => {
    setIsMenuOpen(open)
    setDraftValue(open ? editableValue : null)
    setApplyToAll(false)
  }
  const handleDraftValueChange = (nextValue) => {
    if (isDisabled) return
    setDraftValue(nextValue)
  }
  const handleApplyToAllChange = (checked) => {
    setApplyToAll(checked === true)
  }
  const handleApply = () => {
    if (isDisabled || (!applyToAll && selectedValue === currentValue)) return
    setIsMenuOpen(false)
    if (applyToAll) {
      onApplyAllAccess({ user, nextValue: selectedValue })
      return
    }
    onChange({ user, scope, access, nextValue: selectedValue })
  }

  return (
    <div className="flex w-16 min-w-16 max-w-16 items-center justify-center overflow-visible">
      <DropdownMenu open={isMenuOpen} onOpenChange={handleMenuOpenChange}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="relative inline-flex size-8 items-center justify-center rounded-md bg-background transition hover:bg-accent hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            aria-label={`${user.knoxId || user.sabun || user.id} ${scope.name} 권한, ${accessSummaryLabel}. 권한 상세 및 변경 메뉴 열기`}
          >
            {isPending || isApplyingAll ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <>
                <span
                  aria-hidden="true"
                  className={`block size-3.5 rounded-full transition ${statusDotClass} ${manualOverrideBorderClass}`}
                  data-state={statusState}
                />
                {statusState === "admin" ? (
                  <span
                    aria-hidden="true"
                    className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[8px] font-semibold leading-none tracking-tight text-muted-foreground"
                  >
                    ADMIN
                  </span>
                ) : cellValue === "pending" ? (
                  <span
                    aria-hidden="true"
                    className="absolute bottom-0 left-1/2 -translate-x-1/2 whitespace-nowrap text-[8px] font-semibold leading-none tracking-tight text-chart-3 dark:text-chart-1"
                  >
                    승인요청
                  </span>
                ) : null}
              </>
            )}
            <span className="sr-only">{visibleLabel}</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <div className="p-3">
            <AccessStatusDetails access={access} scope={scope} />
          </div>
          <DropdownMenuSeparator />
          {scope.dataScopeType === "affiliation" && onDataScopeChange ? (
            <>
              <div className="p-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    setIsMenuOpen(false)
                    onDataScopeChange({ user, scope, access })
                  }}
                  disabled={hasSuperuserBypass || isMutating}
                >
                  <Database className="size-3.5" />
                  소속 데이터 범위
                </Button>
              </div>
              <DropdownMenuSeparator />
            </>
          ) : null}
          {isDisabled ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              {isPending || isMutating ? "권한 변경을 처리하고 있습니다." : "이 권한은 여기서 변경할 수 없습니다."}
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3 px-3 py-1.5">
                <DropdownMenuLabel className="p-0 text-xs text-muted-foreground">
                  권한 변경
                </DropdownMenuLabel>
                {scope.scopeType === "portal" && onApplyAllAccess ? (
                  <div className="flex items-center gap-1.5">
                    <Checkbox
                      id={`scope-permission-apply-all-${user.id}`}
                      checked={applyToAll}
                      onCheckedChange={handleApplyToAllChange}
                    />
                    <Label
                      htmlFor={`scope-permission-apply-all-${user.id}`}
                      className="cursor-pointer whitespace-nowrap text-xs font-medium"
                    >
                      모든 앱·기능
                    </Label>
                  </div>
                ) : null}
              </div>
              <DropdownMenuRadioGroup
                value={selectedValue}
                onValueChange={handleDraftValueChange}
                className="grid grid-cols-3 gap-1 p-1"
              >
                <DropdownMenuRadioItem
                  value="inherit"
                  className={PERMISSION_CHOICE_CLASS}
                  onSelect={(event) => event.preventDefault()}
                >
                  <RotateCcw className="size-3.5" />
                  자동 규칙
                </DropdownMenuRadioItem>
                <DropdownMenuRadioItem
                  value="user"
                  className={`${PERMISSION_CHOICE_CLASS} ${USER_COLOR_CLASSES.text}`}
                  onSelect={(event) => event.preventDefault()}
                >
                  <UserRound className="size-3.5" />
                  일반
                </DropdownMenuRadioItem>
                <DropdownMenuRadioItem
                  value="admin"
                  className={PERMISSION_CHOICE_CLASS}
                  onSelect={(event) => event.preventDefault()}
                >
                  <ShieldCheck className="size-3.5" />
                  관리자
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
              <DropdownMenuSeparator />
              <DropdownMenuRadioGroup value={selectedValue} onValueChange={handleDraftValueChange}>
                <DropdownMenuRadioItem
                  value="denied"
                  className="mx-1 justify-center gap-1.5 px-2 py-2 pl-2 text-xs text-destructive focus:bg-destructive/10 focus:text-destructive data-[state=checked]:bg-destructive/10 data-[state=checked]:font-medium [&>span]:hidden"
                  onSelect={(event) => event.preventDefault()}
                >
                  <Ban className="size-3.5" />
                  접근 차단
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
              <DropdownMenuSeparator />
              <div className="p-1">
                <Button
                  type="button"
                  size="sm"
                  className="w-full"
                  onClick={handleApply}
                  disabled={!applyToAll && selectedValue === currentValue}
                >
                  권한 변경
                </Button>
              </div>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
})

const permissionColumnClass = "w-20 min-w-20 max-w-20"

export function ScopePermissionMatrix({
  query,
  filters,
  filterDraft,
  setFilterDraft,
  onApplyFilters,
  onResetFilters,
  onManualGrantOnlyChange,
  onAccessChange,
  onApplyAllAccess,
  onDataScopeChange,
  isApplyingAll,
  pendingCell,
}) {
  const scopes = query.data?.scopes || []
  const rows = query.data?.results || []
  const hasFilters = Boolean(filters.search || filters.department || filters.manualGrantOnly)
  const isBusy = query.isFetching
  const handleScroll = (event) => {
    if (!query.hasNextPage || query.isFetching || query.isFetchingNextPage) return
    const { scrollTop, scrollHeight, clientHeight } = event.target
    if (scrollHeight - scrollTop - clientHeight <= 96) {
      query.fetchNextPage()
    }
  }
  return (
    <Card className="grid h-full min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden py-0">
      <form
        className="grid gap-3 border-b p-4 md:grid-cols-[minmax(180px,240px)_minmax(180px,240px)_auto] md:items-end xl:px-4 xl:py-3"
        onSubmit={(event) => {
          event.preventDefault()
          onApplyFilters()
        }}
      >
        <div className="grid min-w-0 gap-1.5">
          <Label htmlFor="scope-permission-user-search">사용자 ID</Label>
          <Input
            id="scope-permission-user-search"
            className="w-full"
            value={filterDraft.search}
            onChange={(event) => setFilterDraft((current) => ({ ...current, search: event.target.value }))}
            placeholder="Knox ID, 사번, 이름"
          />
        </div>
        <div className="grid min-w-0 gap-1.5">
          <Label htmlFor="scope-permission-department-search">부서</Label>
          <Input
            id="scope-permission-department-search"
            className="w-full"
            value={filterDraft.department}
            onChange={(event) => setFilterDraft((current) => ({ ...current, department: event.target.value }))}
            placeholder="정확한 부서명"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex h-9 items-center gap-2 rounded-md border border-input px-3">
            <Checkbox
              id="scope-permission-manual-grant-only"
              checked={filterDraft.manualGrantOnly}
              onCheckedChange={(checked) => {
                onManualGrantOnlyChange(checked === true)
              }}
            />
            <Label
              htmlFor="scope-permission-manual-grant-only"
              className="cursor-pointer whitespace-nowrap text-xs font-normal"
            >
              수동 부여 있음
            </Label>
          </div>
          <Button type="submit" disabled={query.isFetching}>
            <Search className="size-4" />
            검색
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onResetFilters}
            disabled={
              query.isFetching
              || (
                !hasFilters
                && !filterDraft.search
                && !filterDraft.department
                && !filterDraft.manualGrantOnly
              )
            }
          >
            <RotateCcw className="size-4" />
            초기화
          </Button>
        </div>
      </form>

      <CardContent
        className="min-h-0 min-w-0 overflow-auto p-0"
        aria-busy={query.isFetching}
        onScrollCapture={handleScroll}
      >
        {query.isPending ? (
          <div className="grid gap-3 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={`scope-permission-matrix-${index}`} className="h-14 w-full" />
            ))}
          </div>
        ) : query.error && !rows.length ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6" role="alert">
            <p className="text-sm text-destructive">권한 매트릭스를 불러오지 못했습니다.</p>
            <Button type="button" size="sm" variant="outline" onClick={() => query.refetch()}>
              <RefreshCw className="size-4" />
              다시 시도
            </Button>
          </div>
        ) : !scopes.length ? (
          <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">
            표시할 권한 범위가 없습니다.
          </div>
        ) : !rows.length ? (
          <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">
            표시할 사용자가 없습니다.
          </div>
        ) : (
          <Table stickyHeader className="w-max min-w-full" aria-label="사용자별 접근 권한 매트릭스">
            <TableHeader>
              <TableRow className="h-12 bg-muted hover:bg-muted">
                <TableHead className="sticky left-0 z-40 w-44 min-w-44 max-w-44 bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_hsl(var(--border))]">
                  이름
                </TableHead>
                <TableHead className="sticky left-44 z-40 w-40 min-w-40 max-w-40 bg-muted px-2 text-center text-[11px] font-medium text-muted-foreground shadow-[inset_0_-1px_0_hsl(var(--border))]">
                  사용자 ID (Knox ID)
                </TableHead>
                <TableHead className="sticky left-84 z-40 w-40 min-w-40 max-w-40 border-r bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_hsl(var(--border))]">
                  부서
                </TableHead>
                {scopes.map((scope) => {
                  return (
                    <TableHead
                      key={scope.key}
                      className={`z-30 ${permissionColumnClass} bg-muted px-1 text-center align-middle shadow-[inset_0_-1px_0_hsl(var(--border))]`}
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span
                            className="mx-auto block max-w-16 truncate rounded-sm whitespace-nowrap text-xs font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            tabIndex={0}
                            aria-label={`${scope.name}, ${scope.key}`}
                            title={scope.name}
                          >
                            {scope.name}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top">{scope.key}</TooltipContent>
                      </Tooltip>
                    </TableHead>
                  )
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const name = row.user.displayName || "이름 없음"
                const knoxId = row.user.knoxId || "-"
                const department = row.user.department || "부서 없음"
                return (
                  <TableRow key={row.user.id} className="group h-12 hover:bg-muted/40">
                    <TableCell className="sticky left-0 z-20 w-44 min-w-44 max-w-44 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted">
                      <span className="flex min-w-0 items-center justify-center gap-1">
                        <span className="min-w-0 truncate text-sm font-medium" title={name}>{name}</span>
                        {row.user.isSuperuser ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Badge
                                variant="secondary"
                                className="h-5 shrink-0 px-1.5 text-[10px]"
                                aria-label="SuperUser"
                                tabIndex={0}
                              >
                                S
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent side="top">SuperUser</TooltipContent>
                          </Tooltip>
                        ) : null}
                      </span>
                    </TableCell>
                    <TableCell className="sticky left-44 z-20 w-40 min-w-40 max-w-40 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted">
                      <span className="block truncate text-sm" title={knoxId}>{knoxId}</span>
                    </TableCell>
                    <TableCell className="sticky left-84 z-20 w-40 min-w-40 max-w-40 overflow-hidden border-r bg-card px-2 py-2 text-center group-hover:bg-muted">
                      <span className="block truncate text-sm text-muted-foreground" title={department}>{department}</span>
                    </TableCell>
                    {scopes.map((scope) => {
                      const isPortal = scope.scopeType === "portal"
                      return (
                        <TableCell
                          key={scope.key}
                          className={isPortal ? `${permissionColumnClass} bg-muted/10 px-1 py-2 text-center dark:bg-background dark:group-hover:bg-muted/40` : `${permissionColumnClass} px-1 py-2 text-center dark:bg-background dark:group-hover:bg-muted/40`}
                        >
                          <ScopePermissionCell
                            user={row.user}
                            scope={scope}
                            access={row.accesses?.[scope.key]}
                            isPending={pendingCell === `${row.user.id}:${scope.key}`}
                            isMutating={isBusy}
                            onChange={onAccessChange}
                            onApplyAllAccess={isPortal ? onApplyAllAccess : undefined}
                            onDataScopeChange={onDataScopeChange}
                            isApplyingAll={isPortal && isApplyingAll}
                          />
                        </TableCell>
                      )
                    })}
                  </TableRow>
                )
              })}
              {query.isFetchingNextPage ? (
                <TableRow className="h-12 hover:bg-transparent">
                  <TableCell colSpan={scopes.length + 3} className="text-center text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-2">
                      <RefreshCw className="size-3.5 animate-spin" />
                      추가 사용자를 불러오는 중...
                    </span>
                  </TableCell>
                </TableRow>
              ) : null}
              {query.isFetchNextPageError ? (
                <TableRow className="h-12 hover:bg-transparent">
                  <TableCell colSpan={scopes.length + 3} className="text-center">
                    <Button type="button" size="sm" variant="ghost" onClick={() => query.fetchNextPage()}>
                      <RefreshCw className="size-3.5" />
                      추가 목록 다시 불러오기
                    </Button>
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
