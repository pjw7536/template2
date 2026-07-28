import { Skeleton } from "@/components/ui/skeleton"

import { formatPermissionCount } from "../utils/permissionDisplay"


function getSummaryToneClass(tone) {
  if (tone === "primary") return "bg-primary/10 text-primary"
  if (tone === "destructive") return "bg-destructive/10 text-destructive"
  if (tone === "secondary") return "bg-secondary text-secondary-foreground"
  return "bg-muted text-muted-foreground"
}

export function PermissionSummaryTile({
  icon: Icon,
  label,
  value,
  detail,
  tone = "muted",
  isLoading = false,
}) {
  return (
    <div className="min-w-0 rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {isLoading ? (
            <Skeleton className="mt-2 h-7 w-20" />
          ) : (
            <p className="mt-1 truncate text-2xl font-semibold tabular-nums text-foreground">
              {formatPermissionCount(value)}
            </p>
          )}
        </div>
        <div className={`flex size-10 shrink-0 items-center justify-center rounded-md ${getSummaryToneClass(tone)}`}>
          <Icon className="size-4" />
        </div>
      </div>
      {detail ? <p className="mt-2 truncate text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

export function PermissionDesktopSummary({
  icon: Icon,
  label,
  value,
  detail,
  tone = "muted",
  isLoading = false,
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 border-r px-4 py-3 last:border-r-0">
      <div className={`flex size-9 shrink-0 items-center justify-center rounded-md ${getSummaryToneClass(tone)}`}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-muted-foreground">{label}</p>
        <p className="truncate text-xs text-muted-foreground">{detail}</p>
      </div>
      {isLoading ? (
        <Skeleton className="ml-auto h-7 w-14 shrink-0" />
      ) : (
        <p className="ml-auto shrink-0 text-xl font-semibold tabular-nums text-foreground">
          {formatPermissionCount(value)}
        </p>
      )}
    </div>
  )
}
