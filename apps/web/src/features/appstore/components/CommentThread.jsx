// src/features/appstore/components/CommentThread.jsx
import { useState } from "react"
import { MessageSquare, Send, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

function CommentItem({
  comment,
  isUpdating,
  isDeleting,
  onUpdate,
  onDelete,
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState(comment.content)

  const startEdit = () => {
    setDraft(comment.content)
    setIsEditing(true)
  }

  const cancelEdit = () => {
    setIsEditing(false)
    setDraft(comment.content)
  }

  const submitEdit = async () => {
    if (!draft.trim()) return
    try {
      await onUpdate(comment.id, draft.trim())
      setIsEditing(false)
    } catch {
      // 오류는 상위에서 처리
    }
  }

  return (
    <div className="rounded-lg border bg-card/50 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-sm font-medium">
            <span>{comment.author?.name || "익명"}</span>
            {comment.author?.knoxid ? (
              <span className="text-xs text-muted-foreground">({comment.author.knoxid})</span>
            ) : null}
          </div>
          <div className="text-[11px] text-muted-foreground">{comment.createdAt}</div>
        </div>
        <div className="flex items-center gap-1">
          {comment.canEdit ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-xs"
              onClick={isEditing ? submitEdit : startEdit}
              disabled={isUpdating}
              type="button"
            >
              {isEditing ? "저장" : "수정"}
            </Button>
          ) : null}
          {isEditing ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-xs text-muted-foreground"
              onClick={cancelEdit}
              type="button"
            >
              취소
            </Button>
          ) : null}
          {comment.canDelete ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive"
              onClick={() => onDelete(comment.id)}
              disabled={isDeleting}
              type="button"
            >
              <Trash2 className="size-4" />
            </Button>
          ) : null}
        </div>
      </div>
      <Separator className="my-2 bg-border" />
      {isEditing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="min-h-[120px] w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={submitEdit}
              disabled={isUpdating}
              type="button"
            >
              저장
            </Button>
            <Button variant="ghost" size="sm" onClick={cancelEdit} type="button">
              취소
            </Button>
          </div>
        </div>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{comment.content}</p>
      )}
    </div>
  )
}

export function CommentThread({
  comments,
  onAdd,
  onUpdate,
  onDelete,
  isAdding,
  updatingCommentId,
  deletingCommentId,
}) {
  const [draft, setDraft] = useState("")

  const handleAdd = async () => {
    if (!draft.trim()) return
    try {
      await onAdd(draft.trim())
      setDraft("")
    } catch {
      // 오류는 상위에서 처리
    }
  }

  return (
    <Card className="border bg-card shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
            <MessageSquare className="size-4" />
          </div>
          <div>
            <CardTitle className="text-base">댓글</CardTitle>
            <p className="text-xs text-muted-foreground">피드백과 연락처 메모를 남겨주세요.</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-3">
          {comments?.length ? (
            comments.map((comment) => (
              <CommentItem
                key={comment.id}
                comment={comment}
                isUpdating={updatingCommentId === comment.id}
                isDeleting={deletingCommentId === comment.id}
                onUpdate={onUpdate}
                onDelete={onDelete}
              />
            ))
          ) : (
            <p className="text-sm text-muted-foreground">아직 댓글이 없습니다.</p>
          )}
        </div>

        <div className="rounded-lg border bg-muted/40 p-3">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="댓글을 입력하세요"
            className="min-h-[120px] w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          />
          <div className="mt-2 flex justify-end">
            <Button
              size="sm"
              className="gap-1"
              onClick={handleAdd}
              disabled={isAdding}
              type="button"
            >
              <Send className="size-4" />
              등록
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
