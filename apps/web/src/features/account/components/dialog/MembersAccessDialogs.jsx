import { Button } from "@/components/ui/button"
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

function RejectAffiliationDialog({ dialog }) {
  return (
    <Dialog open={Boolean(dialog.target)} onOpenChange={(open) => !open && dialog.onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>거절 사유 입력</DialogTitle>
          <DialogDescription>
            {dialog.target?.name
              ? `${dialog.target.name}님의 소속 변경 요청을 거절합니다.`
              : "소속 변경 요청을 거절합니다."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="affiliationRejectReason">거절 사유 (선택)</Label>
          <textarea
            id="affiliationRejectReason"
            value={dialog.reason}
            onChange={(event) => dialog.onReasonChange(event.target.value)}
            className="min-h-24 resize-y rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="사유를 입력하지 않아도 거절할 수 있습니다."
            maxLength={500}
          />
          <p className="text-xs text-muted-foreground">
            거절 사유는 신청자에게 그대로 표시됩니다.
          </p>
          {dialog.error ? (
            <p className="text-xs text-destructive">
              {dialog.error?.message || "거절 처리에 실패했습니다."}
            </p>
          ) : null}
        </div>
        <DialogFooter className="gap-2">
          <Button type="button" variant="outline" onClick={dialog.onClose} disabled={dialog.isPending}>
            취소
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={dialog.onConfirm}
            disabled={dialog.isPending}
          >
            거절 확정
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GrantAffiliationDialog({ dialog }) {
  return (
    <Dialog open={dialog.open} onOpenChange={dialog.onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>소속 접근 권한 추가</DialogTitle>
          <DialogDescription>
            {dialog.userSdwtProd} 데이터를 함께 사용할 사용자와 역할을 선택합니다.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="affiliationGrantSearch">사용자 검색</Label>
            <Input
              id="affiliationGrantSearch"
              value={dialog.search}
              onChange={(event) => dialog.onSearchChange(event.target.value)}
              placeholder="이름, Knox ID, 사번 검색"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="affiliationGrantUser">대상 사용자</Label>
            <Select
              value={dialog.userId}
              onValueChange={dialog.onUserIdChange}
              disabled={dialog.isCandidatesPending || dialog.candidates.length === 0}
            >
              <SelectTrigger id="affiliationGrantUser" className="w-full">
                <SelectValue
                  placeholder={dialog.isCandidatesPending ? "사용자 조회 중..." : "사용자를 선택하세요"}
                />
              </SelectTrigger>
              <SelectContent>
                {dialog.candidates.map((candidate) => (
                  <SelectItem key={candidate.userId} value={String(candidate.userId)}>
                    {candidate.displayName || candidate.username || candidate.knoxId || candidate.sabun}
                    {candidate.knoxId ? ` · ${candidate.knoxId}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!dialog.isCandidatesPending && dialog.candidates.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                추가할 수 있는 사용자가 없습니다. 검색어를 변경해 보세요.
              </p>
            ) : null}
          </div>
          <div className="grid gap-2">
            <Label htmlFor="affiliationGrantRole">소속 역할</Label>
            <Select value={dialog.role} onValueChange={dialog.onRoleChange}>
              <SelectTrigger id="affiliationGrantRole" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="viewer">조회 권한</SelectItem>
                <SelectItem value="member">일반 권한</SelectItem>
                <SelectItem value="manager">운영 권한</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              조회 권한은 읽기 전용이며, 삭제와 권한 관리는 운영 권한만 가능합니다.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="affiliationGrantReason">변경 사유 (필수)</Label>
            <Textarea
              id="affiliationGrantReason"
              value={dialog.reason}
              onChange={(event) => dialog.onReasonChange(event.target.value)}
              placeholder="권한을 추가하는 이유를 입력하세요"
              maxLength={500}
              disabled={dialog.isPending}
            />
          </div>
          {dialog.candidatesError || dialog.error ? (
            <p className="text-xs text-destructive">
              {dialog.candidatesError?.message
                || dialog.error?.message
                || "사용자 또는 권한 정보를 불러오지 못했습니다."}
            </p>
          ) : null}
        </div>
        <DialogFooter className="gap-2">
          <Button type="button" variant="outline" onClick={() => dialog.onOpenChange(false)} disabled={dialog.isPending}>
            취소
          </Button>
          <Button
            type="button"
            onClick={dialog.onConfirm}
            disabled={!dialog.userId || !dialog.reason.trim() || dialog.isPending}
          >
            {dialog.isPending ? "추가 중..." : "권한 추가"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RoleChangeDialog({ dialog }) {
  return (
    <Dialog open={Boolean(dialog.target)} onOpenChange={(open) => !open && dialog.onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>소속 역할 변경</DialogTitle>
          <DialogDescription>
            {dialog.target?.row?.name
              ? `${dialog.target.row.name}님의 소속 역할을 변경합니다.`
              : "선택한 사용자의 소속 역할을 변경합니다."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="affiliationRoleChangeReason">변경 사유 (필수)</Label>
          <Textarea
            id="affiliationRoleChangeReason"
            value={dialog.reason}
            onChange={(event) => dialog.onReasonChange(event.target.value)}
            placeholder="역할을 변경하는 이유를 입력하세요"
            maxLength={500}
            disabled={dialog.isPending}
          />
        </div>
        <DialogFooter className="gap-2">
          <Button type="button" variant="outline" onClick={dialog.onClose} disabled={dialog.isPending}>
            취소
          </Button>
          <Button
            type="button"
            onClick={dialog.onConfirm}
            disabled={!dialog.reason.trim() || dialog.isPending}
          >
            {dialog.isPending ? "변경 중..." : "역할 변경"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RevokeAffiliationDialog({ dialog }) {
  return (
    <Dialog open={Boolean(dialog.target)} onOpenChange={(open) => !open && dialog.onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>추가 소속 접근 회수</DialogTitle>
          <DialogDescription>
            {dialog.target?.name
              ? `${dialog.target.name}님의 ${dialog.userSdwtProd} 추가 접근 권한을 회수합니다.`
              : "선택한 사용자의 추가 소속 접근 권한을 회수합니다."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <p className="text-sm text-muted-foreground">
            현재 소속 자체는 변경되지 않으며, 마지막 운영 권한은 회수할 수 없습니다.
          </p>
          <div className="grid gap-2">
            <Label htmlFor="affiliationRevokeReason">변경 사유 (필수)</Label>
            <Textarea
              id="affiliationRevokeReason"
              value={dialog.reason}
              onChange={(event) => dialog.onReasonChange(event.target.value)}
              placeholder="권한을 회수하는 이유를 입력하세요"
              maxLength={500}
              disabled={dialog.isPending}
            />
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button type="button" variant="outline" onClick={dialog.onClose} disabled={dialog.isPending}>
            취소
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={dialog.onConfirm}
            disabled={!dialog.reason.trim() || dialog.isPending}
          >
            {dialog.isPending ? "회수 중..." : "권한 회수"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function MembersAccessDialogs({
  rejectDialog,
  grantDialog,
  roleChangeDialog,
  revokeDialog,
}) {
  return (
    <>
      <RejectAffiliationDialog dialog={rejectDialog} />
      <GrantAffiliationDialog dialog={grantDialog} />
      <RoleChangeDialog dialog={roleChangeDialog} />
      <RevokeAffiliationDialog dialog={revokeDialog} />
    </>
  )
}
