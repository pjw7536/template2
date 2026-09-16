import { useMemo, useRef, useState } from "react"
import { Plus, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { useBulkApplyAccessPolicyRules } from "../hooks/useAccountData"
import { getPermissionMutationErrorMessage } from "../utils/permissionDisplay"
import { PermissionErrorState } from "./PermissionPanelStates"


const INITIAL_POLICY_FORM = {
  value: "",
  isActive: true,
}

const DEFAULT_DEPARTMENT_COLUMN_WIDTH = 320
const MIN_DEPARTMENT_COLUMN_WIDTH = 240
const MAX_DEPARTMENT_COLUMN_WIDTH = 560
const DEPARTMENT_COLUMN_RESIZE_STEP = 16

function clampDepartmentColumnWidth(width) {
  return Math.min(
    MAX_DEPARTMENT_COLUMN_WIDTH,
    Math.max(MIN_DEPARTMENT_COLUMN_WIDTH, width),
  )
}

function buildPolicyRows(rules) {
  const rowsByDepartment = new Map()

  for (const rule of rules) {
    const value = rule?.value?.trim()
    if (!value || rule.ruleType !== "department") continue

    const normalizedValue = value.toLocaleLowerCase("ko-KR")
    const row = rowsByDepartment.get(normalizedValue) || {
      value,
      rulesByScope: {},
    }
    row.rulesByScope[rule.scope] = rule
    rowsByDepartment.set(normalizedValue, row)
  }

  return [...rowsByDepartment.values()].sort((left, right) =>
    left.value.localeCompare(right.value, "ko-KR"),
  )
}

function PolicyStateSwitch({
  department,
  scope,
  checked,
  disabled,
  isPending,
  onChange,
}) {
  const label = `${department} · ${scope.label} 자동 접근 규칙`

  return (
    <div className="flex min-h-9 items-center justify-center">
      {isPending ? (
        <RefreshCw className="size-4 animate-spin text-muted-foreground" aria-label={`${label} 변경 중`} />
      ) : (
        <Switch
          checked={checked}
          onCheckedChange={onChange}
          disabled={disabled}
          aria-label={`${label} ${checked ? "사용 중" : "사용 안 함"}`}
        />
      )}
    </div>
  )
}

export function AccessPolicyPanel({ query, scopeOptions }) {
  const bulkApplyMutation = useBulkApplyAccessPolicyRules()
  const [mutationError, setMutationError] = useState("")
  const [form, setForm] = useState(INITIAL_POLICY_FORM)
  const [departmentColumnWidth, setDepartmentColumnWidth] = useState(
    DEFAULT_DEPARTMENT_COLUMN_WIDTH,
  )
  const [isResizingDepartmentColumn, setIsResizingDepartmentColumn] = useState(false)
  const departmentResizeRef = useRef(null)
  const rows = useMemo(
    () => buildPolicyRows(query.data?.results || []),
    [query.data?.results],
  )
  const scopeKeys = useMemo(
    () => scopeOptions.map((scope) => scope.value),
    [scopeOptions],
  )
  const isMutating = bulkApplyMutation.isPending

  const handleDepartmentResizeStart = (event) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    departmentResizeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startWidth: departmentColumnWidth,
    }
    setIsResizingDepartmentColumn(true)
  }

  const handleDepartmentResizeMove = (event) => {
    const resizeState = departmentResizeRef.current
    if (!resizeState || resizeState.pointerId !== event.pointerId) return
    setDepartmentColumnWidth(
      clampDepartmentColumnWidth(
        resizeState.startWidth + event.clientX - resizeState.startX,
      ),
    )
  }

  const handleDepartmentResizeEnd = (event) => {
    const resizeState = departmentResizeRef.current
    if (!resizeState || resizeState.pointerId !== event.pointerId) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    departmentResizeRef.current = null
    setIsResizingDepartmentColumn(false)
  }

  const handleDepartmentResizeKeyDown = (event) => {
    let nextWidth = null
    if (event.key === "ArrowLeft") {
      nextWidth = departmentColumnWidth - DEPARTMENT_COLUMN_RESIZE_STEP
    } else if (event.key === "ArrowRight") {
      nextWidth = departmentColumnWidth + DEPARTMENT_COLUMN_RESIZE_STEP
    } else if (event.key === "Home") {
      nextWidth = MIN_DEPARTMENT_COLUMN_WIDTH
    } else if (event.key === "End") {
      nextWidth = MAX_DEPARTMENT_COLUMN_WIDTH
    }
    if (nextWidth === null) return
    event.preventDefault()
    setDepartmentColumnWidth(clampDepartmentColumnWidth(nextWidth))
  }

  const applyPolicyState = async ({ value, targetScopeKeys, isActive, successMessage }) => {
    if (isMutating || !targetScopeKeys.length) return false

    setMutationError("")
    try {
      const result = await bulkApplyMutation.mutateAsync({
        value,
        scopeKeys: targetScopeKeys,
        isActive,
      })
      const updated = Number(result?.summary?.updated) || 0
      toast.success(`${successMessage} (${updated}건 변경)`)
      return true
    } catch (error) {
      const message = getPermissionMutationErrorMessage(
        error,
        "자동 접근 규칙을 변경하지 못했습니다.",
      )
      setMutationError(message)
      toast.error(message)
      return false
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const value = form.value.trim()
    if (!value) {
      const message = "대상 부서를 입력해 주세요."
      setMutationError(message)
      toast.error(message)
      return
    }
    if (!scopeKeys.length) {
      const message = "적용할 권한 범위가 없습니다."
      setMutationError(message)
      toast.error(message)
      return
    }

    const applied = await applyPolicyState({
      value,
      targetScopeKeys: scopeKeys,
      isActive: form.isActive,
      successMessage: `${value} 부서 규칙을 전체 범위에 적용했습니다.`,
    })
    if (applied) setForm({ ...INITIAL_POLICY_FORM })
  }

  return (
    <Card className="h-full min-h-0 min-w-0 overflow-hidden py-0">
      <CardContent className="grid h-full min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] gap-4 p-4">
        <form
          className="grid gap-3 border-b pb-4 md:grid-cols-[minmax(12rem,20rem)_9rem_auto] md:items-end"
          onSubmit={handleSubmit}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="access-policy-value">대상 부서</Label>
            <Input
              id="access-policy-value"
              value={form.value}
              onChange={(event) => setForm((current) => ({ ...current, value: event.target.value }))}
              placeholder="부서명"
              maxLength={150}
              required
              disabled={isMutating}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="access-policy-active">초기 상태</Label>
            <div className="flex h-9 items-center gap-2">
              <Switch
                id="access-policy-active"
                checked={form.isActive}
                onCheckedChange={(checked) => setForm((current) => ({ ...current, isActive: checked }))}
                disabled={isMutating}
              />
              <span className="text-sm text-muted-foreground">
                {form.isActive ? "사용 중" : "사용 안 함"}
              </span>
            </div>
          </div>
          <Button
            type="submit"
            className="justify-self-start whitespace-nowrap"
            disabled={isMutating || query.isPending || query.isError || !scopeKeys.length}
          >
            {isMutating ? <RefreshCw className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {isMutating ? "적용 중" : "전체 범위에 적용"}
          </Button>
          {mutationError ? (
            <p className="text-sm text-destructive md:col-span-3" role="alert">
              {mutationError}
            </p>
          ) : null}
        </form>

        {query.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : query.error ? (
          <PermissionErrorState error={query.error} onRetry={query.refetch} />
        ) : !rows.length ? (
          <div className="flex min-h-40 items-center justify-center rounded-md border p-4 text-sm text-muted-foreground">
            등록된 자동 접근 규칙이 없습니다. 부서를 입력해 전체 범위에 적용해 주세요.
          </div>
        ) : (
          <div className="min-h-0 min-w-0 overflow-auto rounded-md border">
            <Table
              stickyHeader
              className="w-max min-w-full"
              style={{
                "--policy-department-column-width": `${departmentColumnWidth}px`,
              }}
              aria-label="부서별 자동 접근 규칙 매트릭스"
            >
              <TableHeader>
                <TableRow className="h-12 bg-muted hover:bg-muted">
                  <TableHead className="sticky left-0 z-40 w-[var(--policy-department-column-width)] min-w-[var(--policy-department-column-width)] max-w-[var(--policy-department-column-width)] border-r bg-muted px-3 text-left">
                    대상 부서
                    <span
                      className={`group absolute -right-1.5 top-0 z-50 h-full w-3 cursor-col-resize touch-none select-none outline-none focus-visible:ring-2 focus-visible:ring-ring ${isResizingDepartmentColumn ? "bg-primary/10" : ""}`}
                      role="separator"
                      aria-label="대상 부서 열 너비 조절"
                      aria-orientation="vertical"
                      aria-valuemin={MIN_DEPARTMENT_COLUMN_WIDTH}
                      aria-valuemax={MAX_DEPARTMENT_COLUMN_WIDTH}
                      aria-valuenow={departmentColumnWidth}
                      tabIndex={0}
                      title="드래그하여 너비 조절 · 더블클릭하여 초기화"
                      onPointerDown={handleDepartmentResizeStart}
                      onPointerMove={handleDepartmentResizeMove}
                      onPointerUp={handleDepartmentResizeEnd}
                      onPointerCancel={handleDepartmentResizeEnd}
                      onDoubleClick={() => setDepartmentColumnWidth(DEFAULT_DEPARTMENT_COLUMN_WIDTH)}
                      onKeyDown={handleDepartmentResizeKeyDown}
                    >
                      <span
                        className={`absolute inset-y-0 left-1/2 -translate-x-1/2 transition-colors ${isResizingDepartmentColumn ? "w-0.5 bg-primary" : "w-px bg-border group-hover:bg-primary/60"}`}
                        aria-hidden="true"
                      />
                    </span>
                  </TableHead>
                  <TableHead className="w-20 min-w-20 bg-muted px-2 text-center">전체</TableHead>
                  {scopeOptions.map((scope) => (
                    <TableHead
                      key={scope.value}
                      className="w-24 min-w-24 bg-muted px-2 text-center"
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span
                            className="mx-auto block max-w-20 truncate rounded-sm text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            tabIndex={0}
                          >
                            {scope.label}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top">{scope.label}</TooltipContent>
                      </Tooltip>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const activeCount = scopeOptions.filter(
                    (scope) => row.rulesByScope[scope.value]?.isActive,
                  ).length
                  const allActive = Boolean(scopeOptions.length) && activeCount === scopeOptions.length
                  const anyActive = activeCount > 0
                  const isRowPending =
                    isMutating
                    && bulkApplyMutation.variables?.value === row.value
                    && bulkApplyMutation.variables?.scopeKeys?.length === scopeKeys.length

                  return (
                    <TableRow key={row.value} className="group h-12 hover:bg-muted/40">
                      <TableCell className="sticky left-0 z-20 w-[var(--policy-department-column-width)] min-w-[var(--policy-department-column-width)] max-w-[var(--policy-department-column-width)] border-r bg-card px-3 group-hover:bg-muted">
                        <span className="block whitespace-normal break-words text-sm font-medium leading-5" title={row.value}>
                          {row.value}
                        </span>
                      </TableCell>
                      <TableCell className="px-2 text-center">
                        {isRowPending ? (
                          <RefreshCw className="mx-auto size-4 animate-spin text-muted-foreground" />
                        ) : (
                          <Checkbox
                            checked={allActive ? true : anyActive ? "indeterminate" : false}
                            onCheckedChange={() => {
                              const nextActive = !anyActive
                              applyPolicyState({
                                value: row.value,
                                targetScopeKeys: scopeKeys,
                                isActive: nextActive,
                                successMessage: `${row.value} 부서의 전체 규칙을 ${nextActive ? "사용" : "미사용"}으로 변경했습니다.`,
                              })
                            }}
                            disabled={isMutating}
                            aria-label={`${row.value} 전체 자동 접근 규칙 ${allActive ? "사용 중" : anyActive ? "일부 사용 중" : "사용 안 함"}`}
                          />
                        )}
                      </TableCell>
                      {scopeOptions.map((scope) => {
                        const rule = row.rulesByScope[scope.value]
                        const checked = Boolean(rule?.isActive)
                        const isCellPending =
                          isMutating
                          && bulkApplyMutation.variables?.value === row.value
                          && bulkApplyMutation.variables?.scopeKeys?.length === 1
                          && bulkApplyMutation.variables.scopeKeys[0] === scope.value

                        return (
                          <TableCell key={scope.value} className="px-2 text-center">
                            <PolicyStateSwitch
                              department={row.value}
                              scope={scope}
                              checked={checked}
                              disabled={isMutating}
                              isPending={isCellPending}
                              onChange={(nextActive) => {
                                applyPolicyState({
                                  value: row.value,
                                  targetScopeKeys: [scope.value],
                                  isActive: nextActive,
                                  successMessage: `${row.value} · ${scope.label} 규칙을 ${nextActive ? "사용" : "미사용"}으로 변경했습니다.`,
                                })
                              }}
                            />
                          </TableCell>
                        )
                      })}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
