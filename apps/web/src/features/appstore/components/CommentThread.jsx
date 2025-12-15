// src/features/appstore/components/CommentThread.jsx
import { useState } from "react"
import { Heart, MessageSquare, Send, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

function buildCommentTree(comments) {
  const nodesById = new Map()
  const roots = []

    ; (comments ?? []).forEach((comment) => {
      if (!comment?.id) return
      nodesById.set(comment.id, { ...comment, replies: [] })
    })

  nodesById.forEach((node) => {
    const parentId = node.parentCommentId
    const parent = parentId != null ? nodesById.get(parentId) : null
    if (parent) {
      parent.replies.push(node)
      return
    }
    roots.push(node)
  })

  const sortById = (a, b) => {
    if (a.id === b.id) return 0
    if (a.id == null) return -1
    if (b.id == null) return 1
    return a.id - b.id
  }

  const sortTree = (nodes) => {
    nodes.sort(sortById)
    nodes.forEach((node) => sortTree(node.replies))
  }

  sortTree(roots)
  return roots
}

function CommentItem({
  comment,
  depth,
  isUpdating,
  isDeleting,
  isAdding,
  onAdd,
  onToggleLike,
  isTogglingLike,
  togglingLikeId,
  onUpdate,
  onDelete,
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState(comment.content)
  const [isReplying, setIsReplying] = useState(false)
  const [replyDraft, setReplyDraft] = useState("")

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

  const startReply = () => {
    setReplyDraft("")
    setIsReplying(true)
  }

  const cancelReply = () => {
    setReplyDraft("")
    setIsReplying(false)
  }

  const submitReply = async () => {
    if (!replyDraft.trim()) return
    if (!onAdd) return
    try {
      await onAdd(replyDraft.trim(), comment.id)
      cancelReply()
    } catch {
      // 오류는 상위에서 처리
    }
  }

  return (
    <div className={cn("rounded-lg border p-3", depth > 0 ? "bg-muted/40" : "bg-card/50")}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex w-full justify-between gap-1">
          <div className="flex items-center gap-2 text-sm font-medium">
            <span>{comment.author?.name || "사용자"}</span>
            {comment.author?.knoxid ? (
              <span className="text-xs text-muted-foreground">({comment.author.knoxid})</span>
            ) : null}
          </div>
          <div className="text-[11px] text-muted-foreground self-end">{comment.createdAt}</div>

        </div>
        <div className="flex items-center gap-1">
          {onToggleLike ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1 px-2 text-xs"
              onClick={() => onToggleLike(comment.id)}
              disabled={isTogglingLike && togglingLikeId === comment.id}
              type="button"
            >
              <Heart className={cn("size-4", comment.liked && "fill-primary text-primary")} />
              {comment.likeCount ?? 0}
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={isReplying ? cancelReply : startReply}
            disabled={isAdding || isEditing}
            type="button"
          >
            {isReplying ? "닫기" : "답글"}
          </Button>
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

      {isReplying ? (
        <div className="mt-3 space-y-2 rounded-lg border bg-muted/40 p-3">
          <textarea
            value={replyDraft}
            onChange={(event) => setReplyDraft(event.target.value)}
            placeholder="답글을 입력하세요"
            className="min-h-[120px] w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          />
          <div className="flex justify-end gap-2">
            <Button
              size="sm"
              className="gap-1"
              onClick={submitReply}
              disabled={isAdding}
              type="button"
            >
              <Send className="size-4" />
              등록
            </Button>
            <Button variant="ghost" size="sm" onClick={cancelReply} type="button">
              취소
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export function CommentThread({
  comments,
  onAdd,
  onUpdate,
  onDelete,
  onToggleLike,
  isAdding,
  updatingCommentId,
  deletingCommentId,
  togglingLikeId,
  isTogglingLike,
}) {
  const [draft, setDraft] = useState("")
  const tree = buildCommentTree(comments)

  const renderNode = (commentNode, depth) => {
    return (
      <div
        key={commentNode.id}
        className={cn("grid gap-3", depth > 0 && "border-l border-border/60 pl-4")}
      >
        <CommentItem
          comment={commentNode}
          depth={depth}
          isUpdating={updatingCommentId === commentNode.id}
          isDeleting={deletingCommentId === commentNode.id}
          isAdding={isAdding}
          onAdd={onAdd}
          onUpdate={onUpdate}
          onDelete={onDelete}
          onToggleLike={onToggleLike}
          isTogglingLike={isTogglingLike}
          togglingLikeId={togglingLikeId}
        />

        {commentNode.replies?.length ? (
          <div className="grid gap-3">
            {commentNode.replies.map((child) => renderNode(child, depth + 1))}
          </div>
        ) : null}
      </div>
    )
  }

  const handleAdd = async () => {
    if (!draft.trim()) return
    if (!onAdd) return
    try {
      await onAdd(draft.trim(), null)
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
            <p className="text-xs text-muted-foreground">자유롭게 의견을 남겨주세요.</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-3">
          {tree?.length ? (
            tree.map((node) => renderNode(node, 0))
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
