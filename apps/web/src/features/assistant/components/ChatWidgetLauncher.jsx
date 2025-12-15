import { Bot } from "lucide-react"

import { Button } from "@/components/ui/button"

export function ChatWidgetLauncher({
  buttonPosition,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onClick,
  floatingButtonRef,
  isAttentionTooltipVisible,
  attentionTooltipText,
}) {
  const isPositioned = buttonPosition.x !== null && buttonPosition.y !== null

  return (
    <div
      className={[
        "fixed z-50",
        isPositioned ? "cursor-grab active:cursor-grabbing" : "bottom-4 right-4",
      ]
        .filter(Boolean)
        .join(" ")}
      style={
        isPositioned
          ? { left: buttonPosition.x, top: buttonPosition.y }
          : undefined
      }
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {isAttentionTooltipVisible ? (
        <div
          className="pointer-events-none absolute left-1/2 bottom-full mb-2 -translate-x-1/2"
          role="status"
          aria-live="polite"
        >
          <div className="relative whitespace-nowrap rounded-full border border-border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md">
            {attentionTooltipText}
            <div className="absolute left-1/2 top-full h-2 w-2 -translate-x-1/2 -translate-y-1 rotate-45 bg-popover border-b border-r border-border" />
          </div>
        </div>
      ) : null}

      <Button
        size="icon"
        className="h-12 w-12 rounded-full shadow-lg"
        onClick={onClick}
        aria-label="Open assistant chat"
        ref={floatingButtonRef}
      >
        <Bot className="size-8" />
        <span className="sr-only">도움받기</span>
      </Button>
    </div>
  )
}
