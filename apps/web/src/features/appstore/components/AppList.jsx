// 앱 목록 컴포넌트
import { useEffect, useRef, useState } from "react"
import { ArrowUpRight, Eye, GripVertical, Heart, MessageSquare } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { getCoverScreenshotUrl } from "../utils/appScreenshots"

const MotionCard = motion.create(Card)
const ORDER_LAYOUT_TRANSITION = {
  layout: { type: "spring", stiffness: 500, damping: 38, mass: 0.7 },
}

function StatBadge({ icon: Icon, value, label }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
      <Icon className="size-3" />
      <span className="font-medium text-foreground">{value}</span>
      {label && <span className="text-[10px] text-muted-foreground">{label}</span>}
    </div>
  )
}

function AppTitle({ name }) {
  const titleRef = useRef(null)
  const [isTruncated, setIsTruncated] = useState(false)

  useEffect(() => {
    const element = titleRef.current
    if (!element) {
      return
    }

    const checkTruncation = () => {
      setIsTruncated(element.scrollWidth > element.clientWidth)
    }

    checkTruncation()

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(checkTruncation)
      observer.observe(element)
      return () => observer.disconnect()
    }

    const handleResize = () => {
      checkTruncation()
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [name])

  const title = (
    <span ref={titleRef} className="block truncate text-sm font-semibold leading-none">
      {name}
    </span>
  )

  if (!isTruncated) {
    return title
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{title}</TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs break-words">
        {name}
      </TooltipContent>
    </Tooltip>
  )
}

function buildRetryImageSrc(src, retryCount) {
  if (!src || !retryCount || src.startsWith("data:")) {
    return src
  }

  try {
    const base = globalThis.location?.href || "http://localhost/"
    const url = new URL(src, base)
    const isAppstoreCover =
      url.pathname.includes("/api/v1/appstore/apps/") &&
      url.pathname.endsWith("/cover")
    if (!isAppstoreCover) {
      return src
    }
    url.searchParams.set("_retry", String(retryCount))
    return url.toString()
  } catch {
    return src
  }
}

function AppCardScreenshot({ app, coverSrc }) {
  const [imageSrc, setImageSrc] = useState(coverSrc)
  const [retryCount, setRetryCount] = useState(0)
  const [hasFailed, setHasFailed] = useState(false)

  useEffect(() => {
    setImageSrc(coverSrc)
    setRetryCount(0)
    setHasFailed(false)
  }, [coverSrc])

  if (!coverSrc) {
    return (
      <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
        스크린샷 없음
      </div>
    )
  }

  if (hasFailed) {
    return (
      <div className="flex h-full w-full items-center justify-center px-3 text-center text-xs text-muted-foreground">
        미리보기를 불러오지 못했습니다.
      </div>
    )
  }

  return (
    <img
      src={imageSrc}
      alt={`${app.name} 스크린샷`}
      className="h-full w-full object-contain"
      onError={() => {
        if (retryCount >= 2) {
          setHasFailed(true)
          return
        }
        const nextRetryCount = retryCount + 1
        setRetryCount(nextRetryCount)
        setImageSrc(buildRetryImageSrc(coverSrc, nextRetryCount))
      }}
    />
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
  isOrderEditing = false,
  isOrderSaving = false,
  onMoveApp,
}) {
  const shouldReduceMotion = useReducedMotion()
  const dragRef = useRef({ sourceId: null, targetId: null })
  const [draggedAppId, setDraggedAppId] = useState(null)

  const clearDragState = () => {
    dragRef.current = { sourceId: null, targetId: null }
    setDraggedAppId(null)
  }

  const handleDragStart = (event, appId) => {
    dragRef.current = { sourceId: appId, targetId: null }
    setDraggedAppId(appId)
    event.dataTransfer.effectAllowed = "move"
    event.dataTransfer.setData("text/plain", String(appId))
  }

  const handleDragEnter = (event, targetAppId) => {
    if (!isOrderEditing || isOrderSaving) return
    event.preventDefault()
    const { sourceId: sourceAppId, targetId: previousTargetId } = dragRef.current
    if (!sourceAppId || sourceAppId === targetAppId) return
    if (previousTargetId === targetAppId) return
    dragRef.current.targetId = targetAppId
    onMoveApp?.(sourceAppId, targetAppId)
  }

  const handleKeyboardMove = (event, app, index) => {
    if (!isOrderEditing || isOrderSaving) return
    const direction = ["ArrowLeft", "ArrowUp"].includes(event.key)
      ? -1
      : ["ArrowRight", "ArrowDown"].includes(event.key)
        ? 1
        : 0
    if (!direction) return
    const target = apps[index + direction]
    if (!target) return
    event.preventDefault()
    onMoveApp?.(app.id, target.id)
  }

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
    <div
      className="grid grid-cols-[repeat(auto-fit,280px)] gap-3"
      role={isOrderEditing ? "list" : undefined}
      aria-label={isOrderEditing ? "앱 노출 순서" : undefined}
    >
      {apps.map((app, index) => {
        const isSelected = selectedAppId === app.id
        const isDragged = draggedAppId === app.id
        const coverSrc = getCoverScreenshotUrl(app)

        return (
          <MotionCard
            key={app.id}
            layout={isOrderEditing ? "position" : false}
            transition={shouldReduceMotion ? { duration: 0 } : ORDER_LAYOUT_TRANSITION}
            onClick={() => {
              if (!isOrderEditing) onSelect(app.id)
            }}
            draggable={isOrderEditing && !isOrderSaving}
            tabIndex={isOrderEditing ? 0 : undefined}
            role={isOrderEditing ? "listitem" : undefined}
            aria-label={isOrderEditing ? `${app.name}, 현재 순서 ${index + 1}` : undefined}
            onKeyDown={(event) => handleKeyboardMove(event, app, index)}
            onDragStart={(event) => handleDragStart(event, app.id)}
            onDragEnter={(event) => handleDragEnter(event, app.id)}
            onDragOver={(event) => {
              if (!isOrderEditing || isOrderSaving) return
              event.preventDefault()
              event.dataTransfer.dropEffect = "move"
            }}
            onDrop={(event) => {
              event.preventDefault()
              clearDragState()
            }}
            onDragEnd={clearDragState}
            className={cn(
              "relative flex h-full min-h-[200px] flex-col gap-2 overflow-hidden py-3",
              isSelected && "border-primary/60 ring-1 ring-primary/30",
              isOrderEditing
                ? "cursor-grab focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
                : "cursor-pointer transition-shadow hover:-translate-y-0.5 hover:shadow-md",
              isDragged && "border-2 border-dashed border-primary/60 bg-primary/5 shadow-none",
            )}
          >
            {isDragged ? (
              <div className="flex flex-1 items-center justify-center text-xs font-medium text-primary">
                {index + 1}번 위치에 배치
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between px-5 py-1">
                  <div className="flex min-w-0 items-center gap-2">
                    {isOrderEditing ? (
                      <>
                        <GripVertical
                          className="size-4 shrink-0 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <span className="shrink-0 text-xs font-semibold tabular-nums text-primary">
                          {index + 1}
                        </span>
                      </>
                    ) : null}
                    <AppTitle name={app.name} />
                  </div>

                  <Badge variant="secondary" className="shrink-0 text-[9px] leading-none">
                    {app.category || "기타"}
                  </Badge>
                </div>
                <div className="flex justify-center px-3 py-2">
                  <div className="relative h-32 w-60 overflow-hidden rounded-md bg-muted ring-1 ring-border">
                    <AppCardScreenshot app={app} coverSrc={coverSrc} />
                  </div>
                </div>
                <CardContent className="flex flex-1 flex-col gap-2 px-3 py-1">
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
                      disabled={isOrderEditing}
                      onClick={(event) => {
                        event.stopPropagation()
                        onOpenLink?.(app)
                      }}
                    >
                      Link
                      <ArrowUpRight className="size-3" />
                    </Button>
                  </div>
                </CardContent>
              </>
            )}
          </MotionCard>
        )
      })}
    </div>
  )
}
