import * as React from "react"
import { Button } from "components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { Check, XCircle } from "lucide-react"

import { buildToastOptions } from "../utils/toast"
import { makeCellKey } from "../utils/dataTableCellState"
import { composeComment, splitComment } from "../utils/commentUtils"
import { deriveFlagState } from "../utils/dataTableFlagState"

function showInstantInformSuccessToast() {
  toast.success("즉시 인폼 완료", {
    description: "코멘트와 상태가 업데이트되었습니다.",
    ...buildToastOptions({ intent: "success", duration: 2000 }),
  })
}

function showInstantInformErrorToast(message) {
  toast.error("즉시 인폼 실패", {
    description: message || "즉시 인폼 처리 중 오류가 발생했습니다.",
    icon: <XCircle className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "destructive", duration: 3000 }),
  })
}

function showAlreadyInformedToast() {
  toast.info("이미 Inform 되었습니다.", {
    ...buildToastOptions({ intent: "info", duration: 2400 }),
  })
}

function showQueuedInstantInformToast() {
  toast.info("Inform Queue에 등록되어 해제 불가 합니다 (1~2분 내 인폼 예정)", {
    ...buildToastOptions({ intent: "info", duration: 2400 }),
  })
}

export function InstantInformCell({
  meta,
  recordId,
  baseValue,
  rowOriginal,
  disabled = false,
  disabledReason = "이미 JIRA 전송됨 (즉시인폼 불가)",
}) {
  const { visibleText: baseVisibleText, suffixWithMarker } = splitComment(rowOriginal?.comment)

  const baseState = deriveFlagState(baseValue, 0)
  const sendJiraState = deriveFlagState(rowOriginal?.send_jira, 0)
  const isLocked = disabled || sendJiraState.isOn
  const draftValue = meta?.instantInformDrafts?.[recordId]
  const effectiveState = draftValue === undefined ? baseState : deriveFlagState(draftValue, baseState.numericValue)
  const { isOn, isError } = effectiveState
  const isChecked = isOn

  const [isDialogOpen, setIsDialogOpen] = React.useState(false)
  const [commentDraft, setCommentDraft] = React.useState(baseVisibleText)

  React.useEffect(() => {
    if (isDialogOpen) {
      setCommentDraft(baseVisibleText)
    }
  }, [baseVisibleText, isDialogOpen])

  const instantInformKey = makeCellKey(recordId, "instant_inform")
  const commentKey = makeCellKey(recordId, "comment")
  const needToSendKey = makeCellKey(recordId, "needtosend")
  const statusKey = makeCellKey(recordId, "status")

  const isSaving =
    Boolean(meta?.updatingCells?.[instantInformKey]) ||
    Boolean(meta?.updatingCells?.[commentKey]) ||
    Boolean(meta?.updatingCells?.[needToSendKey]) ||
    Boolean(meta?.updatingCells?.[statusKey])

  const errorMessage = meta?.updateErrors?.[instantInformKey] ?? meta?.updateErrors?.[commentKey]

  const resetDraftState = () => {
    meta?.removeInstantInformDraftValue?.(recordId)
    meta?.clearUpdateError?.(instantInformKey)
    meta?.clearUpdateError?.(commentKey)
  }

  const openDialog = () => {
    if (isSaving) return
    if (isChecked) {
      if (sendJiraState.isOn) {
        showAlreadyInformedToast()
        return
      }
      showQueuedInstantInformToast()
      return
    }
    if (isLocked) {
      toast.info(disabledReason, {
        ...buildToastOptions({ intent: "info", duration: 2400 }),
      })
      return
    }
    resetDraftState()
    setIsDialogOpen(true)
  }

  const handleConfirm = async () => {
    if (!recordId || typeof meta?.handleUpdate !== "function") return

    meta?.setInstantInformDraftValue?.(recordId, 1)
    meta?.clearUpdateError?.(instantInformKey)
    meta?.clearUpdateError?.(commentKey)

    const composedComment = composeComment(commentDraft ?? baseVisibleText, suffixWithMarker)
    const updates = {
      comment: composedComment,
      instant_inform: 1,
      needtosend: 1,
      status: "COMPLETE",
    }

    try {
      const ok = await meta.handleUpdate(recordId, updates)
      if (ok) {
        showInstantInformSuccessToast()
        setIsDialogOpen(false)
        return
      }

      const message = meta?.updateErrors?.[instantInformKey] ?? meta?.updateErrors?.[commentKey]
      showInstantInformErrorToast(message)
    } catch (error) {
      showInstantInformErrorToast(error?.message)
    } finally {
      meta?.removeInstantInformDraftValue?.(recordId)
    }
  }

  const handleDialogClose = (nextOpen) => {
    if (!nextOpen) {
      resetDraftState()
    }
    setIsDialogOpen(nextOpen)
  }

  const titleText = isLocked
    ? disabledReason
    : isError
      ? "즉시인폼 오류 상태"
      : isChecked
        ? "즉시인폼 등록 완료"
        : "즉시인폼 진행"

  return (
    <div className="inline-flex justify-center">
      <button
        type="button"
        onClick={openDialog}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            openDialog()
          }
        }}
        disabled={isSaving}
        role="switch"
        aria-checked={isChecked}
        aria-disabled={isLocked || isSaving}
        aria-label={titleText}
        title={titleText}
        className={cn(
          "inline-flex h-5 w-5 items-center justify-center rounded-full border text-muted-foreground transition-colors focus:outline-none ",
          isError
            ? "border-destructive/60 bg-destructive/10 text-destructive"
            : isChecked
              ? "bg-primary border-primary text-primary-foreground"
              : "border-border hover:border-primary hover:text-primary",
          !isLocked && !isSaving && "cursor-pointer",
          (isLocked || isSaving) && "cursor-not-allowed opacity-60"
        )}
      >
        {isError ? <XCircle className="h-3 w-3" strokeWidth={3} /> : null}
        {!isError && isChecked ? <Check className="h-3 w-3" strokeWidth={3} /> : null}
      </button>

      <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Inform Comment 수정
            </DialogTitle>
          </DialogHeader>

          <textarea
            value={commentDraft}
            disabled={isSaving}
            onChange={(e) => {
              setCommentDraft(e.target.value)
              meta?.clearUpdateError?.(instantInformKey)
              meta?.clearUpdateError?.(commentKey)
            }}
            className="min-h-[6rem] resize-y rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
            aria-label="즉시 인폼 코멘트"
            placeholder="코멘트를 입력해 주세요"
            autoFocus
          />

          {errorMessage ? <div className="text-xs text-destructive">{errorMessage}</div> : null}

          <DialogFooter className="flex items-start gap-2">
            <div className="flex flex-col mr-auto text-[11px] text-muted-foreground">
              <span>Enter: 저장  |  Shift+Enter: 줄바꿈</span>
              <span className="text-primary">ESOP종료 여부 상관 없이 즉시인폼 합니다. (1~2분 소요)</span>
            </div>

            <Button onClick={() => void handleConfirm()} disabled={isSaving}>
              Inform
            </Button>
            <Button variant="outline" onClick={() => handleDialogClose(false)} disabled={isSaving}>
              취소
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default InstantInformCell
