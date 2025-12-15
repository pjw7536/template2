// src/features/appstore/components/AppDetail.jsx
import {
  ArrowUpRight,
  BadgeCheck,
  Eye,
  Heart,
  Link as LinkIcon,
  MessageSquare,
  Shield,
  User,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

import { CommentThread } from "./CommentThread"

const KST_TIME_ZONE = "Asia/Seoul"
const commentTimePartsFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: KST_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

function formatCommentTimeToKst(value) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const parts = commentTimePartsFormatter.formatToParts(date).reduce((acc, part) => {
    if (part.type in acc) return acc
    acc[part.type] = part.value
    return acc
  }, {})
  return `${parts.year ?? "0000"}-${parts.month ?? "00"}-${parts.day ?? "00"} ${parts.hour ?? "00"}:${parts.minute ?? "00"}`
}

function InfoRow({ icon: Icon, label, value, muted }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-muted/40 px-3 py-2">
      <Icon className="mt-0.5 size-4 text-muted-foreground" />
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn("text-sm", muted && "text-muted-foreground")}>{value || "미입력"}</span>
      </div>
    </div>
  )
}

function StatPill({ icon: Icon, value, label }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border px-3 py-2">
      <Icon className="size-4 text-muted-foreground" />
      <div className="flex flex-col leading-tight">
        <span className="text-sm font-semibold">{value}</span>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
    </div>
  )
}

export function AppDetail({
  app,
  isLoading,
  onOpenLink,
  onToggleLike,
  onEdit,
  onDelete,
  onAddComment,
  onUpdateComment,
  onDeleteComment,
  onToggleCommentLike,
  isLiking,
  isAddingComment,
  updatingCommentId,
  deletingCommentId,
  togglingCommentLikeId,
  isTogglingCommentLike,
}) {
  if (isLoading) {
    return (
      <Card className="border bg-card shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">선택한 앱 정보를 불러오는 중...</CardContent>
      </Card>
    )
  }

  if (!app) {
    return (
      <Card className="border bg-card shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">
          왼쪽 목록에서 앱을 선택하거나 새로 등록해 보세요.
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="border bg-card shadow-sm">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-lg font-semibold text-primary ring-1 ring-primary/20">
                {app.name?.charAt(0) || "A"}
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-xl">{app.name}</CardTitle>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant="outline" className="rounded-full bg-background/70 px-2 py-0">
                    {app.category || "기타"}
                  </Badge>
                  {app.owner ? (
                    <Badge variant="outline" className="rounded-full bg-background/70 px-2 py-0">
                      등록자: {app.owner.name}
                    </Badge>
                  ) : null}
                  <Badge variant="outline" className="rounded-full bg-background/70 px-2 py-0">
                    댓글 {app.commentCount ?? 0}
                  </Badge>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                className="gap-1"
                onClick={() => onOpenLink?.(app)}
                type="button"
              >
                <LinkIcon className="size-4" />
                링크 열기
              </Button>
              <Button
                variant={app.liked ? "secondary" : "outline"}
                className="gap-1"
                onClick={() => onToggleLike?.(app)}
                disabled={isLiking}
                type="button"
              >
                <Heart className={cn("size-4", app.liked && "fill-primary text-primary")} />
                {app.liked ? "좋아요 취소" : "좋아요"}
              </Button>
              {app.canEdit ? (
                <Button variant="outline" className="gap-1" onClick={() => onEdit?.(app)} type="button">
                  <BadgeCheck className="size-4" />
                  수정
                </Button>
              ) : null}
              {app.canDelete ? (
                <Button
                  variant="destructive"
                  className="gap-1"
                  onClick={() => onDelete?.(app)}
                  type="button"
                >
                  삭제
                </Button>
              ) : null}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <InfoRow icon={User} label="담당자 이름" value={app.contactName} />
            <InfoRow icon={Shield} label="담당자 Knox ID" value={app.contactKnoxid} />
            <InfoRow icon={ArrowUpRight} label="접속 URL" value={app.url} muted />
          </div>
          <Separator className="bg-border" />
          <CardDescription className="text-sm leading-relaxed text-foreground">
            {app.description || "설명이 없습니다."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid h-56 place-items-center overflow-hidden rounded-xl border bg-muted sm:h-64 md:h-72">
            {app.screenshotUrl ? (
              <img
                src={app.screenshotUrl}
                alt={`${app.name} 스크린샷`}
                className="h-full w-full object-contain"
                loading="lazy"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                등록된 스크린샷이 없습니다.
              </div>
            )}
          </div>

          <Separator className="bg-border" />

          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            <StatPill icon={Eye} value={app.viewCount} label="조회수" />
            <StatPill icon={Heart} value={app.likeCount} label="좋아요" />
            <StatPill icon={MessageSquare} value={app.commentCount ?? 0} label="댓글" />
            <StatPill icon={BadgeCheck} value={app.badge || "-"} label="Badge" />
          </div>
        </CardContent>
      </Card>

      <CommentThread
        comments={(app.comments ?? []).map((comment) => ({
          ...comment,
          createdAt: formatCommentTimeToKst(comment.createdAt) || comment.createdAt,
        }))}
        onAdd={(content, parentCommentId) => onAddComment?.(app.id, content, parentCommentId)}
        onUpdate={(commentId, content) => onUpdateComment?.(app.id, commentId, content)}
        onDelete={(commentId) => onDeleteComment?.(app.id, commentId)}
        onToggleLike={(commentId) => onToggleCommentLike?.(app.id, commentId)}
        isAdding={isAddingComment}
        updatingCommentId={updatingCommentId}
        deletingCommentId={deletingCommentId}
        togglingLikeId={togglingCommentLikeId}
        isTogglingLike={isTogglingCommentLike}
      />
    </div>
  )
}
