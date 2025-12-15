// src/features/appstore/components/AppList.jsx
import { ArrowUpRight, Eye, Heart, MessageSquare } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

function StatBadge({ icon: Icon, value, label }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
      <Icon className="size-3" />
      <span className="font-medium text-foreground">{value}</span>
      {label && <span className="text-[10px] text-muted-foreground">{label}</span>}
    </div>
  )
}

export function AppList({
  apps,
  selectedAppId,
  onSelect,
  onOpenLink,
  onToggleLike: _onToggleLike,
  onEdit: _onEdit,
  onDelete: _onDelete,
  isLoading,
}) {
  if (isLoading) {
    return (
      <Card className="border bg-card shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">목록을 불러오는 중...</CardContent>
      </Card>
    )
  }

  if (!apps?.length) {
    return (
      <Card className="border bg-card shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">
          조건에 맞는 앱이 없습니다. 새로운 앱을 등록해 보세요.
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fit,280px)] gap-3">
      {apps.map((app) => {
        const isSelected = selectedAppId === app.id
        const coverSrc =
          app.screenshotUrl ||
          (Array.isArray(app.screenshotUrls) ? app.screenshotUrls[app.coverScreenshotIndex ?? 0] : "")

        return (
          <Card
            key={app.id}
            onClick={() => onSelect(app.id)}
            className={cn(
              "flex h-full min-h-[200px] cursor-pointer flex-col gap-0 py-3 overflow-hidden border bg-card shadow-sm transition hover:-translate-y-0.5 hover:shadow-md",
              isSelected && "border-primary/60 ring-1 ring-primary/30",
            )}
          >
            {/* ✅ 상단을 2컬럼(Grid)로 분리 */}
            {/* 예: 뱃지(선택) */}
            <div className="flex justify-start px-5 pb-2">
              <Badge variant="secondary" className="shrink-0 text-[11px]">
                {app.category || "기타"}
              </Badge>
            </div>
            <Separator className="bg-border" />
            <div className="grid grid-cols-[128px_1fr] gap-3 px-3 py-2">
              {/* 왼쪽: 스크린샷 */}
              <div className="relative h-28 w-32 overflow-hidden rounded-md bg-muted ring-1 ring-border">
                {coverSrc ? (
                  <img
                    src={coverSrc}
                    alt={`${app.name} 스크린샷`}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                    스크린샷 없음
                  </div>
                )}
              </div>

              {/* 오른쪽: 앱 이름 */}
              <CardHeader className="p-0">
                <div className="flex items-start justify-center gap-2">
                  <div className="min-w-0">
                    <CardTitle className="truncate text-lg leading-tight">{app.name}</CardTitle>
                    {/* 필요하면 한 줄 서브 텍스트/카테고리 */}
                    {/* <p className="mt-0.5 truncate text-xs text-muted-foreground">{app.category}</p> */}
                  </div>
                </div>
              </CardHeader>
            </div>

            <CardContent className="flex flex-1 flex-col gap-2 px-3 pb-3">
              <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                {app.description || "설명이 없습니다."}
              </p>

              <Separator className="bg-border" />

              <div className="mt-auto flex items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1">
                  <StatBadge icon={Eye} value={app.viewCount} />
                  <StatBadge icon={Heart} value={app.likeCount} />
                  <StatBadge icon={MessageSquare} value={app.commentCount ?? 0} />
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1 px-2 text-xs text-primary hover:bg-primary/10"
                  onClick={(event) => {
                    event.stopPropagation()
                    onOpenLink?.(app)
                  }}
                >
                  바로가기
                  <ArrowUpRight className="size-3" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
