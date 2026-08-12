import { Button } from "@/components/ui/button"

export function ChatErrorBanner({
  message,
  onDismiss,
  canRetry = false,
  onRetry,
  retryLabel = "재시도",
  canDiscard = false,
  onDiscard,
  discardLabel = "저장하지 않고 제거",
}) {
  if (!message) return null

  return (
    <div
      className="mx-4 shrink-0 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive"
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-center justify-between gap-2">
        <span>{message}</span>
        <div className="flex shrink-0 items-center gap-1">
          {canRetry ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-destructive underline underline-offset-4"
              onClick={onRetry}
            >
              {retryLabel}
            </Button>
          ) : null}
          {canDiscard ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-destructive underline underline-offset-4"
              onClick={onDiscard}
            >
              {discardLabel}
            </Button>
          ) : null}
          {!canDiscard ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-destructive underline underline-offset-4"
              onClick={onDismiss}
            >
              닫기
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
