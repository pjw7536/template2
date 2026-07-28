import { useState } from "react"
import { AlertTriangle, Plus, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"

import {
  useCreateAccessPolicyRule,
  useDeleteAccessPolicyRule,
  useUpdateAccessPolicyRule,
} from "../hooks/useAccountData"
import {
  formatPermissionCount,
  getPermissionMutationErrorMessage,
} from "../utils/permissionDisplay"
import { PermissionErrorState } from "./PermissionPanelStates"


const INITIAL_POLICY_FORM = {
  value: "",
  isActive: true,
}

function PolicyDeleteDialog({
  target,
  isSubmitting,
  onOpenChange,
  onConfirm,
  errorMessage,
}) {
  return (
    <Dialog
      open={Boolean(target)}
      onOpenChange={(nextOpen) => {
        if (!isSubmitting) onOpenChange(nextOpen)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-destructive/10 text-destructive">
              <AlertTriangle className="size-5" />
            </div>
            <div className="min-w-0">
              <DialogTitle>자동 접근 규칙 삭제</DialogTitle>
              <DialogDescription className="mt-1">
                {target ? `대상 부서: ${target.value || "-"}` : ""}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        {errorMessage ? (
          <p className="text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            취소
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isSubmitting}>
            {isSubmitting ? <RefreshCw className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            삭제
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function AccessPolicyPanel({ query, scope, scopeOptions, onScopeChange }) {
  const createMutation = useCreateAccessPolicyRule()
  const updateMutation = useUpdateAccessPolicyRule()
  const deleteMutation = useDeleteAccessPolicyRule()
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [mutationError, setMutationError] = useState("")
  const [form, setForm] = useState(INITIAL_POLICY_FORM)
  const rules = query.data?.results || []
  const isMutating = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending
  const scopeLabel = scopeOptions.find((option) => option.value === scope)?.label || scope

  const createPolicy = async (payload) => {
    if (isMutating) return
    setMutationError("")
    try {
      await createMutation.mutateAsync(payload)
      setForm({ ...INITIAL_POLICY_FORM })
      toast.success("자동 접근 규칙을 추가했습니다.")
    } catch (error) {
      const message = getPermissionMutationErrorMessage(error, "자동 접근 규칙을 추가하지 못했습니다.")
      setMutationError(message)
      toast.error(message)
    }
  }

  const updatePolicyActive = async (rule, checked) => {
    if (isMutating) return
    setMutationError("")
    try {
      await updateMutation.mutateAsync({ id: rule.id, isActive: checked })
      toast.success(checked ? "자동 접근 규칙을 사용합니다." : "자동 접근 규칙 사용을 중지했습니다.")
    } catch (error) {
      const message = getPermissionMutationErrorMessage(
        error,
        "자동 접근 규칙의 사용 여부를 변경하지 못했습니다.",
      )
      setMutationError(message)
      toast.error(message)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (isMutating) return

    const value = form.value.trim()
    if (!value) {
      const message = "대상 부서를 입력해 주세요."
      setMutationError(message)
      toast.error(message)
      return
    }

    await createPolicy({
      scope,
      ruleType: "department",
      value,
      isActive: form.isActive,
    })
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget || isMutating) return
    setMutationError("")
    try {
      await deleteMutation.mutateAsync({ id: deleteTarget.id })
      setDeleteTarget(null)
      toast.success("자동 접근 규칙을 삭제했습니다.")
    } catch (error) {
      const message = getPermissionMutationErrorMessage(error, "자동 접근 규칙을 삭제하지 못했습니다.")
      setMutationError(message)
      toast.error(message)
    }
  }

  return (
    <Card className="grid min-w-0 grid-rows-[auto_auto] overflow-hidden py-0 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:gap-0">
      <CardHeader className="border-b px-4 py-3 xl:grid-rows-[auto] xl:content-start xl:pb-3!">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">
              <span className="xl:hidden">자동 규칙</span>
              <span className="hidden xl:inline">자동 접근 규칙</span>
            </CardTitle>
            <CardDescription>{scopeLabel} · {formatPermissionCount(rules.length)}개 규칙</CardDescription>
          </div>
          <Select value={scope} onValueChange={onScopeChange} disabled={isMutating}>
            <SelectTrigger className="w-52" aria-label="자동 접근 규칙 권한 범위">
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
      <CardContent className="grid min-w-0 grid-rows-[auto_auto] gap-4 p-4 xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)]">
        <form
          className="grid gap-3 border-b pb-4 xl:grid-cols-[11rem_11rem_8rem_auto] xl:items-end xl:justify-start"
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
            <Label>적용 결과</Label>
            <div className="flex h-9 items-center rounded-md border bg-muted/40 px-3 text-sm">
              일반 사용자로 접근 허용
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="access-policy-active">사용 여부</Label>
            <div className="flex h-9 items-center gap-2">
              <Switch
                id="access-policy-active"
                checked={form.isActive}
                onCheckedChange={(checked) => setForm((current) => ({ ...current, isActive: checked }))}
                aria-label="자동 접근 규칙 사용"
                disabled={isMutating}
              />
              <span className="text-sm text-muted-foreground">{form.isActive ? "사용" : "사용 안 함"}</span>
            </div>
          </div>
          <Button
            type="submit"
            className="self-end justify-self-start whitespace-nowrap"
            disabled={isMutating || query.isPending || query.isError}
          >
            {createMutation.isPending ? <RefreshCw className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {createMutation.isPending ? "추가 중" : "규칙 추가"}
          </Button>
          {mutationError ? (
            <p className="text-sm text-destructive xl:col-span-4" role="alert">
              {mutationError}
            </p>
          ) : null}
        </form>

        {query.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : query.error ? (
          <PermissionErrorState error={query.error} onRetry={query.refetch} />
        ) : !rules.length ? (
          <div className="rounded-md border p-4 text-sm text-muted-foreground">
            등록된 자동 접근 규칙이 없습니다.
          </div>
        ) : (
          <div className="min-w-0 overflow-x-auto rounded-md border xl:min-h-0 xl:overflow-auto">
            <Table stickyHeader>
              <TableHeader>
                <TableRow>
                  <TableHead>대상 부서</TableHead>
                  <TableHead>적용 결과</TableHead>
                  <TableHead>사용 여부</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => {
                  const isUpdating = updateMutation.isPending && updateMutation.variables?.id === rule.id
                  return (
                    <TableRow key={rule.id}>
                      <TableCell className="max-w-lg truncate">{rule.value || "-"}</TableCell>
                      <TableCell>일반 사용자로 접근 허용</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={Boolean(rule.isActive)}
                            onCheckedChange={(checked) => updatePolicyActive(rule, checked)}
                            aria-label={`${rule.value || "부서"} 규칙 사용`}
                            disabled={isMutating}
                          />
                          <Badge variant={rule.isActive ? "secondary" : "outline"}>
                            {isUpdating ? "변경 중" : rule.isActive ? "사용 중" : "사용 안 함"}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => {
                            setMutationError("")
                            setDeleteTarget(rule)
                          }}
                          disabled={isMutating}
                        >
                          <Trash2 className="size-4" />
                          삭제
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      <PolicyDeleteDialog
        target={deleteTarget}
        isSubmitting={deleteMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onConfirm={handleDeleteConfirm}
        errorMessage={mutationError}
      />
    </Card>
  )
}
