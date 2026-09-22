import { useEffect, useState } from "react"
import {
  Ban,
  Check,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  UserPlus,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

import { ACCESS_ACTION_LABELS, ACCESS_ROLE_OPTIONS } from "../utils/permissionDisplay"


export function PermissionDecisionDialog({
  decision,
  onOpenChange,
  onSubmit,
  isSubmitting,
  errorMessage,
}) {
  const [role, setRole] = useState("user")
  const [reason, setReason] = useState("")
  const [approveAllApps, setApproveAllApps] = useState(false)

  useEffect(() => {
    setRole(decision?.role || "user")
    setReason("")
    setApproveAllApps(false)
  }, [decision])

  if (!decision) return null

  const requiresRole = ["approve", "grant", "change_role"].includes(decision.action)
  const requiresReason = [
    "grant",
    "revoke",
    "reset_to_policy",
    "change_role",
    "apply_all",
  ].includes(decision.action)
  const showsReason = requiresReason || decision.action === "reject"
  const actionLabel = decision.label || ACCESS_ACTION_LABELS[decision.action] || decision.action
  const ActionIcon = {
    approve: Check,
    reject: Ban,
    grant: UserPlus,
    revoke: Ban,
    reset_to_policy: RotateCcw,
    change_role: SlidersHorizontal,
    apply_all: ShieldCheck,
  }[decision.action] || Save

  const handleSubmit = async () => {
    if (isSubmitting || (requiresReason && !reason.trim())) return
    await onSubmit({
      userId: decision.row.user.id,
      scope: decision.scope?.key || "portal",
      action: decision.action,
      role: requiresRole ? role : undefined,
      reason: requiresReason || reason.trim() ? reason.trim() : undefined,
      approveAllApps: decision.action === "approve" && !decision.scope
        ? approveAllApps
        : undefined,
    })
  }

  return (
    <Dialog
      open={Boolean(decision)}
      onOpenChange={(open) => {
        if (!isSubmitting) onOpenChange(open)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{actionLabel}</DialogTitle>
          <DialogDescription>
            <span>{decision.row.user.displayName || decision.row.user.knoxId}</span>
            {decision.scope ? (
              <span className="mt-1 block">권한 범위: {decision.scope.name}</span>
            ) : null}
            {decision.action === "reset_to_policy" ? (
              <span className="mt-1 hidden xl:block">
                직접 지정한 상태를 제거하고 자동 접근 규칙의 판정으로 전환합니다.
              </span>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          {requiresRole ? (
            <div className="grid gap-2">
              <Label htmlFor="access-role">접근 역할</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger id="access-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACCESS_ROLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
          {decision.action === "approve" && !decision.scope ? (
            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <Label htmlFor="approve-all-apps">활성 앱 함께 허용</Label>
                <p className="mt-1 text-xs text-muted-foreground">
                  기존 차단은 유지하고 미설정·대기 앱만 일반 사용자로 허용합니다.
                </p>
              </div>
              <Switch
                id="approve-all-apps"
                checked={approveAllApps}
                onCheckedChange={setApproveAllApps}
                disabled={isSubmitting}
              />
            </div>
          ) : null}
          {decision.description ? (
            <p className="text-sm text-muted-foreground">
              {decision.description}
            </p>
          ) : null}
          {showsReason ? (
            <div className="grid gap-2">
              <Label htmlFor="access-reason">
                사유 ({requiresReason ? "필수" : "선택"})
              </Label>
              <Textarea
                id="access-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="사유를 입력하세요"
                maxLength={500}
                disabled={isSubmitting}
              />
            </div>
          ) : null}
          {errorMessage ? (
            <p className="text-sm text-destructive" role="alert">
              {errorMessage}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            취소
          </Button>
          <Button
            variant={["reject", "revoke"].includes(decision.action) ? "destructive" : "default"}
            onClick={handleSubmit}
            disabled={isSubmitting || (requiresReason && !reason.trim())}
          >
            {isSubmitting ? (
              <RefreshCw className="size-4 animate-spin" />
            ) : (
              <>
                <Save className="size-4 xl:hidden" />
                <ActionIcon className="hidden size-4 xl:block" />
              </>
            )}
            {isSubmitting ? (
              <>
                <span className="xl:hidden">저장 중</span>
                <span className="hidden xl:inline">처리 중</span>
              </>
            ) : (
              <>
                <span className="xl:hidden">저장</span>
                <span className="hidden xl:inline">{actionLabel}</span>
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
