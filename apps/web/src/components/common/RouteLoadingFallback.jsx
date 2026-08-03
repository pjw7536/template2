export function RouteLoadingFallback() {
  return (
    <div
      className="flex h-full min-h-0 items-center justify-center bg-background px-6 py-4 text-foreground"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 rounded-2xl border bg-card px-4 py-3 text-sm shadow-xs">
        <span
          className="size-4 animate-spin rounded-full border-2 border-muted border-t-primary"
          aria-hidden="true"
        />
        <span>화면을 불러오는 중입니다.</span>
      </div>
    </div>
  )
}
