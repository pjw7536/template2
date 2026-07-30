import { useEffect, useMemo, useState } from "react"
import { Database, RefreshCw, Search } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import { Textarea } from "@/components/ui/textarea"

import {
  useAffiliation,
  useUpdateUserScopeData,
  useUserScopeData,
} from "../hooks/useAccountData"
import { getPermissionMutationErrorMessage } from "../utils/permissionDisplay"


export function DataScopeDialog({ selection, onOpenChange }) {
  const [mode, setMode] = useState("default")
  const [selectedIds, setSelectedIds] = useState([])
  const [reason, setReason] = useState("")
  const [search, setSearch] = useState("")
  const userId = selection?.user?.id
  const scopeKey = selection?.scope?.key
  const query = useUserScopeData({
    userId,
    scope: scopeKey,
    enabled: Boolean(selection),
  })
  const affiliationQuery = useAffiliation()
  const mutation = useUpdateUserScopeData()

  useEffect(() => {
    if (!query.data) return
    setMode(query.data.dataScopeMode || "default")
    setSelectedIds(
      (query.data.grants || [])
        .filter((grant) => grant.isActive && grant.source === "manual")
        .map((grant) => grant.affiliationId),
    )
    setReason("")
    setSearch("")
  }, [query.data])

  const options = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase()
    return (affiliationQuery.data?.affiliationOptions || []).filter((option) => {
      if (!normalizedSearch) return true
      return [
        option.department,
        option.line,
        option.user_sdwt_prod,
      ].some((value) => String(value || "").toLocaleLowerCase().includes(normalizedSearch))
    })
  }, [affiliationQuery.data?.affiliationOptions, search])

  if (!selection) return null

  const userLabel = selection.user.displayName || selection.user.knoxId || selection.user.id
  const isAll = mode === "all"
  const lockedIds = new Set(
    (query.data?.grants || [])
      .filter((grant) => grant.isActive && grant.source !== "manual")
      .map((grant) => grant.affiliationId),
  )
  const currentAffiliations = (query.data?.effective?.affiliations || []).filter(
    (affiliation) => affiliation.source === "current",
  )
  const preservedGrantCount = (query.data?.grants || []).filter(
    (grant) => grant.isActive,
  ).length
  const toggleAffiliation = (affiliationId, checked) => {
    setSelectedIds((current) => {
      if (checked) return [...new Set([...current, affiliationId])]
      return current.filter((id) => id !== affiliationId)
    })
  }
  const handleSubmit = async () => {
    if (mutation.isPending || !reason.trim()) return
    try {
      await mutation.mutateAsync({
        userId,
        scope: scopeKey,
        dataScopeMode: mode,
        affiliationIds: selectedIds,
        reason: reason.trim() || undefined,
      })
      toast.success("앱별 소속 데이터 범위를 변경했습니다.")
      onOpenChange(false)
    } catch (error) {
      toast.error(
        getPermissionMutationErrorMessage(
          error,
          "소속 데이터 범위를 변경하지 못했습니다.",
        ),
      )
    }
  }

  return (
    <Dialog
      open={Boolean(selection)}
      onOpenChange={(open) => {
        if (!mutation.isPending) onOpenChange(open)
      }}
    >
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database className="size-4" />
            소속 데이터 범위
          </DialogTitle>
          <DialogDescription>
            {userLabel} · {selection.scope.name}
          </DialogDescription>
        </DialogHeader>

        {query.isPending ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
            <RefreshCw className="size-4 animate-spin" />
            데이터 범위를 불러오는 중입니다.
          </div>
        ) : query.error ? (
          <div className="flex min-h-48 flex-col items-center justify-center gap-3" role="alert">
            <p className="text-sm text-destructive">데이터 범위를 불러오지 못했습니다.</p>
            <Button type="button" size="sm" variant="outline" onClick={() => query.refetch()}>
              다시 시도
            </Button>
          </div>
        ) : (
          <div className="grid min-h-0 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="data-scope-mode">범위 방식</Label>
              <Select value={mode} onValueChange={setMode} disabled={mutation.isPending}>
                <SelectTrigger id="data-scope-mode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">현재 소속 + 선택 소속</SelectItem>
                  <SelectItem
                    value="all"
                    disabled={selection.access?.explicitStatus !== "allowed"}
                  >
                    모든 활성 소속
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                앱 관리자 역할만으로 전체 소속이 열리지 않습니다. 전체 범위는 별도로 지정됩니다.
              </p>
            </div>

            {currentAffiliations.length ? (
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <p className="text-xs font-medium text-muted-foreground">자동 포함되는 현재 소속</p>
                <p className="mt-1 text-sm">
                  {currentAffiliations.map((affiliation) => affiliation.userSdwtProd).join(", ")}
                </p>
              </div>
            ) : null}

            {!selection.access?.allowed && preservedGrantCount > 0 ? (
              <div className="rounded-lg border bg-muted/30 px-3 py-2" role="status">
                <p className="text-sm font-medium">데이터 설정 보존 중</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  앱 접근권한이 없어 현재는 사용할 수 없습니다. 앱 권한을 다시 부여하면
                  보존된 소속 {preservedGrantCount}개가 다시 적용됩니다.
                </p>
              </div>
            ) : null}

            <div className="grid min-h-0 gap-2">
              <Label htmlFor="data-scope-search">추가 소속</Label>
              <div className="relative">
                <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="data-scope-search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="pl-9"
                  placeholder="부서, 라인, user_sdwt_prod 검색"
                  disabled={isAll || mutation.isPending}
                />
              </div>
              <div className="max-h-64 min-h-32 overflow-y-auto rounded-lg border">
                {affiliationQuery.isPending ? (
                  <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">
                    소속 목록을 불러오는 중입니다.
                  </div>
                ) : affiliationQuery.isError ? (
                  <div
                    className="flex min-h-32 flex-col items-center justify-center gap-3 px-4 text-center"
                    role="alert"
                  >
                    <p className="text-sm text-destructive">소속 목록을 불러오지 못했습니다.</p>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => affiliationQuery.refetch()}
                    >
                      다시 시도
                    </Button>
                  </div>
                ) : !options.length ? (
                  <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">
                    {search.trim() ? "검색 결과가 없습니다." : "등록된 활성 소속이 없습니다."}
                  </div>
                ) : (
                  options.map((option) => {
                    const checkboxId = `data-scope-affiliation-${option.id}`
                    return (
                      <label
                        key={option.id}
                        htmlFor={checkboxId}
                        className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-b-0 hover:bg-muted/50"
                      >
                        <Checkbox
                          id={checkboxId}
                          checked={selectedIds.includes(option.id) || lockedIds.has(option.id)}
                          onCheckedChange={(checked) => {
                            toggleAffiliation(option.id, checked === true)
                          }}
                          disabled={isAll || mutation.isPending || lockedIds.has(option.id)}
                        />
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium">
                            {option.user_sdwt_prod}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {option.department} / {option.line}
                            {lockedIds.has(option.id) ? " · 자동 부여" : ""}
                          </span>
                        </span>
                      </label>
                    )
                  })
                )}
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="data-scope-reason">
                변경 사유 (필수)
              </Label>
              <Textarea
                id="data-scope-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                maxLength={500}
                placeholder="권한 부여 목적과 기간을 입력하세요"
                disabled={mutation.isPending}
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            취소
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={
              query.isPending
              || query.isError
              || (!isAll && affiliationQuery.isError)
              || mutation.isPending
              || !reason.trim()
            }
          >
            {mutation.isPending ? <RefreshCw className="size-4 animate-spin" /> : null}
            {mutation.isPending ? "저장 중" : "저장"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
