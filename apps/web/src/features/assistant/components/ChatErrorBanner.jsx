import { Button } from "@/components/ui/button"

export function ChatErrorBanner({ message, onDismiss }) {
  if (!message) return null

  return (
    <div className="mx-4 shrink-0 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
      <div className="flex items-center justify-between gap-2">
        <span>{message}</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-destructive underline underline-offset-4"
          onClick={onDismiss}
        >
          닫기
        </Button>
      </div>
    </div>
  )
}
