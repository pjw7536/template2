import { useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

function clampIndex(value, length) {
  if (!length) return 0
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  const integer = Math.floor(numeric)
  if (integer < 0 || integer >= length) return 0
  return integer
}

export function ScreenshotCarousel({ images, altBase = "스크린샷", initialIndex = 0 }) {
  const safeImages = Array.isArray(images)
    ? images.filter((src) => typeof src === "string" && src.trim()).map((src) => src.trim())
    : []
  const total = safeImages.length
  const [activeIndex, setActiveIndex] = useState(() => clampIndex(initialIndex, total))

  useEffect(() => {
    setActiveIndex((prev) => clampIndex(prev, total))
  }, [total])

  useEffect(() => {
    setActiveIndex(clampIndex(initialIndex, total))
  }, [initialIndex, total])

  if (!total) {
    return (
      <div className="grid h-56 place-items-center overflow-hidden rounded-xl border bg-muted sm:h-64 md:h-72">
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          등록된 스크린샷이 없습니다.
        </div>
      </div>
    )
  }

  const handlePrev = () => {
    setActiveIndex((prev) => (total ? (prev - 1 + total) % total : 0))
  }

  const handleNext = () => {
    setActiveIndex((prev) => (total ? (prev + 1) % total : 0))
  }

  return (
    <div className="grid gap-3">
      <div className="relative grid h-56 place-items-center overflow-hidden rounded-xl border bg-muted sm:h-64 md:h-72">
        <img
          src={safeImages[activeIndex]}
          alt={`${altBase} ${activeIndex + 1}`}
          className="h-full w-full object-contain"
          loading="lazy"
        />

        {total > 1 ? (
          <>
            <Button
              variant="secondary"
              size="icon"
              type="button"
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-background/70 hover:bg-background"
              onClick={handlePrev}
              aria-label="이전 스크린샷"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-background/70 hover:bg-background"
              onClick={handleNext}
              aria-label="다음 스크린샷"
            >
              <ChevronRight className="size-4" />
            </Button>
            <div className="absolute bottom-2 right-2 rounded bg-background/70 px-2 py-1 text-xs text-muted-foreground">
              {activeIndex + 1} / {total}
            </div>
          </>
        ) : null}
      </div>

      {total > 1 ? (
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
          {safeImages.map((src, index) => (
            <button
              key={`${index}-${src.slice(0, 24)}`}
              type="button"
              onClick={() => setActiveIndex(index)}
              className={cn(
                "overflow-hidden rounded-md border bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30",
                index === activeIndex && "ring-2 ring-primary/40",
              )}
              aria-label={`${altBase} ${index + 1} 선택`}
            >
              <img src={src} alt={`${altBase} 썸네일 ${index + 1}`} className="h-14 w-full object-cover" />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

